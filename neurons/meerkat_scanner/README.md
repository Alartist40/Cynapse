# Air-Gap Update Scanner (MVP)

A lightweight, single-folder tool designed to inventory software and scan for CVEs on air-gapped Windows/Linux systems. No internet, no admin rights, and no installation required on the target machine.

## Features

-   **Zero-Install**: Runs from a single folder or executable.
-   **Offline Capable**: Uses a local SQLite database (`cve.db`) for vulnerability lookups.
-   **Local Inventory**: Scans for:
    -   Python packages (checking `sys.path` sites)
    -   Node.js modules (scanning `package.json` in user home)
    -   Common System Executables (Chrome, Firefox, Git, Docker)
-   **Reporting**: Generates a self-contained `report.html` with color-coded risk assessment.

## How It Works

1.  **Preparation (Online)**: You run `db_build.py` on an internet-connected machine. This script downloads the latest CVE definitions from NVD (National Vulnerability Database) and builds a compact SQLite database (`cve.db`).
    *   *Note: If the NVD feed is blocked (403 Forbidden), the script automatically populates with a set of mock CVEs for demonstration purposes.*
2.  **Transfer**: You copy the entire project folder (containing `scan.py` and `cve.db`) to your air-gapped machine using a USB drive or secure transfer method.
3.  **Scan (Offline)**: You run `scan.py` on the target machine. It:
    -   Walks the file system to find installed software versions.
    -   Queries the local `cve.db` for known vulnerabilities matching the found software.
    -   Produces `report.html`.

## Setup Instructions (Fresh Computer)

### Prerequisites
-   **Python 3.8+** installed.
-   Basic standard libraries (pre-installed with Python).

### Step 1: Build the Database (Internet Required)
On a computer with internet access:
1.  Open a terminal in the project folder.
2.  Run the build script:
    ```bash
    python db_build.py
    ```
    -   This will create `cve.db`.
    -   *If you see "Switching to MOCK DATA mode", it means NVD access was blocked, but the database uses sample data so you can still test the scanner.*

### Step 2: Run the Scan (Offline)
On the target air-gapped computer:
1.  Copy the folder containing `scan.py`, `cve.db`, and `report_template.html`.
2.  Open a terminal in that folder.
3.  Run the scanner:
    ```bash
    python scan.py
    ```
4.  Wait for the scan to complete (usually < 2 minutes).
5.  Open the generated `report.html` in any web browser to view your risk report.

## Packaging as EXE (Optional)
To create a standalone executable that doesn't need Python installed on the target:
1.  Install PyInstaller: `pip install pyinstaller`
2.  Run: `pyinstaller --onefile scan.py`
3.  Use the generated `dist/scan.exe` (Windows) or `dist/scan` (Linux). (Remember to keep `cve.db` and `report_template.html` in the same folder as the exe).
