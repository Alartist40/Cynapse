"""
HiveMind Trainer - Distillation training for Queen model
Uses lazy imports to avoid loading heavy dependencies at module import time.
"""


class HiveMindTrainer:
    """Trainer for the Queen model using knowledge distillation from larger models."""
    
    def __init__(self, queen_path, teacher_name):
        self.queen_path = queen_path
        self.teacher_name = teacher_name
        self.queen = None
        self.teacher = None
        self.optimizer = None
        
        # Load Queen model
        self.queen = self._load_queen(queen_path)
        
        # Load Teacher model (lazy - only when needed)
        print(f"[Trainer] Will load teacher model: {teacher_name} when training starts...")
        
    def _load_queen(self, path):
        """Load the Queen model from GGUF using llama.cpp."""
        try:
            from llama_cpp import Llama
            return Llama(model_path=path, n_gpu_layers=-1, verbose=False)
        except ImportError:
            print("[Trainer] llama-cpp-python not installed. Queen model loading deferred.")
            return None
        except Exception as e:
            print(f"[Trainer] Could not load Queen model: {e}")
            return None

    def _load_teacher(self):
        """Lazy load the teacher model only when training starts."""
        if self.teacher is not None:
            return self.teacher
            
        try:
            # Try to import from local airllm
            import sys
            import os
            airllm_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'airllm')
            if airllm_path not in sys.path:
                sys.path.insert(0, airllm_path)
            
            try:
                from airllm import AutoModel
            except ImportError:
                from cynapse.airllm import AutoModel
            
            print(f"[Trainer] Loading teacher model: {self.teacher_name} (this may take time)...")
            self.teacher = AutoModel.from_pretrained(self.teacher_name)
            return self.teacher
        except ImportError as e:
            print(f"[Error] Could not import AutoModel: {e}")
            print("Please install: pip install transformers torch accelerate")
            return None
        except Exception as e:
            print(f"[Error] Could not load teacher model: {e}")
            return None

    def train_step(self, prompt: str):
        """Perform a single training step using knowledge distillation."""
        # Lazy load teacher
        teacher = self._load_teacher()
        if not teacher:
            print("[Trainer] Teacher model not loaded.")
            return 0.0

        # Teacher generates answer
        print(f"[Trainer] Teacher generating for: '{prompt}'")
        try:
            input_tokens = teacher.tokenizer(
                [prompt], 
                return_tensors="pt", 
                return_attention_mask=False, 
                truncation=True, 
                max_length=128, 
                padding=False
            )
            teacher_out = teacher.generate(
                input_tokens['input_ids'].cuda(),
                max_new_tokens=50,
                return_dict_in_generate=True,
                output_scores=True
            )
            teacher_text = teacher.tokenizer.decode(teacher_out.sequences[0])
            print(f"[Trainer] Teacher says: {teacher_text[:50]}...")
        except Exception as e:
            print(f"[Trainer] Teacher inference failed: {e}")
            return 0.0

        # Queen logic (Distillation)
        # Note: If self.queen is Llama object, we can't do torch .backward() on it directly.
        # This requires the Queen to be a PyTorch model for real backprop.
        print("[Trainer] Distillation step calculated (mock). Queen requires PyTorch model for real backprop.")
        return 0.1  # Mock loss

    def train_on_dataset(self, dataset_path):
        """Train on a dataset of prompts."""
        import json
        
        with open(dataset_path, 'r') as f:
            for line in f:
                if line.strip():
                    prompt = json.loads(line).get("prompt", "")
                    if prompt:
                        loss = self.train_step(prompt)
                        print(f"Loss: {loss}")
