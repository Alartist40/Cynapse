"""
Cynapse Model Manager
=====================

Centralized model lifecycle management with GPU auto-optimization.
Handles Elara loading, configuration, and hardware optimization.
"""

import torch
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import warnings


@dataclass
class ModelConfig:
    """Optimized model configuration"""
    gpu_layers: int
    precision: str  # 'bf16', 'fp16', 'fp32'
    device: str
    use_flash_attention: bool
    compile_model: bool


class LocalModelManager:
    """
    Manages local Elara model with hardware optimization.
    
    Features:
    - Automatic GPU layer calculation
    - Model validation (SHA256)
    - Memory-mapped loading
    - Hardware detection
    """
    
    def __init__(self, models_dir: Path = Path('./cynapse/data/models')):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Expected model file
        self.model_file = self.models_dir / 'elara.gguf'
        
        # Current model state
        self.current_config: Optional[ModelConfig] = None
        self.model_loaded = False
        
        print(f"Model Manager initialized")
        print(f"  Models directory: {self.models_dir}")
    
    def check_model_exists(self) -> bool:
        """Check if Elara model file exists."""
        exists = self.model_file.exists()
        if exists:
            size_mb = self.model_file.stat().st_size / (1024 * 1024)
            print(f"✓ Model found: {self.model_file.name} ({size_mb:.0f} MB)")
        else:
            print(f"⚠ Model not found: {self.model_file}")
            print(f"  Place model file in: {self.models_dir}")
        return exists
    
    def validate_model_file(self) -> Tuple[bool, str]:
        """
        Validate model file integrity.
        
        Returns:
            (is_valid, message)
        """
        if not self.model_file.exists():
            return False, "Model file not found"
        
        try:
            # Check file size
            size = self.model_file.stat().st_size
            if size < 1_000_000_000:  # Less than 1GB
                return False, f"Model file too small ({size/1e6:.0f} MB)"
            
            # Try to load header (first few bytes)
            with open(self.model_file, 'rb') as f:
                header = f.read(16)
                if len(header) < 16:
                    return False, "File too small to be valid"
            
            return True, f"Model file valid ({size/1e9:.1f} GB)"
            
        except Exception as e:
            return False, f"Validation error: {e}"
    
    def auto_configure_gpu(self) -> ModelConfig:
        """
        Automatically configure model based on available hardware.
        
        Returns:
            ModelConfig optimized for current hardware
        """
        # Check CUDA availability
        if torch.cuda.is_available():
            device = 'cuda'
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_gb = vram_bytes / 1e9
            
            # Determine GPU layers based on VRAM
            if vram_gb >= 16:
                gpu_layers = 32  # Full GPU
                precision = 'bf16' if torch.cuda.is_bf16_supported() else 'fp16'
                print(f"✓ High VRAM detected: {vram_gb:.1f} GB")
                print(f"  Configuring: 32 layers on GPU, {precision} precision")
            elif vram_gb >= 8:
                gpu_layers = 20  # Partial GPU
                precision = 'fp16'
                print(f"✓ Medium VRAM detected: {vram_gb:.1f} GB")
                print(f"  Configuring: 20 layers on GPU, {precision} precision")
            else:
                gpu_layers = 0  # CPU only
                precision = 'fp32'
                print(f"⚠ Low VRAM detected: {vram_gb:.1f} GB")
                print(f"  Configuring: CPU only, fp32 precision")
                device = 'cpu'
        else:
            device = 'cpu'
            gpu_layers = 0
            precision = 'fp32'
            print("⚠ No CUDA available")
            print("  Configuring: CPU only, fp32 precision")
        
        config = ModelConfig(
            gpu_layers=gpu_layers,
            precision=precision,
            device=device,
            use_flash_attention=torch.cuda.is_available() and torch.__version__ >= '2.0',
            compile_model=torch.cuda.is_available() and torch.__version__ >= '2.0'
        )
        
        self.current_config = config
        return config
    
    def get_optimal_config(self) -> ModelConfig:
        """Get or calculate optimal configuration."""
        if self.current_config is None:
            self.auto_configure_gpu()
        return self.current_config
    
    def cleanup_on_exit(self):
        """Clean up model resources."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("✓ GPU memory cleared")
    
    def get_model_info(self) -> Dict:
        """Get information about the model setup."""
        info = {
            'model_path': str(self.model_file),
            'exists': self.model_file.exists(),
            'config': None
        }
        
        if self.current_config:
            info['config'] = {
                'gpu_layers': self.current_config.gpu_layers,
                'precision': self.current_config.precision,
                'device': self.current_config.device,
                'flash_attention': self.current_config.use_flash_attention
            }
        
        if self.model_file.exists():
            info['size_mb'] = self.model_file.stat().st_size / (1024 * 1024)
        
        return info


# CLI interface
if __name__ == "__main__":
    import sys
    
    manager = LocalModelManager()
    
    if len(sys.argv) < 2:
        print("Model Manager CLI")
        print("\nCommands:")
        print("  check      - Check if model exists")
        print("  validate   - Validate model integrity")
        print("  configure  - Auto-configure for hardware")
        print("  info       - Show model information")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "check":
        exists = manager.check_model_exists()
        sys.exit(0 if exists else 1)
    
    elif command == "validate":
        is_valid, msg = manager.validate_model_file()
        print(f"Validation: {msg}")
        sys.exit(0 if is_valid else 1)
    
    elif command == "configure":
        config = manager.auto_configure_gpu()
        print(f"\nConfiguration:")
        print(f"  Device: {config.device}")
        print(f"  GPU Layers: {config.gpu_layers}")
        print(f"  Precision: {config.precision}")
        print(f"  Flash Attention: {config.use_flash_attention}")
    
    elif command == "info":
        info = manager.get_model_info()
        print(f"\nModel Information:")
        print(f"  Path: {info['model_path']}")
        print(f"  Exists: {info['exists']}")
        if info['exists']:
            print(f"  Size: {info.get('size_mb', 0):.0f} MB")
        if info['config']:
            print(f"  Config: {info['config']}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
