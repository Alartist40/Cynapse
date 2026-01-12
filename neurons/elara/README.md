# Custom 3B AI Model

## Overview
This project implements a custom ~2.8 Billion parameter Language Model designed to run efficiently on consumer devices (including mobile). It builds upon `nanoGPT` but incorporates state-of-the-art architectures:

1.  **DeepSeek-style Mixture of Experts (MoE)**:
    -   **Shared Experts**: Common knowledge experts that are always active (DeepSeek style).
    -   **Routed Experts**: Specialized experts selected dynamically (Top-2) to minimize compute.
2.  **TiDAR (Think in Diffusion, Talk in Autoregression)**:
    -   **Drafting Mode**: A `DiffusionHead` rapidly drafts tokens ("Thinking").
    -   **AR Mode**: The standard head validates/generates tokens ("Talking").
3.  **Tiny Recursive Model (TRM)**: Recursive blocks reuse weights to increase reasoning depth without memory bloat.

## Documentation
-   **[architecture.md](architecture.md)**: Detailed breakdown of project files and structure.
-   **[train.md](train.md)**: How to train this model (AMD/CPU friendly).
-   **[singular.md](singular.md)**: How to export this model to a single file (GGUF) for phones/Ollama.
-   **[Changelog.md](Changelog.md)**: History of changes.

## Architecture Config (Mobile Optimized ~2.8B)
-   **Layers**: 32 (Physical) * 2 (Recursive depth) = 64 effective depths
-   **Embedding Dim**: 1280
-   **Heads**: 16
-   **Experts**: 8 Routed + 1 Shared

## Quick Start
1.  **Install Requirements** (CPU/Mobile friendly):
    ```bash
    pip install -r requirements.txt
    ```
    *AMD Users: See inside requirements.txt for ROCm command.*

2.  **Verify Architecture**:
    ```bash
    python verify.py
    ```
