# Changelog

## [1.1.0] - 2026-02-02
### 🚀 Improvements
- **Hub Refactor Integration**: Updated for compatibility with the new Cynapse Hub restructuring
- **TUI Support**: Added semantic metadata for the Synaptic Fortress Interface
- **Security Audit**: Verified implementation against the 2026 security audit report


## [Unreleased] - MVP Demo

### Added
-   **Core Scanner (`scan.py`)**:
    -   Implemented inventory logic for Python packages (via `sys.path` and `.dist-info`).
    -   Implemented inventory logic for Node.js modules (recursive search for `package.json` in user home).
    -   Implemented version detection for Chrome, Firefox, Git, and Docker via WMI (Windows) and `which`/`--version` (Linux/macOS).
    -   Vulnerability matching logic against local SQLite database.
    -   Generation of `report.html` using a template.
-   **Database Builder (`db_build.py`)**:
    -   Logic to fetch NVD JSON data (gzipped).
    -   Parser to extract Product, Version, CVE ID, CVSS score, and Description.
    -   **Fallback Mechanism**: Added robust handling for HTTP 403 Forbidden errors from NVD. If the feed is unreachable, the script automatically seeds the database with mock data (e.g., Python 3.9.0 vulnerabilities) to ensure the MVP is demonstrable.
    -   Dual download method: Tries `urllib` first, falls back to `curl` if available.
-   **Reporting**:
    -   Created `report_template.html` with Jinja-like placeholders.
    -   Supported color-coded severity levels (High, Medium, Clean).

### Technical Details
-   **Zero-Dependency**: The scanner runs strictly on the Python Standard Library (`sqlite3`, `json`, `pathlib`, `re`, `subprocess`, `html`). No `pip install` required for the target machine.
-   **Cross-Platform**: Designed to work on Windows and Linux/macOS.
-   **Database**: Uses SQLite for fast, single-file offline lookups. Schema includes `pkg`, `version`, `cve_id`, `cvss`, `summary`.
