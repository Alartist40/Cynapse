
import torch
import torch
from torch.optim import AdamW
try:
    from cynapse.airllm import AutoModel
except ImportError:
    try:
        from airllm import AutoModel
    except ImportError:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'airllm'))
        from cynapse.airllm import AutoModel

class HiveMindTrainer:
    def __init__(self, queen_path, teacher_name):
        self.queen_path = queen_path
        self.queen = self.load_queen(queen_path)
        print(f"[Trainer] Loading teacher model: {teacher_name} (this may take time)...")
        self.teacher = AutoModel.from_pretrained(teacher_name)
        # Note: Optimization on GGUF directly is tricky. 
        # Usually we need a PyTorch model for backprop. 
        # improvement.md suggests loading GGUF via llama.cpp but then using AdamW on it?
        # That part of improvement.md is pseudo-code/conceptual. 
        # You can't backprop into a GGUF loaded by llama.cpp easily without converting it to a trainable format or using a specific library.
        # For this MVP, we will implement the inference/distillation step structure 
        # but acknowledge the limitation or assume the user has a trainable PyTorch version of the Queen 
        # OR we use a LORA adapter on top of a base model.
        # Given the constraint of 'day 1', I will implement the logic as requested but add a note.
        
        # However, to make it runnable, I'll mock the optimizer step if GGUF is used, 
        # or require a PyTorch model for the Queen for real training.
        # improvement.md days: "Queen is generalist... custom 3B MoE model... (GGUF)"
        # But later: "Queen learns via distillation... loss.backward()"
        # This requires the Queen to be a PyTorch model (e.g. HuggingFace AutoModelForCausalLM).
        # if the user provides GGUF, we can only infer, not train, unless we use tools that support GGUF training (like llama.cpp finetune).
        # But the code in improvement.md imports torch and does loss.backward().
        # So I will assume we need a PyTorch model for the Queen for the training mode, 
        # or I will implement a placeholder that warns about GGUF.
        
        # For now, I'll follow the improvement.md structure but make it robust.
        self.optimizer = None # placeholder

    def load_queen(self, path):
        # improvement.md suggests llama_cpp.Llama
        try:
            from llama_cpp import Llama
            return Llama(model_path=path, n_gpu_layers=-1, verbose=False)
        except ImportError:
            print("[Trainer] llama-cpp-python not installed. Queen model loading failed.")
            return None

    def train_step(self, prompt: str):
        if not self.teacher:
            print("[Trainer] Teacher model not loaded.")
            return 0.0

        # Teacher generates answer
        print(f"[Trainer] Teacher generating for: '{prompt}'")
        try:
            input_tokens = self.teacher.tokenizer([prompt], return_tensors="pt", return_attention_mask=False, truncation=True, max_length=128, padding=False)
            teacher_out = self.teacher.generate(
                input_tokens['input_ids'].cuda(), 
                max_new_tokens=50,
                return_dict_in_generate=True,
                output_scores=True
            )
            teacher_text = self.teacher.tokenizer.decode(teacher_out.sequences[0])
            print(f"[Trainer] Teacher says: {teacher_text[:50]}...")
        except Exception as e:
            print(f"[Trainer] Teacher inference failed: {e}")
            return 0.0
        
        # Queen logic (Distillation)
        # Check if we can actually train
        # If self.queen is Llama object, we can't do torch .backward() on it directly.
        
        print("[Trainer] Distillation step calculated (mock). Queen requires PyTorch model for real backprop.")
        return 0.1 # Mock loss

    def train_on_dataset(self, dataset_path):
        import json
        with open(dataset_path, 'r') as f:
            for line in f:
                if line.strip():
                    prompt = json.loads(line).get("prompt", "")
                    if prompt:
                        loss = self.train_step(prompt)
                        print(f"Loss: {loss}")

