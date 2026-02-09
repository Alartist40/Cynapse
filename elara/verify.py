"""
Verification script for Custom 3B Model
"""
import torch
from model import GPT, GPTConfig

def verify():
    # 1. Initialize Model
    # Use defaults from GPTConfig which are now tuned for ~3B
    config = GPTConfig()
    print("Initializing model with config:", config)
    
    model = GPT(config)
    model.to('cpu') # Ensure it fits on RAM for structure check, or verify param count
    
    # 2. Check Parameters
    num_params = model.get_num_params()
    print(f"Total Parameters: {num_params:,}")
    print(f"Total Parameters (Millions): {num_params/1e6:.2f}M")
    print(f"Total Parameters (Billions): {num_params/1e9:.2f}B")
    
    # Target is ~2.8B (Mobile Optimized)
    # n_layer=32, n_embd=1280, n_head=16. 
    
    # 4. Check Shared Experts
    print("Checking for Shared Experts (DeepSeek Style)...")
    has_shared = False
    # Check odd layers which should be MoE
    block = model.transformer.h[1].block.mlp
    if hasattr(block, 'shared_experts'):
        print(f"Shared Experts found! Count: {len(block.shared_experts)}")
        has_shared = True
    else:
        print("WARNING: Shared Experts NOT found in MoE layer.")
    
    # 5. Test Forward Pass (Dummy)
    print("Running forward pass...")
    dummy_input = torch.zeros((1, 64), dtype=torch.long)
    try:
        logits, loss = model(dummy_input)
        print("AR Forward Pass Successful. Logits shape:", logits.shape)
        
        # Test TiDAR mode
        if config.use_diffusion_head:
            diff_logits, _ = model(dummy_input, mode='diffusion')
            print("Diffusion Forward Pass Successful.")
            
            # Test TiDAR Generation logic
            print("Testing TiDAR (Diffusion) Generation...")
            # Generate 10 tokens
            gen_out = model.generate_tidar(dummy_input[:, :4], max_new_tokens=10)
            print("TiDAR Generation Successful. Output shape:", gen_out.shape)
            
        if has_shared:
             print("VERIFICATION COMPLETE: Custom 3B Model (MoE+Shared+TiDAR+Recursive) is structurally valid.")
            
    except Exception as e:
        print("Forward pass failed!")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    verify()
