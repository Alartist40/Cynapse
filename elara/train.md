# Training the Custom 3B Model

This guide explains how to train your custom model from scratch.

## 1. Environment Setup
Unlike standard setups, this model is optimized for accessibility.
-   **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
-   **AMD/ROCm Users**: Install PyTorch with ROCm support manually if needed:
    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/rocm5.6
    ```
-   **CPU Users**: Install lightweight PyTorch:
    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    ```

## 2. Data Preparation
The model expects a `data/` directory. You can use any text dataset.
1.  **Download a dataset** (e.g., TinyShakespeare for testing, or OpenWebText for real training).
2.  **Tokenize it**:
    ```bash
    # Example using the included prepare.py (if available) or creating a simple one
    python data/shakespeare_char/prepare.py
    ```
    *Note: Ensure you have `train.bin` and `val.bin` in your data folder.*

## 3. Training Configuration
Edit `config/train_gpt2.py` (or create a new config file) to set your hyperparameters.
For this **3B Custom Model**, we recommend starting with a smaller batch size to fit in memory if training on consumer hardware, or using Gradient Accumulation.

**Key Hyperparameters to Check in `train.py`:**
-   `batch_size`: lowering this helps memory.
-   `gradient_accumulation_steps`: increase this to simulate larger batch sizes.
-   `max_iters`: How long to train.

## 4. Running the Training
```bash
python train.py config/train_custom_3b.py
```
*Note: Since we modified `model.py` to return `(logits, loss)` or `(logits, loss, diff_logits)`, ensure your `train.py` handles the new return signature if you enabled TiDAR diffusion loss.*

### Training with TiDAR (Diffusion + AR)
The model `forward` pass now supports `mode='ar'` and `mode='diffusion'`.
To train the diffusion head effectively, your training loop should:
1.  Compute AR Loss: `logits, loss_ar = model(X, Y)`
2.  Compute Diffusion Loss: `diff_logits, _ = model(X, mode='diffusion')` -> calculate loss against Y.
3.  Combine: `loss = loss_ar + lambda * loss_diff`.
*(The current `model.py` implementation combines these automatically if `use_diffusion_head` is True and targets are provided.)*

## 5. Monitoring
Install `wandb` to monitor training progress:
```bash
pip install wandb
wandb login
```
Set `wandb_log = True` in your config to see graphs of Loss vs Steps.
