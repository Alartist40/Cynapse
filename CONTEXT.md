# Project Context: Cynapse Hub

## 1. Purpose Mapping
**Cynapse** is a specialized security ecosystem designed for air-gapped and high-security environments. It orchestrates 12+ standalone security "neurons" (tools) through a central hub.
- **Core Problem**: Managing multiple security tools in a unified, portable, and offline manner.
- **Value Proposition**: Physical security via sharded AI model storage (Ghost Shell), hands-free operation via ultrasonic whistle triggers, and local AI training/inference.
- **Primary User**: Security researchers, IT auditors, and "Ghost Shell" operators who require high privacy and zero cloud dependency.

## 2. Architecture Decisions
- **Modularity**: Tools are decoupled as "neurons" with their own manifests and dependencies.
- **Physical-Acoustic Auth**: Model assembly requires 3 physical USB shards and an 18 kHz whistle trigger.
- **Portability-First**: Minimal external dependencies; Windows builds use embedded Python distributions.
- **Security-in-Depth**: SHA256 verification of shards, signature checking for neurons (though currently disabled), and restricted log permissions (0600).
- **Redundancy**: Dual entry points through `cynapse.py` (Hub) and `hivemind.py` (AI Ecosystem).

## 3. Data Flow Patterns
- **Input**: 18 kHz whistle signals, CLI commands, and English sentences for AI processing.
- **Processing**:
    - Hub: Discovery -> Verification -> Subprocess Execution.
    - HiveMind: Query -> Routing (Drones) -> Inference (Queen/Worker).
    - Ghost Shell: Verification -> XOR Decryption -> RAM Concatenation.
- **Output**:
    - Audit Trail: NDJSON logs in `.cynapse/logs/`.
    - Forensic Reports: HTML (Meerkat), JSON (Owl OCR).
    - Hardened Assets: Signed binaries, redacted files.

## 4. Integration Points
- **Ollama/AirLLM**: External and local LLM backends for HiveMind.
- **Tesseract/Flair**: OCR and NER for Privacy-focused redaction.
- **Docker**: Ephemeral environments for CTF challenges and rule verification.
- **PyAudio**: Real-time FFT analysis for ultrasonic detection.
