# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-01-08

### Added
- **Core CLI (`redteam.py`)**: Implemented the main red-teaming engine using Python standard library.
- **Attack Suite (`attacks.json`)**: Added 12 baseline attacks covering:
    - System Prompt Leaks
    - RAG Source/Chunk Leaks
    - Data Poisoning (Math, Facts)
    - Safety Refusals (Harmful queries)
- **Reporting**: Added JUnit XML generation (`redteam.xml`) for CI integration.
- **Documentation**: Added comprehensive `README.md` with setup and usage instructions.

### Technical Implementation
- **Architecture**: Zero-dependency Python script interacting with local LLM APIs via `urllib`.
- **Extensibility**: Attacks are defined in JSON, allowing easy addition of new test cases without code changes.
- **Evaluators**: Implemented deterministic heuristic judges (keyword matching, length checks, refusal detection).
