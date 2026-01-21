#!/usr/bin/env python3
"""
HiveMind CLI - Your Personal AI Ecosystem
Provides interactive menu and CLI access to Cynapse HiveMind features.
"""

import argparse
import sys
import os

# Setup import paths
current_dir = os.path.dirname(os.path.abspath(__file__))  # .../cynapse
parent_dir = os.path.dirname(current_dir)  # .../ (project root)

# Add project root so we can import 'cynapse'
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Add current dir so we can import 'hivemind' modules if running as script inside cynapse
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


def _lazy_import_chat_loop():
    """Lazy import for chat_loop to avoid loading heavy dependencies at startup."""
    try:
        from hivemind.interact.terminal_chat import chat_loop
        return chat_loop
    except ImportError:
        try:
            from cynapse.hivemind.interact.terminal_chat import chat_loop
            return chat_loop
        except ImportError as e:
            print(f"[Error] Could not import chat module: {e}")
            print("Make sure you have the required dependencies installed.")
            return None


def _lazy_import_trainer():
    """Lazy import for HiveMindTrainer to avoid loading torch at startup."""
    try:
        from hivemind.queen.trainer import HiveMindTrainer
        return HiveMindTrainer
    except ImportError:
        try:
            from cynapse.hivemind.queen.trainer import HiveMindTrainer
            return HiveMindTrainer
        except ImportError as e:
            print(f"[Error] Could not import trainer module: {e}")
            print("Training requires: pip install torch transformers")
            return None


def _lazy_import_adapter():
    """Lazy import for observe_and_adapt to avoid loading heavy dependencies at startup."""
    try:
        from hivemind.learn.adapter import observe_and_adapt
        return observe_and_adapt
    except ImportError:
        try:
            from cynapse.hivemind.learn.adapter import observe_and_adapt
            return observe_and_adapt
        except ImportError as e:
            print(f"[Error] Could not import adapter module: {e}")
            print("Learning requires: pip install peft transformers torch")
            return None


def run_interactive_menu():
    """Run the interactive HiveMind control panel."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 40)
        print("   🐝 HIVEMIND CONTROL PANEL")
        print("=" * 40)
        print("1. [Interact] Chat with Queen & Drones")
        print("2. [Feed]     Train Queen on 70B Model")
        print("3. [Learn]    Teach Queen your style")
        print("4. [Settings] Toggle Auto-Route / Voice")
        print("5. [Exit]     Quit")
        print("=" * 40)

        choice = input("Select option (1-5): ").strip()

        if choice == '1':
            print("\n[Interact] Starting chat...")
            chat_loop = _lazy_import_chat_loop()
            if chat_loop:
                chat_loop(model_name="queen", auto_route=True, voice=False)
            input("\nPress Enter to return to menu...")

        elif choice == '2':
            print("\n[Feed] Training Mode")
            teacher = input("Enter Teacher Model (default: meta-llama/Llama-2-70b-chat-hf): ").strip()
            if not teacher:
                teacher = "meta-llama/Llama-2-70b-chat-hf"

            queue_path = input("Enter Queen Path (default: ./queen.gguf): ").strip()
            if not queue_path:
                queue_path = "./queen.gguf"

            print(f"Initializing Trainer with {teacher}...")
            HiveMindTrainer = _lazy_import_trainer()
            if HiveMindTrainer:
                try:
                    trainer = HiveMindTrainer(queen_path=queue_path, teacher_name=teacher)
                    trainer.train_step("Interactive test prompt")
                except Exception as e:
                    print(f"[Error] Training failed: {e}")
            else:
                print("(Training simulation - dependencies not available)")
            input("\nPress Enter to return to menu...")

        elif choice == '3':
            print("\n[Learn] Adaptation Mode")
            mode = input("Select mode (o=observe, a=apply): ").lower()
            observe_and_adapt = _lazy_import_adapter()
            if observe_and_adapt:
                if mode == 'o':
                    observe_and_adapt(mode="observe")
                elif mode == 'a':
                    observe_and_adapt(mode="apply")
                else:
                    print("Invalid mode.")
            input("\nPress Enter to return to menu...")

        elif choice == '4':
            print("\n[Settings] Not yet implemented in MVP Config")
            input("\nPress Enter to return to menu...")

        elif choice == '5':
            print("Goodbye!")
            break
        else:
            input("Invalid selection. Press Enter...")


def main():
    parser = argparse.ArgumentParser(prog="hivemind", description="HiveMind: Your Personal AI Ecosystem")
    subparsers = parser.add_subparsers(dest="mode", help="Mode of operation")

    # Modes
    feed = subparsers.add_parser("feed", help="Train queen")
    feed.add_argument("--teacher", required=True)
    feed.add_argument("--queen", default="./queen.gguf")

    interact = subparsers.add_parser("interact", help="Chat")
    interact.add_argument("--model", default="queen")
    interact.add_argument("--auto-route", action="store_true")

    learn = subparsers.add_parser("learn", help="Adapt")
    learn.add_argument("--mode", choices=["observe", "apply"], required=True)

    subparsers.add_parser("menu", help="Interactive Menu")

    args = parser.parse_args()

    if args.mode == "menu" or args.mode is None:
        run_interactive_menu()
    elif args.mode == "feed":
        HiveMindTrainer = _lazy_import_trainer()
        if HiveMindTrainer:
            trainer = HiveMindTrainer(queen_path=args.queen, teacher_name=args.teacher)
            print("[Feed] Trainer initialized. Use train_step() or train_on_dataset().")
    elif args.mode == "interact":
        chat_loop = _lazy_import_chat_loop()
        if chat_loop:
            chat_loop(args.model, auto_route=args.auto_route)
    elif args.mode == "learn":
        observe_and_adapt = _lazy_import_adapter()
        if observe_and_adapt:
            observe_and_adapt(mode=args.mode)


if __name__ == "__main__":
    main()
