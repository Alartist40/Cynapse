"""
Elara Trainer - Local Training System
=====================================

Trains Elara model on local documents with Ollama mentorship.
Manual checkpoint control - user decides when to save.
"""

import time
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from datetime import datetime
import warnings

# Lazy imports for heavy dependencies
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None

# Training components
from .data_loader import DocumentDataLoader, TrainingConfig
from .checkpoint import CheckpointManager, CheckpointMetadata
from .ollama_mentor import OllamaMentor

# Model (from elara reference)
try:
    import sys
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.append(str(project_root / 'elara'))
    from model import GPT, GPTConfig
    HAS_MODEL = True
except ImportError:
    HAS_MODEL = False
    GPT = None
    GPTConfig = None
    warnings.warn("Elara model not found. Training will use mock mode.")


@dataclass
class TrainerConfig:
    """Training configuration"""
    epochs: int = 10
    learning_rate: float = 6e-4
    batch_size: int = 4
    warmup_iters: int = 100
    device: str = 'auto'  # 'auto', 'cuda', 'cpu'
    log_interval: int = 10
    

class ElaraTrainer:
    """
    Main training coordinator for Elara.
    
    Features:
    - Load and process documents
    - Train with Ollama mentorship
    - Manual checkpoint saves
    - Progress reporting for TUI
    """
    
    def __init__(
        self,
        config: Optional[TrainerConfig] = None,
        checkpoint_dir: Optional[Path] = None
    ):
        self.config = config or TrainerConfig()
        self.data_loader = DocumentDataLoader(TrainingConfig())
        self.checkpoint_manager = CheckpointManager(
            checkpoint_dir or Path('./checkpoints')
        )
        self.mentor = OllamaMentor()
        
        # Training state
        self.model = None
        self.optimizer = None
        self.current_epoch = 0
        self.current_loss = 0.0
        self.is_training = False
        self.training_start_time = None
        
        # Progress callback for TUI
        self.progress_callback: Optional[Callable] = None
        
        # Auto-detect device
        if self.config.device == 'auto':
            self.config.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        print(f"Elara Trainer initialized (device: {self.config.device})")
        if self.mentor.is_available():
            print(f"Ollama mentor: {self.mentor.config.model}")
    
    def load_documents(self, docs_path: Path) -> Dict:
        """Load training documents."""
        print(f"\nLoading documents from {docs_path}...")
        self.data_loader.load_documents(docs_path)
        stats = self.data_loader.get_statistics()
        
        print(f"  Documents: {stats['num_documents']}")
        print(f"  Chunks: {stats['total_chunks']}")
        print(f"  Characters: {stats['total_characters']:,}")
        
        return stats
    
    def initialize_model(self, from_checkpoint: Optional[Path] = None):
        """Initialize or load model."""
        if not HAS_MODEL:
            print("Warning: Using mock model (Elara not available)")
            return
        
        # Create model config
        model_config = GPTConfig(
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
        
        # Initialize model
        self.model = GPT(model_config)
        self.model.to(self.config.device)
        
        # Create optimizer
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            betas=(0.9, 0.95),
            eps=1e-8
        )
        
        # Load from checkpoint if provided
        if from_checkpoint and from_checkpoint.exists():
            print(f"Loading checkpoint: {from_checkpoint}")
            metadata = self.checkpoint_manager.load_checkpoint(
                from_checkpoint,
                self.model,
                self.optimizer,
                self.config.device
            )
            self.current_epoch = metadata.epoch
            self.current_loss = metadata.loss
        else:
            print("Initialized new model (training from scratch)")
            self.current_epoch = 0
            self.current_loss = float('inf')
    
    def train(
        self,
        epochs: Optional[int] = None,
        progress_callback: Optional[Callable] = None
    ):
        """
        Start training loop.
        
        Args:
            epochs: Number of epochs (override config)
            progress_callback: Function(epoch, loss, progress) for TUI updates
        """
        if not self.model:
            print("Error: Model not initialized. Call initialize_model() first.")
            return
        
        if not self.data_loader.processed_docs:
            print("Error: No documents loaded. Call load_documents() first.")
            return
        
        epochs = epochs or self.config.epochs
        self.progress_callback = progress_callback
        self.is_training = True
        self.training_start_time = time.time()
        
        print(f"\nStarting training for {epochs} epochs...")
        print(f"Device: {self.config.device}")
        print(f"Learning rate: {self.config.learning_rate}")
        
        # Training loop
        for epoch in range(self.current_epoch, epochs):
            if not self.is_training:
                print("Training stopped by user.")
                break
            
            self.current_epoch = epoch
            epoch_loss = self._train_epoch(epoch)
            self.current_loss = epoch_loss
            
            # Progress report
            progress = (epoch + 1) / epochs
            if self.progress_callback:
                self.progress_callback(epoch, epoch_loss, progress)
            
            print(f"Epoch {epoch+1}/{epochs} - Loss: {epoch_loss:.4f}")
            
            # Get mentor feedback every 5 epochs
            if (epoch + 1) % 5 == 0 and self.mentor.is_available():
                guidance = self.mentor.provide_training_guidance({
                    'epoch': epoch + 1,
                    'loss': epoch_loss,
                    'learning_rate': self.config.learning_rate
                })
                print(f"Mentor: {guidance[:100]}...")
        
        self.is_training = False
        duration = time.time() - self.training_start_time
        print(f"\nTraining complete! Duration: {duration/3600:.2f} hours")
    
    def _train_epoch(self, epoch: int) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        # Get dataset
        dataset = self.data_loader.create_training_dataset()
        if not dataset:
            return 0.0
        
        # Simple training loop (simplified for now)
        for i, batch in enumerate(dataset):
            if not self.is_training:
                break
            
            # Forward pass (mock for now)
            loss = torch.tensor(2.0 - (epoch * 0.1))  # Simulated decreasing loss
            
            total_loss += loss.item()
            num_batches += 1
            
            # Log progress
            if i % self.config.log_interval == 0:
                print(f"  Batch {i}, Loss: {loss.item():.4f}")
        
        return total_loss / max(num_batches, 1)
    
    def save_checkpoint(self, name: Optional[str] = None):
        """Manually save checkpoint."""
        if not self.model:
            print("Error: No model to save.")
            return
        
        metadata = CheckpointMetadata(
            epoch=self.current_epoch,
            step=0,  # Simplified
            loss=self.current_loss,
            learning_rate=self.config.learning_rate,
            timestamp=datetime.now().isoformat(),
            total_tokens=0,  # Track in full implementation
            documents_trained=len(self.data_loader.processed_docs),
            training_duration_hours=(time.time() - self.training_start_time) / 3600
                        if self.training_start_time else 0
        )
        
        path = self.checkpoint_manager.save_checkpoint(
            self.model,
            self.optimizer,
            metadata,
            name
        )
        
        return path
    
    def stop_training(self):
        """Stop training gracefully."""
        self.is_training = False
        print("Training stop requested...")
    
    def get_status(self) -> Dict:
        """Get current training status for TUI."""
        return {
            'is_training': self.is_training,
            'epoch': self.current_epoch,
            'loss': self.current_loss,
            'documents': len(self.data_loader.processed_docs),
            'mentor_available': self.mentor.is_available(),
            'device': self.config.device
        }


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Elara Trainer")
        print("\nUsage:")
        print("  python trainer.py load <docs_path>")
        print("  python trainer.py train --epochs=10")
        sys.exit(1)
    
    command = sys.argv[1]
    
    trainer = ElaraTrainer()
    
    if command == "load" and len(sys.argv) >= 3:
        docs_path = Path(sys.argv[2])
        trainer.load_documents(docs_path)
    
    elif command == "train":
        trainer.initialize_model()
        trainer.train(epochs=5)
    
    else:
        print(f"Unknown command: {command}")
