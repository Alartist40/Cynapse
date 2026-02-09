# Creating a Single Runnable File (GGUF)

To make your model portable (a "singular" file) that works with **Ollama**, **LM Studio**, or **llama.cpp** on phones and laptops, you need to convert it to the **GGUF** format.

## Prerequisites
1.  **llama.cpp**: You need to clone and build the `llama.cpp` repository.
    ```bash
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp
    make
    ```

## Conversion Steps

### 1. Export to HuggingFace Format
First, your raw PyTorch checkpoint (`ckpt.pt`) needs to be converted to a HuggingFace-compatible `model.safetensors` or `pytorch_model.bin` with a `config.json`.
Since this is a **Custom Architecture** (MoE + TiDAR + Recursive), standard conversion scripts might need valid python code to load it.
1.  Ensure your `model.py` is in the directory.
2.  Create a python script to load your `ckpt.pt` and save it with `save_pretrained`:
    ```python
    from model import GPT, GPTConfig
    import torch
    
    # Load your checkpoint
    ckpt = torch.load('out/ckpt.pt')
    config = GPTConfig(**ckpt['model_args'])
    model = GPT(config)
    model.load_state_dict(ckpt['model'])
    
    # Save as HF
    # Note: You might need to map custom keys if using a strict HF runner, 
    # but for GGUF conversion, we often just need the tensor files.
    torch.save(model.state_dict(), 'hf_model/pytorch_model.bin')
    # Save config.json manually or via transformers if mapped.
    ```

### 2. Convert to GGUF
Use the specific conversion script provided by `llama.cpp`.
*Note: Since your architecture is custom (DeepSeek-MoE + Recursive), standard `llama.cpp` might not support it out of the box unless you map it to a supported architecture (like `mixtral` for MoE) or implement the C++ inference code in llama.cpp.*

**For Standard GPT-2 based structures:**
```bash
python llama.cpp/convert-hf-to-gguf.py ./hf_model --outfile custom_model_3b.gguf --outtype f16
```

### 3. Quantization (Critical for Mobile)
To make it small enough for phones (3B params ~ 6GB -> 2GB):
```bash
./llama.cpp/quantize custom_model_3b.gguf custom_model_3b-q4_k_m.gguf q4_k_m
```
This `custom_model_3b-q4_k_m.gguf` is your **Singular File**.

## Usage
**Run on Phone (using generic GGUF loader app):**
-   Copy `custom_model_3b-q4_k_m.gguf` to your phone.
-   Open app (e.g. Layla, ChatterUI).
-   Load the GGUF file.

**Run with Ollama:**
1.  Create a `Modelfile`:
    ```dockerfile
    FROM ./custom_model_3b-q4_k_m.gguf
    PARAMETER temperature 0.7
    SYSTEM You are a helpful AI assistant.
    ```
2.  Create the model:
    ```bash
    ollama create my-custom-model -f Modelfile
    ```
3.  Run:
    ```bash
    ollama run my-custom-model
    ```
