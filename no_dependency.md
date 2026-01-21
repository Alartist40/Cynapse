# Portable Deployment Strategy (No-Dependency Setup)

This document describes how to run Cynapse on any Windows, Mac, or Linux system **without requiring Python to be pre-installed**.

---

## Quick Start (Windows USB)

1. Run `python build_portable.py` on a development machine
2. Copy the `build/portable/` folder to your USB stick
3. On any Windows PC, double-click `run_cynapse.bat`

---

## Strategy Overview

### Windows: Embedded Python Distribution

Python provides an "embeddable" package - a minimal Python installation that can be bundled with your application. This is the **recommended approach** for USB deployment.

**How it works:**
1. Download Python embeddable package (~10MB)
2. Install pip into the embedded Python
3. Install required packages
4. Bundle everything with launcher scripts

**Pros:**
- No Python installation required on target machine
- Works on any Windows 7/8/10/11 x64 system
- Complete isolation from system Python

**Cons:**
- Windows-only (separate build needed for Mac/Linux)
- Larger distribution size (~200-500MB with dependencies)

---

### Mac/Linux: Portable Virtual Environment

For Mac/Linux, we use a **pre-built virtual environment** with precompiled wheels.

**Option A: AppImage (Linux)**
```bash
# Create AppDir structure with Python and dependencies
# Package as single executable AppImage
```

**Option B: Shell Script with Bundled Python**
```bash
# Bundle Miniconda/pyenv with the application
# Use relative paths for all operations
```

---

### Cross-Platform: Docker Container

For complete isolation and cross-platform support:

```bash
# Build container
docker build -t cynapse .

# Run with volume mount for data persistence
docker run -it -v $(pwd)/data:/app/data cynapse
```

---

## Files Created

| File | Description |
|------|-------------|
| `build_portable.py` | Script to create portable Windows distribution |
| `build/portable/` | Output folder with complete portable distribution |
| `run_cynapse.bat` | Windows launcher (created by build script) |
| `run_cynapse.sh` | Unix launcher (for Mac/Linux builds) |

---

## Minimal Dependencies Mode

For basic functionality without AI features, Cynapse can run with **zero external dependencies**:

```python
# Core features that work without dependencies:
- Neuron discovery and listing
- Configuration management
- Audit logging
- Basic CLI interface

# Features requiring dependencies:
- AI Chat (requires: ollama)
- Voice Control (requires: whistle detection)
- Training (requires: torch, transformers)
- Learning (requires: peft, torch)
```

To run in minimal mode:
```bash
python cynapse.py list   # Works without any pip packages
python cynapse.py help   # Works without any pip packages
```

---

## Building the Portable Distribution

### Prerequisites (Development Machine Only)
- Python 3.10+ installed
- Internet connection (to download embedded Python and packages)

### Build Command
```bash
cd cynapse
python build_portable.py
```

### What the Build Script Does
1. Downloads Python 3.11 embeddable package
2. Installs pip into the embedded Python
3. Installs minimal required packages
4. Creates launcher batch files
5. Bundles everything into `build/portable/`

### Output Structure
```
build/portable/
├── python/                 # Embedded Python installation
│   ├── python.exe
│   ├── python311.dll
│   ├── Lib/
│   └── site-packages/
├── cynapse/               # Application code
│   ├── cynapse.py
│   ├── hivemind.py
│   ├── neurons/
│   └── ...
├── run_cynapse.bat        # Windows launcher
└── README.txt             # Quick start instructions
```

---

## Troubleshooting

### "python.exe not found"
Make sure you're running from the `build/portable/` directory.

### Large distribution size
Remove optional neurons from `cynapse/neurons/` to reduce size:
- `elara/` (AI model files - large)
- `tinyml_anomaly/` (ML models)

### Missing DLLs on target machine
The embedded Python includes all necessary DLLs for Windows Vista+.
