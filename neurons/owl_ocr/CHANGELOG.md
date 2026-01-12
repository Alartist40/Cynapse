# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Core Logic (`redact.py`)**:
    - Implemented `ocr_image` function using local Tesseract subprocess.
    - Implemented `find_pii` using Regex patterns for Email, Phone, Credit Card, and SSN.
    - Implemented masking logic (`mask()`) to hide PII values in reports.
    - Added `redact_image_file` using `Pillow` to draw redaction boxes.
    - Added comprehensive error handling for missing dependencies.
- **Documentation**:
    - Created `README.md` with setup and usage instructions.
    - Added `requirements.txt` for minimal dependencies.

### Changed
- **PDF Handling**:
    - Implemented basic PDF structure parsing with `pypdf`.
    - Added fallback/warning for PDF OCR when external rendering tools are missing.
