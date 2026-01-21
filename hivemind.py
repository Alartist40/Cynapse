import argparse
import sys
import os

# Ensure we can import modules from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    parser = argparse.ArgumentParser(prog="hivemind", description="HiveMind: Your Personal AI Ecosystem")
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Mode of operation")
    
    # Mode 1: Feed (Train queen on 70B knowledge)
    feed = subparsers.add_parser("feed", help="Train queen on 70B knowledge")
    feed.add_argument("--teacher", required=True, help="70B model name (e.g., meta-llama/Llama-2-70b-chat-hf)")
    feed.add_argument("--queen", default="./queen.gguf", help="Path to your 3B queen model")
    feed.add_argument("--dataset", required=False, help="JSONL with prompts (optional, interactive if not provided)")
    
    # Mode 2: Interact (Chat with queen/drones)
    interact = subparsers.add_parser("interact", help="Chat with queen/drones")
    interact.add_argument("--model", default="queen", help="Model to chat with: 'queen' or drone name")
    interact.add_argument("--auto-route", action="store_true", help="Automatically route queries to specialists")
    interact.add_argument("--voice", action="store_true", help="Use Whisper for voice input")
    
    # Mode 3: Learn (Queen adapts to your style)
    learn = subparsers.add_parser("learn", help="Queen adapts to your style")
    learn.add_argument("--mode", choices=["observe", "apply"], required=True, help="observe: record interactions, apply: fine-tune persona")
    
    args = parser.parse_args()
    
    print(f"[HiveMind] Mode: {args.mode}")
    
    if args.mode == "feed":
        from cynapse.hivemind.queen.trainer import HiveMindTrainer
        print(f"[HiveMind] Initializing Trainer with Teacher: {args.teacher}")
        # trainer = HiveMindTrainer(queen=args.queen, teacher=args.teacher)
        # if args.dataset:
        #     trainer.train_on_dataset(args.dataset)
        # else:
        #     print("Interactive training mode not yet implemented for batch.")
        
    elif args.mode == "interact":
        from cynapse.hivemind.interact.terminal_chat import chat_loop
        chat_loop(args.model, auto_route=args.auto_route, voice=args.voice)
        
    elif args.mode == "learn":
        from cynapse.hivemind.learn.adapter import observe_and_adapt
        observe_and_adapt(mode=args.mode)

if __name__ == "__main__":
    main()
