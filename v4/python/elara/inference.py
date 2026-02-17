"""
Elara Inference Engine
=====================

Async text generation with streaming support.
Optimized for Cynapse integration.
"""

import torch
import asyncio
from typing import Optional, Callable, List
from pathlib import Path
import warnings

try:
    from .model_loader import ElaraModelLoader, HAS_ELARA
except (ImportError, ValueError):
    try:
        from model_loader import ElaraModelLoader, HAS_ELARA
    except ImportError:
        HAS_ELARA = False
        ElaraModelLoader = None


class ElaraInference:
    """
    Inference interface for Elara model.

    Features:
    - Async generation
    - Streaming output
    - Memory-efficient
    - Progress callbacks
    """

    def __init__(self, model_loader: Optional['ElaraModelLoader'] = None):
        self.loader = model_loader or ElaraModelLoader()
        self.model = None
        self.is_generating = False

    async def load_model(self) -> bool:
        """Load model asynchronously."""
        if not HAS_ELARA:
            return False

        # Run blocking load in thread pool
        loop = asyncio.get_event_loop()
        self.model = await loop.run_in_executor(
            None, self.loader.load
        )

        return self.model is not None

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_k: int = 40,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Generate text asynchronously.

        Args:
            prompt: Input text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Top-k sampling
            stream_callback: Function called with each token

        Returns:
            Generated text
        """
        if not self.model:
            return "Error: Model not loaded"

        if self.is_generating:
            return "Error: Already generating"

        self.is_generating = True

        try:
            import tiktoken
            enc = tiktoken.get_encoding("gpt2")

            # Encode prompt
            input_ids = torch.tensor(enc.encode(prompt, allowed_special={"<|endoftext|>"}), dtype=torch.long)
            input_ids = input_ids.unsqueeze(0).to(next(self.model.parameters()).device)

            # Generate
            output_ids = self.model.generate(input_ids, max_tokens, temperature=temperature, top_k=top_k)

            # Decode (only the new part)
            new_tokens = output_ids[0, input_ids.size(1):]
            response = enc.decode(new_tokens.tolist())

            if stream_callback:
                # Simulate streaming for now as model.generate is not natively streaming
                for word in response.split():
                    stream_callback(word + " ")
                    await asyncio.sleep(0.01)

            return response

        except Exception as e:
            return f"Inference error: {e}"
        finally:
            self.is_generating = False

    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self.model is not None

    async def unload(self):
        """Unload model asynchronously."""
        if self.model:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.loader.unload)
            self.model = None


# Simple test
if __name__ == "__main__":
    async def test():
        inference = ElaraInference()
        print("Testing Elara inference...")

        if await inference.load_model():
            print("Model loaded!")
            response = await inference.generate("Hello")
            print(f"Response: {response}")
        else:
            print("Model not available")

    asyncio.run(test())
