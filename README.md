# Cynapse: The Ghost Shell Hub

> *"Your AI should know you—but no one else."*

**Cynapse** is a bio-digital security ecosystem designed for high-privacy environments. It orchestrates specialized "neurons" (security tools) through a central hub, presenting them in a Neural Operations Center TUI.

---

## 🚀 Features

-   **Synaptic Fortress TUI**: A cyberpunk terminal interface that visualizes your system's security state as a living organism.
-   **HiveMind AI**: An n8n-style workflow engine for local AI (Elara) training and tool use.
-   **Ghost Shell**: Physical security via USB-sharded authentication and RAM-only model assembly.
-   **Polyglot Neurons**:
    -   🐘 **Elephant**: Ed25519 binary signing (Rust)
    -   🦏 **Rhino**: Zero-trust API gateway (Go)
    -   🐺 **Wolverine**: RAG security auditing (Python)
    -   🦇 **Bat**: USB shard management (Python)

---

## 📦 Installation

### Option A: Native Binary (Easy)
Download the latest release for your OS from the Releases page.
-   **Windows**: Double-click `Cynapse.exe`
-   **Linux**: Run `./Cynapse.AppImage`

### Option B: Run from Source (Dev)

**Prerequisites**:
-   Python 3.10+
-   (Optional) Go 1.20+ (for Rhino)
-   (Optional) Rust/Cargo (for Elephant)

**Setup**:
1.  Clone the repository:
    ```bash
    git clone https://github.com/Alartist40/Cynapse.git
    cd Cynapse
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Run the system:
    ```bash
    python cynapse_entry.py --tui
    ```

---

## 🛠️ Usage

### CLI Mode
Run specific tasks without the interface:
```bash
python cynapse_entry.py --cli
```

### Building from Source
Create a standalone executable:
```bash
python build_scripts/build_all.py
```
*Note: Requires Go and Rust installed for full polyglot compilation.*

---

## 📂 Architecture

The project is structured as a unified Python package:
-   `cynapse/core`: Central logic (Hub, HiveMind)
-   `cynapse/tui`: User interface code
-   `cynapse/neurons`: Security tools and modules

See [architecture.md](architecture.md) for details.

---

## 📄 License
MIT License. See LICENSE for details.
