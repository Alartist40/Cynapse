import sys
import os
try:
    import ollama
except ImportError:
    ollama = None

from cynapse.hivemind.drones.router import route_query

def chat_loop(model_name="queen", auto_route=False, voice=False):
    if ollama is None:
        print("[Error] 'ollama' python package is not installed. Please install it with: pip install ollama")
        return

    # Load registry to get model names if auto-route hits a drone
    import json
    registry_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "drones", "registry.json")
    registry = {}
    if os.path.exists(registry_path):
        with open(registry_path, "r") as f:
            registry = json.load(f)

    print(f"[HiveMind] Chat initialized. Model: {model_name}. Auto-route: {auto_route}. Voice: {voice}")
    print("Type 'exit' to quit.")

    while True:
        try:
            if voice:
                print("[Voice] Listening... (Press Enter to simulate voice input for now)")
                # Placeholder for Whisper integration
                user_input = input("> [Voice Simulated Input]: ")
            else:
                user_input = input("> ")
        except EOFError:
            break

        if user_input.lower() == "exit":
            break
            
        if not user_input.strip():
            continue
        
        target_model = model_name
        drone_id = None
        
        if auto_route:
            drone_id = route_query(user_input)
            if drone_id != "queen":
                # Look up actual model name from registry
                if drone_id in registry:
                    target_model = registry[drone_id]["model"]
                    print(f"[Router] Routing to specialist: {drone_id} ({target_model})")
                else:
                    print(f"[Router] Drone {drone_id} found but not in registry? Using default.")
                    drone_id = "queen"
            else:
                # keep default
                pass

        # Handle Queen logic vs Ollama logic
        # If target_model is "queen" or a path to GGUF, we need local inference (llama.cpp)
        # If target_model is an ollama model name (e.g. "codeqwen:7b"), we use ollama lib.
        
        is_ollama_model = ":" in target_model or drone_id is not None
        
        if is_ollama_model:
            try:
                stream = ollama.generate(model=target_model, prompt=user_input, stream=True)
                print(f"[{drone_id or target_model}]: ", end="", flush=True)
                for chunk in stream:
                    print(chunk['response'], end="", flush=True)
                print()
            except Exception as e:
                print(f"\n[Error] Ollama inference failed: {e}")
                print("Make sure Ollama is running and the model is pulled.")
        else:
            # Assume Queen (local GGUF)
            # For MVP, we can mock or use llama.cpp if available
            # We reuse the logic from trainer's load_queen if we want, or just print a placeholder
            print(f"[Queen]: (Local GGUF inference implementation would go here. Using mock response for infrastructure test.)")
            print(f"[Queen]: I heard: {user_input}")

