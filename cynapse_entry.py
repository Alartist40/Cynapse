#!/usr/bin/env python3
"""
Cynapse - Ghost Shell Hub
Entry Point

Usage:
    python cynapse_entry.py --init          # Initialize system
    python cynapse_entry.py --tui           # Launch TUI
    python cynapse_entry.py --health        # Run diagnostics
    python cynapse_entry.py --cli           # CLI mode
    python cynapse_entry.py --test          # Run tests
"""
import sys
import os
import argparse
import subprocess

from pathlib import Path
from cynapse.core.hub import CynapseHub

def check_venv():
    """Ensure we are running in a virtual environment"""
    in_venv = (sys.prefix != sys.base_prefix)
    if not in_venv:
        print("\n⚠️  WARNING: You are running in the system Python environment!")
        print("   It is strongly recommended to use a virtual environment.")
        print("   To fix:")
        print("     source .venv/bin/activate  # Linux/Mac")
        print("     .venv\\Scripts\\activate     # Windows")
        response = input("\n   Continue anyway? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            sys.exit(1)

import importlib.util

def check_dependencies(requirements_file="requirements.txt"):
    """Check if required packages are installed"""
    if not Path(requirements_file).exists():
        return True
        
    with open(requirements_file) as f:
        required = [line.strip().split('>=')[0].split('==')[0].lower() 
                   for line in f if line.strip() and not line.startswith("#")]
    
    missing = []
    # Map pypi names to import names if different
    import_map = {
        "pyyaml": "yaml",
        "Pillow": "PIL",
        "scikit-learn": "sklearn",
        "protobuf": "google.protobuf"
    }

    for pkg in required:
        import_name = import_map.get(pkg, pkg)
        if not importlib.util.find_spec(import_name):
            missing.append(pkg)
            
    if missing:
        print(f"\n❌ Missing dependencies from {requirements_file}:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\n   To install:")
        print(f"   pip install -r {requirements_file}")
        return False
    return True

def init_system():
    """Initialize Cynapse infrastructure"""
    print("🏗️  Initializing Cynapse System...")
    print("=" * 50)
    
    # Create directories
    dirs = [
        "cynapse/data/storage",
        "cynapse/data/documents",
        "cynapse/data/models",
        "cynapse/data/temp",
        "workflows",
        "logs"
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {d}")
    
    # Check config files
    config_files = [
        "cynapse/data/config.ini",
        "hivemind.yaml"
    ]
    
    print("\n📄 Configuration files:")
    for cf in config_files:
        if Path(cf).exists():
            print(f"  ✓ {cf} (exists)")
        else:
            print(f"  ⚠️  {cf} (missing - run again if needed)")
    
    print("\n✅ Initialization complete!")
    print("\nNext steps:")
    print("  1. Install dependencies: pip install -r requirements-full.txt")
    print("  2. Run health check: python cynapse_entry.py --health")
    print("  3. Launch TUI: python cynapse_entry.py --tui")

def health_check():
    """Run system diagnostics"""
    print("🏥 Cynapse Health Check")
    print("=" * 50)
    
    checks = []
    
    # Check 1: Directories
    print("\n📁 Directory structure:")
    dirs_ok = True
    for d in ["cynapse/data", "workflows", "logs"]:
        if Path(d).exists():
            print(f"  ✓ {d}")
        else:
            print(f"  ❌ {d} (missing)")
            dirs_ok = False
    checks.append(("Directories", dirs_ok))
    
    # Check 2: Config files
    print("\n⚙️  Configuration:")
    config_ok = True
    for cf in ["cynapse/data/config.ini", "hivemind.yaml"]:
        if Path(cf).exists():
            print(f"  ✓ {cf}")
        else:
            print(f"  ❌ {cf} (missing)")
            config_ok = False
    checks.append(("Configuration", config_ok))
    
    # Check 3: Module imports
    print("\n🧩 Module imports:")
    modules_ok = True
    try:
        from cynapse.core.hub import CynapseHub
        print("  ✓ CynapseHub")
    except Exception as e:
        print(f"  ❌ CynapseHub: {e}")
        modules_ok = False
    
    try:
        from cynapse.core.hivemind import HiveMind
        print("  ✓ HiveMind")
    except Exception as e:
        print(f"  ❌ HiveMind: {e}")
        modules_ok = False
    
    try:
        from cynapse.tui.main import SynapticFortress
        print("  ✓ SynapticFortress")
    except Exception as e:
        print(f"  ❌ SynapticFortress: {e}")
        modules_ok = False
    
    checks.append(("Modules", modules_ok))
    
    # Check 4: Neuron discovery
    print("\n🧠 Neuron discovery:")
    try:
        hub = CynapseHub()
        neurons = hub.list_neurons()
        if neurons:
            print(f"  ✓ Found {len(neurons)} neurons: {', '.join(neurons[:5])}")
            if len(neurons) > 5:
                print(f"    ... and {len(neurons) - 5} more")
            checks.append(("Neurons", True))
        else:
            print("  ⚠️  No neurons discovered (run from project root)")
            checks.append(("Neurons", True))  # Not critical
    except Exception as e:
        print(f"  ❌ Discovery failed: {e}")
        checks.append(("Neurons", False))
    
    # Check 5: Dependencies
    print("\n📦 Core dependencies:")
    deps_ok = check_dependencies()
    checks.append(("Dependencies", deps_ok))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Health Check Summary:")
    all_ok = True
    for name, status in checks:
        symbol = "✅" if status else "❌"
        print(f"  {symbol} {name}")
        if not status:
            all_ok = False
    
    if all_ok:
        print("\n🎉 All systems operational!")
        print("   Ready to launch: python cynapse_entry.py --tui")
        return 0
    else:
        print("\n⚠️  Some issues detected. Run with --init if needed.")
        return 1

def main():
    check_venv()
    
    parser = argparse.ArgumentParser(
        description="Cynapse Security Hub - Ghost Shell System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --init          # Initialize system infrastructure
  %(prog)s --health        # Run diagnostics
  %(prog)s --tui           # Launch Synaptic Fortress TUI
  %(prog)s --cli           # Run in CLI mode
  %(prog)s --test          # Run self-tests
        """
    )
    
    parser.add_argument("--init", action="store_true", 
                       help="Initialize Cynapse infrastructure (create directories, configs)")
    parser.add_argument("--health", action="store_true",
                       help="Run system diagnostics and health check")
    parser.add_argument("--tui", action="store_true", 
                       help="Launch Synaptic Fortress TUI")
    parser.add_argument("--cli", action="store_true", 
                       help="Run in CLI mode")
    parser.add_argument("--test", action="store_true", 
                       help="Run self-tests")
    parser.add_argument("--train", action="store_true",
                       help="Train Elara on documents in training_docs/")
    parser.add_argument("--model-info", action="store_true",
                       help="Show Elara model information and configuration")
    parser.add_argument("--configure-model", action="store_true",
                       help="Auto-configure model for your hardware")
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")
    
    args = parser.parse_args()
    
    if args.init:
        init_system()
        return 0
    
    if args.health:
        return health_check()
    
    if args.tui:
        print("🚀 Launching Synaptic Fortress...")
        print("   Press 'h' for help, 'Q' to quit\n")
        try:
            from cynapse.tui.main import SynapticFortress
            app = SynapticFortress()
            app.run()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Error launching TUI: {e}")
            print("   Run --health to check system status")
            return 1
        return 0
    
    if args.cli:
        print("💻 CLI Mode (interactive)")
        hub = CynapseHub()
        neurons = hub.list_neurons()
        print(f"\nDiscovered {len(neurons)} neurons:")
        for n in neurons:
            print(f"  - {n}")
        return 0
    
    if args.test:
        print("🧪 Running self-tests...")
        # TODO: Add actual tests
        print("   Tests not yet implemented")
        return 0
    
    if args.model_info:
        print("🧠 Elara Model Information")
        print("=" * 50)
        try:
            from cynapse.core.model_manager import LocalModelManager
            manager = LocalModelManager()
            manager.check_model_exists()
            info = manager.get_model_info()
            print(f"\n  Path: {info['model_path']}")
            print(f"  Exists: {info['exists']}")
            if info['exists']:
                print(f"  Size: {info.get('size_mb', 0):.0f} MB")
            if info['config']:
                print(f"  Config: {info['config']}")
        except Exception as e:
            print(f"  Error: {e}")
        return 0
    
    if args.configure_model:
        print("⚙️  Configuring Model for Hardware")
        print("=" * 50)
        try:
            from cynapse.core.model_manager import LocalModelManager
            manager = LocalModelManager()
            config = manager.auto_configure_gpu()
            print(f"\n  Device: {config.device}")
            print(f"  GPU Layers: {config.gpu_layers}")
            print(f"  Precision: {config.precision}")
            print(f"  Flash Attention: {config.use_flash_attention}")
            print(f"\n✓ Configuration complete")
        except Exception as e:
            print(f"  Error: {e}")
        return 0
    
    if args.train:
        print("🎓 Training Elara on Documents")
        print("=" * 50)
        try:
            from cynapse.core.training import ElaraTrainer
            from pathlib import Path
            
            docs_path = Path('./cynapse/data/training_docs')
            if not docs_path.exists() or not any(docs_path.iterdir()):
                print(f"\n⚠️  No documents found in {docs_path}")
                print("   Add PDFs or text files to this directory first.")
                return 1
            
            trainer = ElaraTrainer()
            
            # Load documents
            print(f"\n📚 Loading documents from {docs_path}...")
            stats = trainer.load_documents(docs_path)
            print(f"   Loaded: {stats['num_documents']} docs, {stats['total_chunks']} chunks")
            
            # Initialize model
            print("\n🤖 Initializing model...")
            trainer.initialize_model()
            
            # Train
            print("\n🏋️ Starting training...")
            def progress_callback(epoch, loss, progress):
                bar_len = 30
                filled = int(bar_len * progress)
                bar = '█' * filled + '░' * (bar_len - filled)
                print(f"\r  [{bar}] {progress*100:.0f}% | Epoch {epoch} | Loss: {loss:.4f}", end='', flush=True)
            
            trainer.train(epochs=5, progress_callback=progress_callback)
            print()  # New line after progress bar
            
            # Ask to save checkpoint
            response = input("\n💾 Save checkpoint? (y/n): ")
            if response.lower() == 'y':
                checkpoint_path = trainer.save_checkpoint()
                print(f"✓ Checkpoint saved: {checkpoint_path}")
            
            print("\n✓ Training complete!")
            return 0
            
        except KeyboardInterrupt:
            print("\n\n👋 Training interrupted by user")
            return 0
        except Exception as e:
            print(f"\n❌ Training error: {e}")
            return 1
    
    # Default: show help
    parser.print_help()
    print("\n💡 Tip: Run --init first to set up the system")
    print("   Then use --train to train Elara on your documents")
    return 0

if __name__ == "__main__":
    sys.exit(main())
