"""
Checkpoint Management for Elara Training
========================================

Manual checkpoint save/load system.
User controls when to save (on command).
"""

import json
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Lazy import for torch
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None


@dataclass
class CheckpointMetadata:
    """Metadata for a training checkpoint."""
    epoch: int
    step: int
    loss: float
    learning_rate: float
    timestamp: str
    total_tokens: int
    documents_trained: int
    training_duration_hours: float
    

class CheckpointManager:
    """
    Manages model checkpoints with manual save control.
    
    Features:
    - Manual save on user command
    - Resume from any checkpoint
    - Keep only last N checkpoints (configurable)
    - Metadata tracking
    """
    
    def __init__(self, checkpoint_dir: Path, max_checkpoints: int = 5):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to save checkpoints
            max_checkpoints: Maximum number of checkpoints to keep
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        
    def save_checkpoint(
        self,
        model: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        metadata: CheckpointMetadata,
        name: Optional[str] = None
    ) -> Path:
        """
        Save a checkpoint manually.
        
        Args:
            model: The model to save
            optimizer: The optimizer state
            metadata: Training metadata
            name: Optional custom name, otherwise auto-generated
            
        Returns:
            Path to saved checkpoint
        """
        if name is None:
            name = f"checkpoint_epoch{metadata.epoch}_step{metadata.step}.pt"
            
        checkpoint_path = self.checkpoint_dir / name
        
        checkpoint = {
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'metadata': asdict(metadata),
            'pytorch_version': torch.__version__,
        }
        
        torch.save(checkpoint, checkpoint_path)
        print(f"✓ Checkpoint saved: {checkpoint_path}")
        
        # Clean up old checkpoints
        self._cleanup_old_checkpoints()
        
        return checkpoint_path
    
    def load_checkpoint(
        self,
        checkpoint_path: Path,
        model: torch.nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
        device: str = 'cpu'
    ) -> CheckpointMetadata:
        """
        Load a checkpoint and restore model/optimizer state.
        
        Args:
            checkpoint_path: Path to checkpoint file
            model: Model to restore state into
            optimizer: Optional optimizer to restore
            device: Device to load checkpoint to
            
        Returns:
            CheckpointMetadata with training state
        """
        checkpoint_path = Path(checkpoint_path)
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
            
        # Load checkpoint
        checkpoint = torch.load(checkpoint_path, map_location=device)
        
        # Restore model
        model.load_state_dict(checkpoint['model_state_dict'])
        
        # Restore optimizer if provided
        if optimizer is not None and 'optimizer_state_dict' in checkpoint:
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            
        # Extract metadata
        metadata_dict = checkpoint.get('metadata', {})
        metadata = CheckpointMetadata(**metadata_dict)
        
        print(f"✓ Checkpoint loaded: {checkpoint_path}")
        print(f"  Epoch: {metadata.epoch}, Step: {metadata.step}, Loss: {metadata.loss:.4f}")
        
        return metadata
    
    def list_checkpoints(self) -> list:
        """List all available checkpoints with metadata."""
        checkpoints = []
        
        for checkpoint_file in self.checkpoint_dir.glob("*.pt"):
            try:
                # Load just the metadata
                checkpoint = torch.load(checkpoint_file, map_location='cpu')
                metadata_dict = checkpoint.get('metadata', {})
                metadata = CheckpointMetadata(**metadata_dict)
                
                checkpoints.append({
                    'path': checkpoint_file,
                    'name': checkpoint_file.name,
                    'epoch': metadata.epoch,
                    'step': metadata.step,
                    'loss': metadata.loss,
                    'timestamp': metadata.timestamp,
                    'size_mb': checkpoint_file.stat().st_size / (1024 * 1024)
                })
            except Exception as e:
                print(f"Warning: Could not read checkpoint {checkpoint_file}: {e}")
                
        # Sort by timestamp (newest first)
        checkpoints.sort(key=lambda x: x['timestamp'], reverse=True)
        return checkpoints
    
    def get_latest_checkpoint(self) -> Optional[Path]:
        """Get the path to the most recent checkpoint."""
        checkpoints = self.list_checkpoints()
        if checkpoints:
            return checkpoints[0]['path']
        return None
    
    def _cleanup_old_checkpoints(self):
        """Remove old checkpoints, keeping only the most recent N."""
        checkpoints = self.list_checkpoints()
        
        if len(checkpoints) > self.max_checkpoints:
            # Remove oldest checkpoints
            to_remove = checkpoints[self.max_checkpoints:]
            for ckpt in to_remove:
                try:
                    ckpt['path'].unlink()
                    print(f"  Cleaned up old checkpoint: {ckpt['name']}")
                except Exception as e:
                    print(f"Warning: Could not remove {ckpt['name']}: {e}")
    
    def export_for_inference(self, checkpoint_path: Path, output_path: Path):
        """
        Export a checkpoint to a smaller file for inference only.
        
        Removes optimizer state to reduce file size.
        """
        checkpoint = torch.load(checkpoint_path, map_location='cpu')
        
        # Create inference-only checkpoint
        inference_checkpoint = {
            'model_state_dict': checkpoint['model_state_dict'],
            'metadata': checkpoint.get('metadata', {})
        }
        
        torch.save(inference_checkpoint, output_path)
        
        original_size = checkpoint_path.stat().st_size / (1024 * 1024)
        new_size = output_path.stat().st_size / (1024 * 1024)
        
        print(f"✓ Exported for inference: {output_path}")
        print(f"  Size reduced: {original_size:.1f}MB → {new_size:.1f}MB")
        
        return output_path


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Checkpoint Manager CLI")
        print("\nUsage:")
        print("  python checkpoint.py list <checkpoint_dir>")
        print("  python checkpoint.py info <checkpoint_path>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list" and len(sys.argv) >= 3:
        checkpoint_dir = Path(sys.argv[2])
        manager = CheckpointManager(checkpoint_dir)
        
        checkpoints = manager.list_checkpoints()
        
        if not checkpoints:
            print(f"No checkpoints found in {checkpoint_dir}")
        else:
            print(f"\nCheckpoints in {checkpoint_dir}:")
            print("-" * 80)
            for i, ckpt in enumerate(checkpoints, 1):
                print(f"{i}. {ckpt['name']}")
                print(f"   Epoch: {ckpt['epoch']}, Step: {ckpt['step']}, Loss: {ckpt['loss']:.4f}")
                print(f"   Time: {ckpt['timestamp']}, Size: {ckpt['size_mb']:.1f}MB")
                print()
    
    elif command == "info" and len(sys.argv) >= 3:
        checkpoint_path = Path(sys.argv[2])
        
        try:
            checkpoint = torch.load(checkpoint_path, map_location='cpu')
            metadata = checkpoint.get('metadata', {})
            
            print(f"\nCheckpoint: {checkpoint_path.name}")
            print("-" * 80)
            print(f"Epoch: {metadata.get('epoch', 'N/A')}")
            print(f"Step: {metadata.get('step', 'N/A')}")
            print(f"Loss: {metadata.get('loss', 'N/A')}")
            print(f"Learning Rate: {metadata.get('learning_rate', 'N/A')}")
            print(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
            print(f"Total Tokens: {metadata.get('total_tokens', 'N/A')}")
            print(f"Documents Trained: {metadata.get('documents_trained', 'N/A')}")
            print(f"Duration: {metadata.get('training_duration_hours', 'N/A')} hours")
            print(f"PyTorch Version: {checkpoint.get('pytorch_version', 'N/A')}")
        except Exception as e:
            print(f"Error reading checkpoint: {e}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
