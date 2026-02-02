# Cynapse Dependencies

This document lists all dependencies required by the Cynapse Ghost Shell Hub and its neurons, along with brief descriptions of their purpose.

## Core Dependencies

These are required for basic hub operation:

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `numpy` | 2.4.1+ | FFT processing for ultrasonic whistle detection; array operations | Yes |
| `pycryptodome` | 3.23.0+ | Cryptographic operations, AES encryption for shards | Yes |
| `PyYAML` | 6.0.3+ | Configuration file parsing | Yes |
| `colorama` | 0.4.6+ | Cross-platform terminal colors (Windows support) | Yes |

## AI/ML Dependencies

Required for HiveMind features (Queen AI, training, inference):

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `torch` | 2.9.1+ | Neural network training and inference | For AI features |
| `transformers` | 4.57.6+ | HuggingFace model loading, tokenization | For AI features |
| `sentence-transformers` | 5.2.0+ | Text embeddings for RAG system | For RAG |
| `accelerate` | 1.12.0+ | Training acceleration, multi-GPU support | For training |
| `optimum` | 2.1.0+ | ONNX optimization for inference | Optional |
| `huggingface-hub` | 0.36.0+ | Model downloading from HuggingFace | For AI features |
| `safetensors` | 0.7.0+ | Safe tensor file format for models | For AI features |
| `tokenizers` | 0.22.2+ | Fast tokenization | For AI features |
| `sentencepiece` | 0.2.1+ | Subword tokenization | For some models |

## Data Processing

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `pandas` | 2.3.3+ | Data manipulation and analysis | For analytics |
| `openpyxl` | 3.1.5+ | Excel file reading/writing | For reports |
| `pypdf` | 6.6.2+ | PDF manipulation (updated for CVE fixes) | For PDFs |
| `PyPDF2` | 3.0.1+ | PDF reading (legacy, to be deprecated) | Legacy |
| `pillow` | 12.1.0+ | Image processing for OCR neuron | For owl_ocr |

## Networking & HTTP

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `requests` | 2.32.5+ | HTTP client for API calls | For network features |
| `httpx` | 0.28.1+ | Async HTTP client | For async operations |
| `urllib3` | 2.6.3+ | HTTP library (requests dependency) | Indirect |
| `certifi` | 2026.1.4+ | SSL certificates | Indirect |

## Machine Learning Utilities

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `scikit-learn` | 1.8.0+ | ML algorithms, preprocessing | For tinyml_anomaly |
| `scipy` | 1.17.0+ | Scientific computing, signal processing | For analysis |
| `joblib` | 1.5.3+ | Parallel processing, model persistence | Indirect |

## System & Utilities

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `psutil` | 7.2.1+ | System monitoring, process management | For monitoring |
| `tqdm` | 4.67.1+ | Progress bars | For UI feedback |
| `pydantic` | 2.12.5+ | Data validation, settings management | For configs |
| `ollama` | 0.6.1+ | Local LLM inference via Ollama | For local AI |
| `regex` | 2026.1.15+ | Advanced regex (better than stdlib) | For parsing |
| `Jinja2` | 3.1.6+ | Template rendering | For reports |

## Math & Computation

| Package | Version | Purpose | Required |
|---------|---------|---------|----------|
| `sympy` | 1.14.0+ | Symbolic mathematics | For analysis |
| `mpmath` | 1.3.0+ | Arbitrary precision math | Indirect |
| `networkx` | 3.6.1+ | Graph algorithms | For analysis |

---

## Dependency Reduction Opportunities

Based on the security audit, the following dependencies could potentially be reduced or replaced:

### 1. Replace `PyPDF2` with `pypdf`
- **Current**: Both `PyPDF2` and `pypdf` are installed
- **Recommendation**: Remove `PyPDF2`, use only `pypdf` (actively maintained)
- **Savings**: ~1 dependency

### 2. Use stdlib `urllib` instead of `requests` (where possible)
- **Current**: `requests` used for simple HTTP calls
- **Recommendation**: Use `urllib.request` for simple GET requests
- **Savings**: Removes `requests`, `urllib3`, `charset-normalizer`, `idna` (~4 dependencies)
- **Tradeoff**: Less convenient API, more code

### 3. Make AI dependencies optional
- **Current**: All AI packages loaded even when not using AI features
- **Recommendation**: Already implemented via lazy imports in `hivemind.py`
- **Status**: ✅ Completed

### 4. Bundle `colorama` functionality
- **Current**: Uses `colorama` for Windows ANSI support
- **Recommendation**: For portability, could inline the minimal functionality needed
- **Savings**: ~1 dependency

---

## Minimum Installation

For a minimal installation without AI features:

```bash
pip install numpy pycryptodome PyYAML colorama psutil tqdm
```

## Full Installation

For all features including AI:

```bash
pip install -r requirements.txt
```

---

## Security Notes

- **pypdf**: Ensure version 6.6.2+ to address CVE-2026-22690 and CVE-2026-22691
- **requests**: No known critical CVEs in current version
- **torch**: Downloaded models should be verified with signatures

---

## Version Pinning Strategy

The `requirements.txt` uses exact version pinning (`==`) for reproducibility. When updating:

1. Test all neurons with new versions
2. Update this document
3. Run security audit (`python cynapse.py --test`)
4. Update CHANGELOG.md
