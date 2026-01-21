import numpy as np
import os
import json
from pathlib import Path

class HiveMemory:
    def __init__(self, db_path="memory.json"):
        # We use a simple JSON storage for the MVP to avoid heavy dependencies like FAISS crashing on some setups
        # Integration with FAISS can be uncommented if "faiss-cpu" is installed.
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_path)
        self.interactions = self.load()
    
    def load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                return json.load(f)
        return []
    
    def save(self):
        with open(self.db_path, 'w') as f:
            json.dump(self.interactions, f, indent=2)
    
    def add_interaction(self, query: str, response: str, user_correction: str = None):
        """Store query + correction."""
        entry = {
            "query": query,
            "response": response,
            "correction": user_correction
        }
        self.interactions.append(entry)
        self.save()
    
    def get_last_n(self, n=10):
        return self.interactions[-n:]

    def search_similar(self, query: str, k=3):
        # Simple text overlap search for MVP
        results = []
        query_words = set(query.lower().split())
        for i, entry in enumerate(self.interactions):
            entry_words = set(entry["query"].lower().split())
            overlap = len(query_words.intersection(entry_words))
            results.append((overlap, i))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [self.interactions[i] for score, i in results[:k] if score > 0]
