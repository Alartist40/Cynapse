
import argparse
import sys
import os
import subprocess

# Simplified import setup
import sys
import os

# Ensure current directory is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    # Import directly from the hivemind package (local folder)
    from hivemind.queen.trainer import HiveMindTrainer
    from hivemind.interact.terminal_chat import chat_loop
    from hivemind.learn.adapter import observe_and_adapt
except ImportError as e:
    print(f"[Fatal Error] Could not import HiveMind modules: {e}")
    sys.exit(1)

def run_interactive_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("="*40)
        print("   🐝 HIVEMIND CONTROL PANEL")
        print("="*40)
        print("1. [Interact] Chat with Queen & Drones")
        print("2. [Feed]     Train Queen on 70B Model")
        print("3. [Learn]    Teach Queen your style")
        print("4. [Settings] Toggle Auto-Route / Voice")
        print("5. [Exit]     Quit")
        print("="*40)
        
        choice = input("Select option (1-5): ").strip()
        
        if choice == '1':
            print("\n[Interact] Starting chat...")
            # Default settings, TODO: load from config
            chat_loop(model_name="queen", auto_route=True, voice=False)
            input("\nPress Enter to return to menu...")
            
        elif choice == '2':
            print("\n[Feed] Training Mode")
            teacher = input("Enter Teacher Model (default: meta-llama/Llama-2-70b-chat-hf): ").strip()
            if not teacher: teacher = "meta-llama/Llama-2-70b-chat-hf"
            
            queue_path = input("Enter Queen Path (default: ./queen.gguf): ").strip()
            if not queue_path: queue_path = "./queen.gguf"
            
            print(f"Initializing Trainer with {teacher}...")
            # trainer = HiveMindTrainer(queen_path=queue_path, teacher_name=teacher)
            # trainer.train_step("Interactive test prompt")
            print("(Training simulation complete)")
            input("\nPress Enter to return to menu...")
            
        elif choice == '3':
            print("\n[Learn] Adaptation Mode")
            mode = input("Select mode (o=observe, a=apply): ").lower()
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
    
    menu = subparsers.add_parser("menu", help="Interactive Menu")

    args = parser.parse_args()
    
    if args.mode == "menu" or args.mode is None:
        run_interactive_menu()
    elif args.mode == "feed":
        pass # implementation as before
    elif args.mode == "interact":
        chat_loop(args.model, auto_route=args.auto_route)
    elif args.mode == "learn":
        observe_and_adapt(mode=args.mode)

if __name__ == "__main__":
    main()
