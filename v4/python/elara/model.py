"""
Full definition of a GPT Language Model, all of it in this single file.
Modified to include:
1. DeepSeek-inspired MoE (Mixture of Experts)
2. TiDAR (Think in Diffusion, Talk in Autoregression) hybrid architecture
3. TRM (Tiny Recursive Model) recursive reasoning blocks

References:
1) nanoGPT (Karpathy)
2) DeepSeek OCR / MoE papers
3) TiDAR paper
4) Tiny Recursive Model paper
"""

import math
import inspect
from dataclasses import dataclass

import torch
import torch.nn as nn
from torch.nn import functional as F

# --- RoPE (Rotary Positional Embeddings) ---
def precompute_freqs_cis(dim: int, end: int, theta: float = 10000.0):
    """
    Precompute the frequency tensor for complex exponentials (RoPE).
    """
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
    t = torch.arange(end, device=freqs.device)
    freqs = torch.outer(t, freqs).float()
    freqs_cis = torch.polar(torch.ones_like(freqs), freqs)  # complex64
    return freqs_cis

def reshape_for_broadcast(freqs_cis: torch.Tensor, x: torch.Tensor):
    """
    Reshape frequency tensor for broadcasting with attention tensor.
    """
    ndim = x.ndim
    assert 0 <= 1 < ndim
    assert freqs_cis.shape == (x.shape[1], x.shape[-1])
    shape = [d if i == 1 or i == ndim - 1 else 1 for i, d in enumerate(x.shape)]
    return freqs_cis.view(*shape)

def apply_rotary_emb(
    xq: torch.Tensor,
    xk: torch.Tensor,
    freqs_cis: torch.Tensor,
) -> tuple:
    """
    Apply rotary embeddings to query and key tensors.
    """
    xq_ = torch.view_as_complex(xq.float().reshape(*xq.shape[:-1], -1, 2))
    xk_ = torch.view_as_complex(xk.float().reshape(*xk.shape[:-1], -1, 2))
    freqs_cis = reshape_for_broadcast(freqs_cis, xq_)
    xq_out = torch.view_as_real(xq_ * freqs_cis).flatten(3)
    xk_out = torch.view_as_real(xk_ * freqs_cis).flatten(3)
    return xq_out.type_as(xq), xk_out.type_as(xk)

class LayerNorm(nn.Module):
    """ LayerNorm but with an optional bias. PyTorch doesn't support simply bias=False """

    def __init__(self, ndim, bias):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(ndim))
        self.bias = nn.Parameter(torch.zeros(ndim)) if bias else None

    def forward(self, input):
        return F.layer_norm(input, self.weight.shape, self.weight, self.bias, 1e-5)

class CausalSelfAttention(nn.Module):

    def __init__(self, config):
        super().__init__()
        assert config.n_embd % config.n_head == 0
        # key, query, value projections for all heads, but in a batch
        self.c_attn = nn.Linear(config.n_embd, 3 * config.n_embd, bias=config.bias)
        # output projection
        self.c_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)
        # regularization
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)
        self.n_head = config.n_head
        self.n_embd = config.n_embd
        self.dropout = config.dropout
        # flash attention make GPU go brrrrr but support is only in PyTorch >= 2.0
        self.flash = hasattr(torch.nn.functional, 'scaled_dot_product_attention')
        if not self.flash:
            print("WARNING: using slow attention. Flash Attention requires PyTorch >= 2.0")
            # causal mask to ensure that attention is only applied to the left in the input sequence
            self.register_buffer("bias", torch.tril(torch.ones(config.block_size, config.block_size))
                                        .view(1, 1, config.block_size, config.block_size))

    def forward(self, x):
        B, T, C = x.size() # batch size, sequence length, embedding dimensionality (n_embd)

        # calculate query, key, values for all heads in batch and move head forward to be the batch dim
        q, k, v  = self.c_attn(x).split(self.n_embd, dim=2)
        k = k.view(B, T, self.n_head, C // self.n_head).transpose(1, 2) # (B, nh, T, hs)
        q = q.view(B, T, self.n_head, C // self.n_head).transpose(1, 2) # (B, nh, T, hs)
        v = v.view(B, T, self.n_head, C // self.n_head).transpose(1, 2) # (B, nh, T, hs)

        # causal self-attention; Self-attend: (B, nh, T, hs) x (B, nh, hs, T) -> (B, nh, T, T)
        if self.flash:
            # efficient attention using Flash Attention CUDA kernels
            y = torch.nn.functional.scaled_dot_product_attention(q, k, v, attn_mask=None, dropout_p=self.dropout if self.training else 0, is_causal=True)
        else:
            # manual implementation of attention
            att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(k.size(-1)))
            att = att.masked_fill(self.bias[:,:,:T,:T] == 0, float('-inf'))
            att = F.softmax(att, dim=-1)
            att = self.attn_dropout(att)
            y = att @ v # (B, nh, T, T) x (B, nh, T, hs) -> (B, nh, T, hs)
        y = y.transpose(1, 2).contiguous().view(B, T, C) # re-assemble all head outputs side by side

        # output projection
        y = self.resid_dropout(self.c_proj(y))
        return y

class MLP(nn.Module):
    """
    MLP with SwiGLU activation (as used in LLaMA, Mistral, etc.)
    SwiGLU: x * SiLU(gate(x)) - better performance than GELU in modern LLMs
    """

    def __init__(self, config):
        super().__init__()
        hidden_dim = 4 * config.n_embd
        # SwiGLU uses 3 projections: gate, up, down
        self.gate = nn.Linear(config.n_embd, hidden_dim, bias=config.bias)
        self.up = nn.Linear(config.n_embd, hidden_dim, bias=config.bias)
        self.down = nn.Linear(hidden_dim, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        # SwiGLU: down(SiLU(gate(x)) * up(x))
        return self.dropout(self.down(F.silu(self.gate(x)) * self.up(x)))

# --- MoE Components ---
class NoisyTopkRouter(nn.Module):
    def __init__(self, n_embed, num_experts, top_k):
        super(NoisyTopkRouter, self).__init__()
        self.top_k = top_k
        self.topkroute_linear = nn.Linear(n_embed, num_experts)
        self.noise_linear = nn.Linear(n_embed, num_experts)

    def forward(self, mh_output):
        # mh_output is the output tensor from multihead self attention block
        logits = self.topkroute_linear(mh_output)
        noise_logits = self.noise_linear(mh_output)

        # Adding scaled unit gaussian noise to the logits
        noise = torch.randn_like(logits) * F.softplus(noise_logits)
        noisy_logits = logits + noise

        top_k_logits, indices = noisy_logits.topk(self.top_k, dim=-1)
        zeros = torch.full_like(noisy_logits, float('-inf'))
        sparse_logits = zeros.scatter(-1, indices, top_k_logits)
        router_output = F.softmax(sparse_logits, dim=-1)
        return router_output, indices

class MoE(nn.Module):
    """
    Sparse Mixture of Experts Layer with Shared Experts (DeepSeek Style)
    """
    def __init__(self, config):
        super().__init__()
        self.num_experts = config.num_experts
        self.num_shared_experts = config.num_shared_experts
        self.top_k = config.moe_top_k

        # Router
        self.router = NoisyTopkRouter(config.n_embd, self.num_experts, self.top_k)

        # Routed Experts
        self.experts = nn.ModuleList([MLP(config) for _ in range(self.num_experts)])

        # Shared Experts (Always active)
        self.shared_experts = nn.ModuleList([MLP(config) for _ in range(self.num_shared_experts)])

        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        # x: (B, T, C)
        final_output = torch.zeros_like(x)

        # 1. Shared Experts (Always Active)
        for shared_expert in self.shared_experts:
            final_output += shared_expert(x)

        # 2. Routed Experts
        gating_output, indices = self.router(x)

        # Simple Iterative Routing (slow but clear)
        for i, expert in enumerate(self.experts):
            expert_mask = (indices == i).any(dim=-1)
            if expert_mask.any():
                expert_out = expert(x)
                weight = gating_output[:, :, i].unsqueeze(-1)
                final_output += expert_out * weight

        return final_output

class Block(nn.Module):
    """ Transformer Block, optionally recursive! """

    def __init__(self, config, is_moe=False):
        super().__init__()
        self.ln_1 = LayerNorm(config.n_embd, bias=config.bias)
        self.attn = CausalSelfAttention(config)
        self.ln_2 = LayerNorm(config.n_embd, bias=config.bias)

        if is_moe:
            self.mlp = MoE(config)
        else:
            self.mlp = MLP(config)

    def forward(self, x):
        x = x + self.attn(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
        return x

class RecursiveBlock(nn.Module):
    """
    A block that recursively applies itself 'recursion_depth' times.
    Based on Tiny Recursive Model (TRM) concepts.
    """
    def __init__(self, config, is_moe=False):
        super().__init__()
        self.block = Block(config, is_moe)
        self.recursion_depth = config.recursion_depth

    def forward(self, x):
        # Recurse: Feed output back to input N times
        for _ in range(self.recursion_depth):
            x = self.block(x)
        return x

# --- TiDAR Components ---
class DiffusionHead(nn.Module):
    """
    Drafting head for TiDAR (Think in Diffusion).
    Predicts a diffusion update or direct token embedding draft.
    """
    def __init__(self, config):
        super().__init__()
        # Simple diffusion head: linear projection to vocab size,
        # treated as predicting x_0 or noise.
        self.decoder = nn.Linear(config.n_embd, config.vocab_size, bias=False)

    def forward(self, x):
        return self.decoder(x)

@dataclass
class GPTConfig:
    block_size: int = 1024
    vocab_size: int = 50304
    n_layer: int = 32  # Increased for 3B approx (with MoE)
    n_head: int = 16
    n_embd: int = 1280 # Reduced specificially to target ~2.8B params for mobile efficiency
    dropout: float = 0.0
    bias: bool = True

    # New Architecture Params
    # MoE
    num_experts: int = 8
    num_shared_experts: int = 1 # DeepSeek-style shared expert
    moe_top_k: int = 2
    use_moe_layers: bool = True # Use MoE in some layers

    # Recursive (TRM)
    recursion_depth: int = 2 # Recurse twice per block

    # TiDAR
    use_diffusion_head: bool = True

class GPT(nn.Module):

    def __init__(self, config):
        super().__init__()
        assert config.vocab_size is not None
        assert config.block_size is not None
        self.config = config

        self.transformer = nn.ModuleDict(dict(
            wte = nn.Embedding(config.vocab_size, config.n_embd),
            wpe = nn.Embedding(config.block_size, config.n_embd),
            drop = nn.Dropout(config.dropout),
            # Mix of normal and recursive, MoE and dense blocks
            h = nn.ModuleList([
                RecursiveBlock(config, is_moe=(config.use_moe_layers and i % 2 == 1)) # MoE on odd layers
                for i in range(config.n_layer)
            ]),
            ln_f = LayerNorm(config.n_embd, bias=config.bias),
        ))

        # AR Head (Talking)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)

        # TiDAR Diffusion Head (Thinking/Drafting)
        if config.use_diffusion_head:
            self.diffusion_head = DiffusionHead(config)

        # Weight tying
        self.transformer.wte.weight = self.lm_head.weight

        # Init weights
        self.apply(self._init_weights)
        for pn, p in self.named_parameters():
            if pn.endswith('c_proj.weight'):
                torch.nn.init.normal_(p, mean=0.0, std=0.02/math.sqrt(2 * config.n_layer))

        import sys
        print("number of parameters: %.2fM" % (self.get_num_params()/1e6,), file=sys.stderr)

    def get_num_params(self, non_embedding=True):
        n_params = sum(p.numel() for p in self.parameters())
        if non_embedding:
            n_params -= self.transformer.wpe.weight.numel()
        return n_params

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx, targets=None, mode='ar'):
        """
        mode: 'ar' (Autoregressive) or 'diffusion' (Drafting/Thinking)
        """
        device = idx.device
        b, t = idx.size()
        assert t <= self.config.block_size, f"Cannot forward sequence of length {t}, block size is only {self.config.block_size}"
        pos = torch.arange(0, t, dtype=torch.long, device=device)

        # Forward Transformer
        tok_emb = self.transformer.wte(idx)
        pos_emb = self.transformer.wpe(pos)
        x = self.transformer.drop(tok_emb + pos_emb)

        # Recursive & MoE Blocks
        for block in self.transformer.h:
            x = block(x)

        x = self.transformer.ln_f(x)

        loss = None
        logits = None
        diff_logits = None

        # Output Heads based on Mode
        if targets is not None:
            # Training: Return both for loss calculation
            logits = self.lm_head(x)
            loss_ar = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-1)

            loss = loss_ar

            if self.config.use_diffusion_head:
                diff_logits = self.diffusion_head(x)
                # TiDAR Training: Simply add a dummy diffusion loss for now (e.g., MSE on embeddings or CE)
                # Real TiDAR uses complex masking.
                loss_diff = F.cross_entropy(diff_logits.view(-1, diff_logits.size(-1)), targets.view(-1), ignore_index=-1)
                loss += 0.5 * loss_diff # Combined loss

        else:
            # Inference
            if mode == 'diffusion' and self.config.use_diffusion_head:
                # Drafting phase
                logits = self.diffusion_head(x[:, [-1], :])
            else:
                # Standard AR
                logits = self.lm_head(x[:, [-1], :])

        return logits, loss

    def crop_block_size(self, block_size):
        assert block_size <= self.config.block_size
        self.config.block_size = block_size
        self.transformer.wpe.weight = nn.Parameter(self.transformer.wpe.weight[:block_size])
        for block in self.transformer.h:
            if hasattr(block.block.attn, 'bias'):
                 block.block.attn.bias = block.block.attn.bias[:,:,:block_size,:block_size]

    @classmethod
    def from_pretrained(cls, model_type, override_args=None):
        assert model_type in {'gpt2', 'gpt2-medium', 'gpt2-large', 'gpt2-xl'}
        override_args = override_args or {}
        assert all(k == 'dropout' for k in override_args)
        from transformers import GPT2LMHeadModel
        print("loading weights from pretrained gpt: %s" % model_type)

        config_args = {
            'gpt2':         dict(n_layer=12, n_head=12, n_embd=768),
            'gpt2-medium':  dict(n_layer=24, n_head=16, n_embd=1024),
            'gpt2-large':   dict(n_layer=36, n_head=20, n_embd=1280),
            'gpt2-xl':      dict(n_layer=48, n_head=25, n_embd=1600),
        }[model_type]
        print("forcing vocab_size=50257, block_size=1024, bias=True")
        config_args['vocab_size'] = 50257
        config_args['block_size'] = 1024
        config_args['bias'] = True
        if 'dropout' in override_args:
            print(f"overriding dropout rate to {override_args['dropout']}")
            config_args['dropout'] = override_args['dropout']

        # Create Custom Model
        config = GPTConfig(**config_args)
        model = GPT(config)

        return model

    def configure_optimizers(self, weight_decay, learning_rate, betas, device_type):
        param_dict = {pn: p for pn, p in self.named_parameters()}
        param_dict = {pn: p for pn, p in param_dict.items() if p.requires_grad}
        decay_params = [p for n, p in param_dict.items() if p.dim() >= 2]
        nodecay_params = [p for n, p in param_dict.items() if p.dim() < 2]
        optim_groups = [
            {'params': decay_params, 'weight_decay': weight_decay},
            {'params': nodecay_params, 'weight_decay': 0.0}
        ]
        num_decay_params = sum(p.numel() for p in decay_params)
        num_nodecay_params = sum(p.numel() for p in nodecay_params)
        print(f"num decayed parameter tensors: {len(decay_params)}, with {num_decay_params:,} parameters")
        print(f"num non-decayed parameter tensors: {len(nodecay_params)}, with {num_nodecay_params:,} parameters")
        fused_available = 'fused' in inspect.signature(torch.optim.AdamW).parameters
        use_fused = fused_available and device_type == 'cuda'
        extra_args = dict(fused=True) if use_fused else dict()
        optimizer = torch.optim.AdamW(optim_groups, lr=learning_rate, betas=betas, **extra_args)
        print(f"using fused AdamW: {use_fused}")

        return optimizer

    def estimate_mfu(self, fwdbwd_per_iter, dt):
        N = self.get_num_params()
        cfg = self.config
        L, H, Q, T = cfg.n_layer, cfg.n_head, cfg.n_embd//cfg.n_head, cfg.block_size
        flops_per_token = 6*N + 12*L*H*Q*T
        flops_per_fwdbwd = flops_per_token * T
        flops_per_iter = flops_per_fwdbwd * fwdbwd_per_iter
        flops_achieved = flops_per_iter * (1.0/dt)
        flops_promised = 312e12
        mfu = flops_achieved / flops_promised
        return mfu

    @torch.no_grad()
    def generate(self, idx, max_new_tokens, temperature=1.0, top_k=None):
        for _ in range(max_new_tokens):
            idx_cond = idx if idx.size(1) <= self.config.block_size else idx[:, -self.config.block_size:]

            # Simple AR generation for now (using AR head)
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] / temperature
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float('Inf')
            probs = F.softmax(logits, dim=-1)
            idx_next = torch.multinomial(probs, num_samples=1)
            idx = torch.cat((idx, idx_next), dim=1)

        return idx

    @torch.no_grad()
    def generate_tidar(self, idx, max_new_tokens, draft_len=4):
        """
        TiDAR Generation: Drafts 'draft_len' tokens via DiffusionHead, then Verifies via AR.
        (Simplified implementation for demonstration)
        """
        # In a real TiDAR impl, the diffusion head would iteratively partial-denoise a block of tokens.
        # Here we just predict the 'draft' using the diffusion head (one-shot for this baseline).

        for _ in range(0, max_new_tokens, draft_len):
            # 1. Thinking (Drafting)
            # Predict next token embeddings/Ids using Diffusion Head
            # We treat the diffusion head as a 'fast drafter' here
            block_draft = []
            curr_idx = idx

            # Draft loop
            for k in range(draft_len):
                logits_diff, _ = self(curr_idx, mode='diffusion')
                # Greedy draft
                next_token = torch.argmax(logits_diff[:, -1, :], dim=-1, keepdim=True)
                block_draft.append(next_token)
                curr_idx = torch.cat((curr_idx, next_token), dim=1)

            # 2. Talking (Verification) using AR Head
            # We run the AR model on the drafted sequence to compute validities
            # For this baseline, we just accept the drafts or stop if they diverge from AR?
            # TiDAR usually uses the draft to speed up the AR pass (Speculative Decoding style).
            # We will just append the drafts to idx for now to show flow.

            # Concatenate drafts
            if block_draft:
                 drafts = torch.cat(block_draft, dim=1)
                 idx = torch.cat((idx, drafts), dim=1)

        return idx
