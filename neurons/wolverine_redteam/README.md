# Local RAG Red-Team (MVP)

![GitHub Workflow Status](https://img.shields.io/badge/Red--Team-Passing-green)

A lightweight (200-line) Python CLI tool to adversarially test your local RAG pipeline (e.g., Ollama, Elara). It runs a suite of attacks including system prompt leaks, poisoning, and refusal checks, producing a PASS/FAIL scorecard.

## Features
- **Offline & Local**: Targets `localhost` (default: Ollama). No cloud keys required.
- **12 Hard-coded Attacks**: Covers System Leaks, Chunk Leaks, Poisoning, and Refusal robustness.
- **CI/CD Ready**: Outputs JUnit XML (`redteam.xml`) and returns exit codes for CI pipelines.
- **Zero Dependencies**: Uses Python standard library only.

## Setup Instructions (Fresh Computer)

### 1. Prerequisites
- **Python 3.8+**: [Download Python](https://www.python.org/downloads/). Ensure `python` is added to your PATH.
- **Ollama**: [Download Ollama](https://ollama.com/).

### 2. Configure Ollama
Pull the default model used by the tool (`llama3.2`):
```bash
ollama pull llama3.2
```
*Note: If you want to use a different model, edit `MODEL` in `redteam.py`.*

Ensure Ollama app is running. It typically listens on `http://localhost:11434`.

### 3. Installation
Clone this repository (or download the files):
```bash
git clone https://github.com/Alartist40/Local-RAG-Red-Team.git
cd Local-RAG-Red-Team
```

## Usage

Simply run the script:
```bash
python redteam.py
```

### Output Explained
The tool will print a table of results:
```text
✅ PASS system #1 – ...
❌ FAIL poison #7 – ...

🔒 Red-team 9/12
```
- **✅ PASS**: The system successfully defended against the attack (e.g., refused a harmful query, didn't leak system prompt).
- **❌ FAIL**: The system failed (e.g., answered a harmful query, was poisoned).

### Files
- `redteam.py`: The main CLI tool.
- `attacks.json`: Configuration file containing the 12 attack definitions.
- `redteam.xml`: Generated after running, compatible with CI tools (GitHub Actions, Jenkins) to display test results.

## Customization
To add more attacks, simply edit `attacks.json`. The supported `judge_type`s are:
- `contains`: Fails if `judge_param` string is found in response.
- `contains_ignore_case`: Fails if `judge_param` string is found (case-insensitive).
- `contains_any`: Fails if any string in `judge_param` list is found.
- `min_length`: Fails if response length > `judge_param`.
- `refusal_check`: Fails if response is NOT a refusal (checks against a keyword list).

## Troubleshooting
- **Connection Error**: Ensure Ollama is running (`ollama serve`).
- **Model not found**: Run `ollama list` to check available models and update `MODEL` variable in `redteam.py`.
