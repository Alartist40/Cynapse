# Changelog

## [1.0.0] - Custom 3B Model Architecture
### Added
- **DeepSeek-Style Shared Experts**:
    - Added `SharedExpert` MLP to MoE layers (always active pathway).
- **TiDAR Generation Logic**:
    - Added `generate_tidar` method for diffusion-based drafting.
- **Documentation**:
    - Added `train.md` (Training guide).
    - Added `singular.md` (Export/GGUF guide).

### Changed
- **Mobile Optimization**:
    - Reduced `n_embd` to 1280 to target ~2.8B parameters (fitting 4GB RAM phones in quantized modes).
    - Optimized `requirements.txt` to exclude default NVIDIA CUDA bloat.
    - Updated `MoE` class to include Shared Experts pathway.

### Fixed
- **Parameter Target**: Adjusted config to strictly meet the "Small enough for basic device" requirement while maintaining 3B-class reasoning capacity.
