# Cynapse Fix & Improvement Guide

This document outlines the critical fixes and optimizations required to make Cynapse fully functional and "production-ready" for testing.

## 1. Critical Performance Fixes

### TUI Input Bottleneck
The current `InputHandler._handle_operations` spawns a HiveMind bee on *every* character typed if not careful (though the current code waits for `\r`), but the blocking `read_key` and single-threaded nature can cause UI stutter.
- **Fix**: Move `HiveMind` initialization and heavy bee execution to a background thread.
- **Fix**: Implement an input queue for the TUI to prevent key loss during heavy processing.
- **Fix**: Replace `print()` based rendering with buffered `sys.stdout.write()` to eliminate flickering.

### Lazy Loading Optimization (cynapse/core/hivemind.py)
`_ensure_numpy` is sometimes called in loops.
- **Fix**: Initialize `numpy` at the module level but inside `HiveMind.__init__` or a unified lazy loader to ensure it's only imported when `HiveMind` is actually used, keeping startup light.

## 2. Integration Fixes

### Elara Model Pathing
The `ElaraModelLoader` and `ElaraTrainer` inconsistently handle paths to the `elara` reference implementation.
- **Fix**: Standardize `sys.path.insert` to use absolute paths based on the project root.
- **Fix**: Add a `--check-weights` command to `cynapse_entry.py` to verify `elara.gguf` existence before launch.

### Neuron Discovery (cynapse/core/hub.py)
The directory scanner doesn't currently parse `manifest.json`.
- **Fix**: Implement `json.load()` for all subdirectories in `cynapse/neurons/` to get real metadata instead of just filenames.

### Missing Configuration Module
The `cynapse.utils.config` module referenced in architecture is missing.
- **Fix**: Create `cynapse/utils/config.py` to handle `config.ini` parsing centrally.

## 3. Security Hardening

### Arbitrary Code Execution
`CodeExecuteNode` allows running any Python code via `subprocess`.
- **Fix**: Add a whitelist of allowed imports or disable it by default in `config.ini`.
- **Fix**: Add a "Sandbox" warning in the TUI when this node runs.

### Thread Safety
`HiveMind.running_bees` is accessed without locks.
- **Fix**: Add `threading.Lock()` around `running_bees` and SQLite writes.

## 4. Aesthetic & UX Improvements

### TUI Fluidity
- **Improvement**: Increase animation frame rate from 4fps to 10fps for smoother transitions (still low enough for minimal CPU).
- **Improvement**: Use `sys.stdout.write` for rendering to prevent cursor flashing/flickering.

### Robust CLI
- **Improvement**: Add `rich` console output to `cynapse_entry.py` for health checks and initialization progress.

## 5. Optimization Tasks (Weak Hardware Focus)

| Target | Current | Optimized Goal |
|--------|---------|----------------|
| Startup Time | ~800ms | < 300ms |
| Model Load | Local disk speed | Mmap-optimized (faster concurrent access) |
| Search Latency | O(n) | Vector-indexed (numpy optimized) |
| Memory Usage | High (eager imports) | Lazy (on-demand imports only) |

## 6. Deployment Step-by-Step

1. **Clean Init**: `python cynapse_entry.py --init`
2. **Setup Dependencies**: `pip install -r requirements-full.txt`
3. **Hardware Config**: `python cynapse_entry.py --configure-model`
4. **Health Audit**: `python cynapse_entry.py --health`
5. **Launch**: `python cynapse_entry.py --tui`

---
*Updated on: 2026-02-09 | Version: 2.1.1-fix*
