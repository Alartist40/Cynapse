# Project Architecture

This document describes the structure and role of every file in the `custom_model` project.

## Core Codebase

### [model.py](model.py)
**Role**: The brain of the project.
-   **Contains**: The full architecture of the Custom 3B Model.
-   **Key Classes**:
    -   `GPTConfig`: Configuration (Layers: 32, Dim: 1280, Experts: 8+1).
    -   `MoE`: The Mixture-of-Experts layer (incorporating Shared Experts and Noisy Top-K Router).
    -   `DiffusionHead`: The "Think" module for TiDAR drafting.
    -   `RecursiveBlock`: The "Reasoning" loop wrapper (TRM style).
    -   `GPT`: The main Transformer combining all above.

### [verify.py](verify.py)
**Role**: Architecture Validator.
-   **Usage**: Run this to check if your model is built correctly.
-   **Function**: Instantiates a model with default config, counts parameters, and runs a dummy data batch to ensure the code does not crash.

### [sample.py](sample.py)
**Role**: Inference Script.
-   **Usage**: `python sample.py`
-   **Function**: Loads a checkpoint and generates text. Can run on CPU or GPU.

### [train.py](train.py)
**Role**: The Teacher.
-   **Usage**: `python train.py`
-   **Function**: Loads data, calculates loss (AR + Diffusion), and updates model weights. Handles distributed training (DDP) and logging (WandB).

## Configuration & Data

### [configurator.py](configurator.py)
**Role**: Config Helper.
-   **Usage**: Internal utility.
-   **Function**: Allows you to override config values from command line arguments (e.g. `--batch_size=32`).

### [custom_model/requirements.txt](requirements.txt)
**Role**: Dependency List.
-   **Usage**: `pip install -r requirements.txt`
-   **Function**: Lists all python libraries needed to run the project. Optimized for CPU/AMD to avoid bloat.

## Documentation

-   **[README.md](README.md)**: Main entry point. Quick start and overview.
-   **[train.md](train.md)**: Detailed training guide.
-   **[singular.md](singular.md)**: Detailed export guide (creating GGUF).
-   **[Changelog.md](Changelog.md)**: History of architectural changes.
