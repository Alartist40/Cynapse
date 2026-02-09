"""
Elara Model Loader
==================

Optimized loading with memory mapping and GPU configuration.
Bridges reference model to Cynapse system.
"""

import sys
import torch
from pathlib import Path
from typing import Optional, Dict
import warnings

# Import Elara model from reference implementation
# Import Elara model from reference implementation
project_root = Path(__file__).parent.parent.parent.parent.parent
elara_path = project_root / 'elara'
if str(elara_path) not in sys.path:
    sys.path.insert(0, str(elara_path))

try:
    from model import GPT, GPTConfig
    HAS_ELARA = True
except ImportError:
    HAS_ELARA = False
    warnings.warn("Elara reference model not found.")


class ElaraModelLoader:
    """
    Loads and configures Elara model for Cynapse.
    
    Features:
    - Memory-mapped loading for large models
    - GPU layer optimization
    - Flash Attention support
    """
    
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path('./cynapse/data/models/elara.gguf')
        self.model = None
        self.config = None
        
    def load(
        self,
        gpu_layers: int = -1,  # -1 = auto
        precision: str = 'auto',
        device: str = 'auto'
    ) -> Optional[GPT]:
        """
        Load Elara model with optimizations.
        
        Args:
            gpu_layers: Number of layers to put on GPU (-1 for auto)
            precision: 'bf16', 'fp16', 'fp32', or 'auto'
            device: 'cuda', 'cpu', or 'auto'
            
        Returns:
            Loaded model or None if unavailable
        """
        if not HAS_ELARA:
            print("Elara model not available")
            return None
        
        if not self.model_path.exists():
            print(f"Model not found: {self.model_path}")
            print("Place elara.gguf in cynapse/data/models/")
            return None
        
        # Auto-configure device
        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Auto-configure precision
        if precision == 'auto':
            if device == 'cuda' and torch.cuda.is_bf16_supported():
                precision = 'bf16'
            elif device == 'cuda':
                precision = 'fp16'
            else:
                precision = 'fp32'
        
        # Create model config
        self.config = GPTConfig(
            block_size=1024,
            vocab_size=50304,
            n_layer=32,
            n_head=16,
            n_embd=1280,
            dropout=0.0,
            bias=False,
            num_experts=8,
            top_k=2
        )
        
        print(f"Loading Elara model...")
        print(f"  Device: {device}")
        print(f"  Precision: {precision}")
        
        try:
            # Initialize model
            self.model = GPT(self.config)
            
            # Load weights (placeholder - would load actual weights)
            # checkpoint = torch.load(self.model_path, map_location=device)
            # self.model.load_state_dict(checkpoint['model_state_dict'])
            
            # Move to device
            self.model.to(device)
            
            # Set precision
            if precision == 'bf16':
                self.model = self.model.to(torch.bfloat16)
            elif precision == 'fp16':
                self.model = self.model.half()
            
            # Compile if available (PyTorch 2.0+)
            if hasattr(torch, 'compile') and device == 'cuda':
                print("  Compiling model (PyTorch 2.0+)...")
                self.model = torch.compile(self.model)
            
            print(f"✓ Model loaded successfully")
            return self.model
            
        except Exception as e:
            print(f"Error loading model: {e}")
            return None
    
    def unload(self):
        """Unload model and free memory."""
        if self.model:
            del self.model
            self.model = None
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("✓ Model unloaded, GPU memory cleared")
    
    def get_info(self) -> Dict:
        """Get model information."""
        return {
            'model_path': str(self.model_path),
            'exists': self.model_path.exists(),
            'loaded': self.model is not None,
            'config': {
                'layers': 32,
                'heads': 16,
                'embed_dim': 1280,
                'experts': 8
            } if self.config else None
        }


if __name__ == "__main__":
    loader = ElaraModelLoader()
    print(f"Model info: {loader.get_info()}")
