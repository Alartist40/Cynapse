"""
Ollama Training Mentor for Elara
=================================

Uses local Ollama models to assist with Elara training.
Provides feedback, generates training pairs, and critiques outputs.
All operations are offline - no cloud dependencies.
"""

import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import warnings

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    warnings.warn("Ollama not installed.")


@dataclass
class MentorConfig:
    model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: int = 512


class OllamaMentor:
    def __init__(self, config=None):
        self.config = config or MentorConfig()
        self.client = None
        self.available = False
        
        if HAS_OLLAMA:
            try:
                self.client = ollama.Client(host='http://localhost:11434')
                self.client.list()
                self.available = True
            except:
                pass
    
    def is_available(self):
        return self.available
    
    def critique_output(self, output: str, prompt: str) -> Dict:
        if not self.available:
            return {'critique': 'Ollama offline', 'score': 0}
        
        critique_prompt = f"Critique this response to '{prompt}':\n{output}\nScore 1-10 and suggest improvements."
        
        try:
            response = self.client.generate(
                model=self.config.model,
                prompt=critique_prompt
            )
            return {'critique': response.get('response', ''), 'score': 5}
        except:
            return {'critique': 'Error', 'score': 0}
