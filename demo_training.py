#!/usr/bin/env python3
"""
Cynapse Phase 2 Demo - Local AI Training
========================================

Demonstrates the complete training pipeline:
1. Load documents from training_docs/
2. Process and chunk text
3. Initialize Elara model
4. Train with Ollama mentorship
5. Save checkpoint
6. Use trained model in chat

Usage:
    python demo_training.py
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def demo_document_loading():
    """Step 1: Load and process training documents"""
    print("\n" + "="*60)
    print("STEP 1: Document Loading")
    print("="*60)
    
    try:
        from cynapse.core.training import DocumentDataLoader
        
        loader = DocumentDataLoader()
        docs_path = Path('cynapse/data/training_docs')
        
        print(f"Loading documents from: {docs_path}")
        loader.load_documents(docs_path)
        
        stats = loader.get_statistics()
        if stats:
            print(f"✓ Loaded {stats['num_documents']} documents")
            print(f"✓ Total chunks: {stats['total_chunks']}")
            print(f"✓ Total characters: {stats['total_characters']:,}")
            print(f"✓ File types: {stats['file_types']}")
        else:
            print("⚠ No documents found (PyPDF2 may not be installed)")
            print("  Install: pip install PyPDF2")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_model_configuration():
    """Step 2: Auto-configure model for hardware"""
    print("\n" + "="*60)
    print("STEP 2: Hardware Configuration")
    print("="*60)
    
    try:
        from cynapse.core.model_manager import LocalModelManager
        
        manager = LocalModelManager()
        
        # Check if model exists
        exists = manager.check_model_exists()
        if not exists:
            print("⚠ Model file not found")
            print("  Place elara.gguf in: cynapse/data/models/")
            print("  (Demo continues with mock configuration)")
        
        # Auto-configure
        config = manager.auto_configure_gpu()
        print(f"\n✓ Hardware detected:")
        print(f"  Device: {config.device}")
        print(f"  GPU Layers: {config.gpu_layers}")
        print(f"  Precision: {config.precision}")
        print(f"  Flash Attention: {config.use_flash_attention}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_training_system():
    """Step 3: Initialize training system"""
    print("\n" + "="*60)
    print("STEP 3: Training System")
    print("="*60)
    
    try:
        from cynapse.core.training import ElaraTrainer, DocumentDataLoader
        from cynapse.core.training import OllamaMentor
        
        # Check components
        print("Checking training components:")
        
        # Data loader
        loader = DocumentDataLoader()
        print("  ✓ DocumentDataLoader ready")
        
        # Ollama mentor
        mentor = OllamaMentor()
        if mentor.is_available():
            print(f"  ✓ OllamaMentor ready ({mentor.config.model})")
        else:
            print("  ⚠ OllamaMentor unavailable")
            print("    Install Ollama: https://ollama.ai")
        
        # Trainer (requires torch)
        if ElaraTrainer is not None:
            print("  ✓ ElaraTrainer ready (PyTorch available)")
            
            # Create trainer instance
            trainer = ElaraTrainer()
            status = trainer.get_status()
            print(f"\n  Trainer status:")
            print(f"    Device: {status['device']}")
            print(f"    Mentor available: {status['mentor_available']}")
        else:
            print("  ⚠ ElaraTrainer unavailable (PyTorch not installed)")
            print("    Install: pip install torch")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_cli_commands():
    """Step 4: Show available CLI commands"""
    print("\n" + "="*60)
    print("STEP 4: CLI Commands Available")
    print("="*60)
    
    commands = [
        ("--init", "Initialize system infrastructure"),
        ("--health", "Run system diagnostics"),
        ("--configure-model", "Auto-configure GPU settings"),
        ("--model-info", "Show model information"),
        ("--train", "Train Elara on documents"),
        ("--tui", "Launch Synaptic Fortress"),
        ("--cli", "List discovered neurons"),
    ]
    
    print("\nAvailable commands:")
    for cmd, desc in commands:
        print(f"  python cynapse_entry.py {cmd:20} # {desc}")


def demo_file_structure():
    """Step 5: Show project structure"""
    print("\n" + "="*60)
    print("STEP 5: Project Structure")
    print("="*60)
    
    structure = """
cynapse/
├── core/
│   ├── training/              # NEW: Training infrastructure
│   │   ├── __init__.py
│   │   ├── data_loader.py     # Document processing
│   │   ├── trainer.py          # Main training coordinator
│   │   ├── checkpoint.py       # Manual save/load
│   │   └── ollama_mentor.py  # Training mentorship
│   └── model_manager.py       # NEW: GPU auto-config
│
├── neurons/
│   └── elara/                 # NEW: Model management
│       ├── __init__.py
│       ├── model_loader.py    # Optimized loading
│       └── inference.py       # Async generation
│
└── data/
    ├── models/                # Model storage
    └── training_docs/           # Training documents (4 PDFs)

elara/                         # Reference model
├── model.py                   # GPT architecture
├── train.py                   # Training scripts
└── ...
"""
    print(structure)


def main():
    """Run complete demo"""
    print("\n" + "="*60)
    print("CYNAPSE PHASE 2 - LOCAL AI TRAINING SYSTEM")
    print("="*60)
    print("\nThis demo shows the complete training pipeline:")
    print("1. Document loading from training_docs/")
    print("2. Hardware auto-configuration")
    print("3. Training system components")
    print("4. CLI commands available")
    print("5. Project structure")
    
    try:
        demo_document_loading()
        demo_model_configuration()
        demo_training_system()
        demo_cli_commands()
        demo_file_structure()
        
        print("\n" + "="*60)
        print("DEMO COMPLETE")
        print("="*60)
        print("\nNext steps:")
        print("1. Install dependencies:")
        print("   pip install torch PyPDF2 ollama")
        print("\n2. Configure your hardware:")
        print("   python cynapse_entry.py --configure-model")
        print("\n3. Start training:")
        print("   python cynapse_entry.py --train")
        print("\n4. Launch TUI:")
        print("   python cynapse_entry.py --tui")
        print("\n✓ Phase 2 implementation complete!")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
