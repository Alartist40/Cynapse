# AI.md — Elara & HiveMind Architecture

**Version**: 1.0.0  
**Date**: 2026-02-03  
**Author**: Alejandro Eduardo Garcia Romero  
**Status**: Production Optimization Phase

---

## Executive Summary

This document describes the AI architecture of Cynapse, consisting of two integrated systems:

1. **Elara**: A custom ~2.8B parameter language model with novel architecture (MoE + TiDAR + TRM)
2. **HiveMind**: An n8n-style orchestration layer that connects Elara to tools, documents, and training pipelines

The goal is **unified intelligence**: One model that divides into task-specific agents, learns from documents, and improves through automated training workflows.

---

## Part 1: Elara — The Core Model

### 1.1 Design Philosophy

Unlike standard LLMs that rely on scale, Elara uses **architectural efficiency**:

- **Sparse Activation**: Only 2 of 9 experts active per token (DeepSeek MoE)
- **Recursive Depth**: 32 physical layers → 64 effective layers via weight reuse (TRM)
- **Dual-Mode Cognition**: Autoregressive for output, diffusion for internal reasoning (TiDAR)
- **Mobile-First**: Targets 4GB RAM quantized (3B params → 2GB Q4_K_M)

### 1.2 Architecture Components

```
Input Tokens
    │
    ▼
┌─────────────────────────────────────────┐
│  Token + Position Embeddings (RoPE)     │
└──────────────────┬──────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
    ▼              ▼              ▼
┌────────┐   ┌──────────────┐   ┌────────────┐
│Recursive│   │   Recursive  │   │  Recursive │  × 32 blocks
│Block 0 │   │  Block 1     │   │  Block 31  │  (MoE on odd)
│ (Dense)│   │   (MoE)      │   │   (Dense)  │
└────┬───┘   └──────┬───────┘   └─────┬──────┘
     │              │                 │
     └──────────────┴─────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  LayerNorm + Dual Heads                 │
│  ├── AR Head (lm_head): Output          │
│  └── Diffusion Head: Internal drafting  │
└─────────────────────────────────────────┘
```

### 1.3 Key Innovations

#### A. DeepSeek-Style MoE with Shared Experts

Standard MoE routes to top-k experts. Elara adds **shared experts** that are always active:

```python
# Standard MoE: 8 experts, top-2 → 2 active
# Elara MoE: 8 routed (top-2) + 1 shared (always) → 3 active

class MoE(nn.Module):
    def forward(self, x):
        # Always-active pathway (common knowledge)
        for shared in self.shared_experts:
            x += shared(x)

        # Routed pathway (specialized knowledge)
        gates, indices = self.router(x)
        for i, expert in enumerate(self.experts):
            mask = (indices == i).any(dim=-1)
            if mask.any():
                x += expert(x) * gates[:, :, i].unsqueeze(-1)
        return x
```

**Why**: Shared experts capture "universal" knowledge (grammar, facts), routed experts handle "specialized" knowledge (coding, math). This reduces expert switching overhead.

#### B. TiDAR (Think in Diffusion, AR in Talk)

Standard autoregressive models generate left-to-right. TiDAR adds a **diffusion head** for internal reasoning:

```
User Query: "Solve x^2 + 5x + 6 = 0"

Standard AR:
[thinking token] → [thinking token] → [thinking token] → "x = -2, x = -3"
(All visible, slow)

TiDAR Mode:
Diffusion Head (internal): [x^2][+5x][+6][=0] → [factors][(x+2)(x+3)] → [roots]
                          (parallel processing via diffusion timesteps)
AR Head (output): "x = -2, x = -3"
                  (verified, coherent)
```

**Implementation**:
```python
# Training: Both heads trained simultaneously
loss = loss_ar + 0.5 * loss_diffusion

# Inference: Draft → Verify
def generate_tidar(self, idx, max_tokens, draft_len=4):
    for _ in range(0, max_tokens, draft_len):
        # 1. THINK: Draft 4 tokens in parallel via diffusion
        drafts = self.diffusion_head.fast_draft(idx, draft_len)

        # 2. TALK: Verify with AR head (accept/reject)
        verified = self.verify_drafts(idx, drafts)
        idx = torch.cat([idx, verified], dim=1)
```

#### C. Tiny Recursive Model (TRM)

Instead of 64 physical layers (memory heavy), Elara has 32 layers applied **twice recursively**:

```python
class RecursiveBlock(nn.Module):
    def forward(self, x):
        for _ in range(self.recursion_depth):  # depth = 2
            x = self.block(x)  # Same weights, iterated
        return x
```

**Benefits**:
- 2× depth without 2× parameters
- Forces iterative refinement (better reasoning)
- Memory efficient: Only stores 32 layer checkpoints for backprop

### 1.4 Configuration Specification

```python
@dataclass
class GPTConfig:
    # Standard GPT
    block_size: int = 1024        # Context window
    vocab_size: int = 50304       # GPT-2 BPE + padding
    n_layer: int = 32             # Physical layers
    n_head: int = 16              # Attention heads
    n_embd: int = 1280            # Embedding dim (reduced for mobile)
    dropout: float = 0.0          # Inference: 0, Training: 0.1
    bias: bool = True

    # MoE
    num_experts: int = 8          # Routed experts
    num_shared_experts: int = 1   # Always-active
    moe_top_k: int = 2            # Experts per token
    use_moe_layers: bool = True

    # TRM
    recursion_depth: int = 2      # Effective layers = 64

    # TiDAR
    use_diffusion_head: bool = True
```

**Parameter Count**:
- Target: ~2.8B parameters
- With MoE sparsity: ~1.5B active per token
- Fits 4GB RAM (Q4_K_M quantization)

### 1.5 File Structure

```
elara/
├── model.py              # Full architecture (training + inference)
├── elara.py              # [NEW] Optimized inference-only core
├── configurator.py       # Command-line config override
├── verify.py             # Architecture validation
├── sample.py             # Text generation script
├── train.py              # Training loop (DDP support)
├── bench.py              # Performance benchmarking
├── requirements.txt      # Dependencies
├── manifest.json         # Cynapse neuron manifest
│
├── data/                 # Training datasets
│   ├── shakespeare_char/ # Character-level (testing)
│   ├── shakespeare/      # Token-level (testing)
│   └── openwebtext/      # Full training (~9B tokens)
│
└── out/                  # Checkpoints and outputs
    └── ckpt.pt           # Model checkpoint
```

### 1.6 Current Implementation Status

**Working**:
- ✅ Model architecture (MoE + Shared Experts + TRM)
- ✅ Training loop with DDP support
- ✅ AR generation
- ✅ Checkpoint save/load
- ✅ Verification script

**Partial**:
- ⚠️ TiDAR generation (simplified implementation, needs full diffusion schedule)
- ⚠️ GGUF export (requires architecture mapping to standard format)

**Dependencies** (Current):
```
torch>=2.0
transformers
numpy
tiktoken
datasets
wandb
tqdm
```

---

## Part 2: HiveMind — The Orchestration Layer

### 2.1 Concept

HiveMind is **not** just a chat interface. It is an n8n-style workflow engine where:

- **Queen (Elara)**: The central intelligence
- **Drones**: Tool-calling agents (code, math, search)
- **Workers**: Training pipeline automation
- **Honeycomb**: Vector memory (RAG)

**Key Insight**: Instead of separate models for different tasks, Elara uses **specialized prompting** via Drones. One model, multiple personas.

### 2.2 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        HIVEMIND CLI                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   User Input                                                 │
│      │                                                       │
│      ▼                                                       │
│   ┌─────────────┐                                            │
│   │   Router    │◄── Query classification (code/math/chat)   │
│   │   (Drone)   │                                            │
│   └──────┬──────┘                                            │
│          │                                                   │
│    ┌─────┼─────┬──────────────┐                              │
│    ▼     ▼     ▼              ▼                              │
│ ┌────┐ ┌────┐ ┌────┐    ┌──────────┐                        │
│ │Code│ │Math│ │Chat│    │ Document │                        │
│ │Qwen│ │Deep│ │Llama│   │  Ingest  │                        │
│ └──┬─┘ └──┬─┘ └──┬─┘    └────┬─────┘                        │
│    │      │      │           │                              │
│    └──────┴──────┴───────────┘                              │
│                   │                                          │
│                   ▼                                          │
│            ┌──────────┐                                      │
│            │  QUEEN   │                                      │
│            │ (Elara)  │                                      │
│            │  3B MoE  │                                      │
│            └────┬─────┘                                      │
│                 │                                            │
│       ┌─────────┼─────────┐                                  │
│       ▼         ▼         ▼                                  │
│   ┌──────┐  ┌──────┐  ┌──────┐                              │
│   │Ollama│  │AirLLM│  │Output│                              │
│   │Bridge│  │Train │  │User  │                              │
│   └──────┘  └──────┘  └──────┘                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Components

#### A. Router (Drone Dispatcher)

Classifies queries and prepends system prompts:

```python
class Router:
    TEMPLATES = {
        "code": "You are CodeQwen, a coding specialist. Think step-by-step.",
        "math": "You are DeepMath, a mathematical reasoning expert.",
        "chat": "You are Elara, a helpful assistant."
    }

    def route(self, query: str) -> str:
        if any(kw in query for kw in ["code", "function", "bug"]):
            return self.TEMPLATES["code"] + query
        elif any(kw in query for kw in ["math", "calculate", "solve"]):
            return self.TEMPLATES["math"] + query
        return self.TEMPLATES["chat"] + query
```

**Optimization**: Instead of loading 3 separate models, we use **prompt engineering** on one model. 3× efficiency.

#### B. Training Pipeline (Workers)

Automated distillation from teacher models:

```
User provides feedback ──► Memory.json
                                │
                                ▼
                        ┌───────────────┐
                        │   Scheduler   │ (Weekly/Monthly)
                        └───────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌────────┐  ┌──────────┐  ┌────────┐
              │AirLLM  │  │ Ollama   │  │ Local  │
              │70B     │  │ Mixtral  │  │ Docs   │
              │Teacher │  │ Teacher  │  │ RAG    │
              └───┬────┘  └────┬─────┘  └───┬────┘
                  │            │            │
                  └────────────┴────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Distillation      │
                    │   (Knowledge        │
                    │    Transfer)        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Elara (3B)        │
                    │   Updated Weights   │
                    └─────────────────────┘
```

**Key Features**:
- **Multi-teacher learning**: Combine knowledge from multiple large models
- **Document-augmented training**: RAG-retrieved context added to training samples
- **Continuous learning**: Automated fine-tuning on accumulated feedback

#### C. Honeycomb (Vector Memory)

Local RAG without cloud dependencies:

```python
class Honeycomb:
    """Lightweight vector database using numpy (no FAISS/Pinecone)"""

    def __init__(self, dim=1280):
        self.vectors = []
        self.texts = []
        self.metadata = []

    def ingest(self, file_path: str):
        # Chunk document, embed using Elara, store locally
        pass

    def retrieve(self, query: str, k=3):
        # Cosine similarity search, return top-k chunks
        pass
```

**Design Choice**: Use numpy for similarity search instead of FAISS to avoid heavy dependencies.

### 2.4 HiveMind CLI Commands

```bash
# Interactive mode
python hivemind.py

# Direct query with routing
python hivemind.py ask "Write a Python function"

# Document ingestion
python hivemind.py feed document.pdf

# Trigger training
python hivemind.py learn --source ollama --model mixtral
```

---

## Part 3: Optimization Strategy

### 3.1 Current Pain Points

1. **Dependency Bloat**: 2GB+ install
2. **Training/Inference Coupling**: Can not deploy without training code
3. **MoE Overhead**: Router computation on every forward pass
4. **No Quantization**: Full FP16 only
5. **Python GIL**: Single-threaded inference

### 3.2 Target Architecture (Elara.py)

**Goals**:
- Single-file deployment
- Minimal dependencies (numpy, optional torch)
- Quantization-ready
- <500 lines (vs current ~750)

### 3.3 Implementation Plan

**Phase 1**: Decouple inference from training
**Phase 2**: Fuse operations, add quantization
**Phase 3**: Minimize to single file with optional deps

---

## Appendices

### A. Comparison Table

| Feature | GPT-3.5 | Llama-2-7B | Elara-3B |
|---------|---------|------------|----------|
| Parameters | 175B | 7B | 2.8B (1.5B active) |
| MoE | No | No | Yes |
| Mobile | No | No | Yes |
| Local Training | No | Limited | Full |

### B. File Manifest

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| model.py | ~750 | Full architecture | Stable |
| elara.py | ~250 | Optimized core | In Progress |
| train.py | ~350 | Training loop | Stable |
| hivemind.py | ~400 | Orchestration | In Progress |

---

*"The best model is not the biggest—it is the one that fits in your pocket and learns from you alone."*
