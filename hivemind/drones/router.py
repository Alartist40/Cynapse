import json
import os

def route_query(query: str):
    """Return drone ID or 'queen' if no match."""
    registry_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")
    try:
        with open(registry_path, "r") as f:
            registry = json.load(f)
    except FileNotFoundError:
        print(f"[Router] Warning: registry.json not found at {registry_path}. Defaulting to queen.")
        return "queen"
    
    query_lower = query.lower()
    
    for drone_id, config in registry.items():
        if any(kw in query_lower for kw in config.get("trigger_keywords", [])):
            return drone_id
    
    return "queen"  # Default fallback
