#!/usr/bin/env python3
"""
Cynapse Portable Builder
Creates a self-contained Windows distribution with embedded Python.
No Python installation required on the target machine.

Usage:
    python build_portable.py

Output:
    build/portable/  - Complete portable distribution
"""

import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.11.9"
PYTHON_EMBED_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Minimal dependencies for portable distribution (no heavy ML packages)
MINIMAL_DEPS = [
    "ollama",  # For chat functionality
]

# Directory setup
SCRIPT_DIR = Path(__file__).parent.resolve()
BUILD_DIR = SCRIPT_DIR / "build" / "portable"
PYTHON_DIR = BUILD_DIR / "python"
APP_DIR = BUILD_DIR / "cynapse"


def download_file(url: str, dest: Path) -> bool:
    """Download a file from URL to destination."""
    print(f"  Downloading: {url}")
    try:
        urllib.request.urlretrieve(url, dest)
        return True
    except Exception as e:
        print(f"  [Error] Download failed: {e}")
        return False


def extract_zip(zip_path: Path, dest_dir: Path):
    """Extract a zip file to destination directory."""
    print(f"  Extracting to: {dest_dir}")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dest_dir)


def setup_embedded_python():
    """Download and setup embedded Python."""
    print("\n[1/5] Setting up embedded Python...")
    
    # Create directories
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    
    # Download Python embeddable
    zip_path = BUILD_DIR / "python_embed.zip"
    if not zip_path.exists():
        if not download_file(PYTHON_EMBED_URL, zip_path):
            return False
    else:
        print("  Using cached Python embeddable package")
    
    # Extract
    extract_zip(zip_path, PYTHON_DIR)
    
    # Enable pip by modifying python311._pth
    pth_file = PYTHON_DIR / f"python311._pth"
    if pth_file.exists():
        content = pth_file.read_text()
        # Uncomment import site line
        content = content.replace("#import site", "import site")
        # Add Lib\site-packages
        if "Lib\\site-packages" not in content:
            content += "\nLib\\site-packages\n"
        pth_file.write_text(content)
        print("  Modified python311._pth for pip support")
    
    return True


def install_pip():
    """Install pip into embedded Python."""
    print("\n[2/5] Installing pip...")
    
    get_pip_path = BUILD_DIR / "get-pip.py"
    if not get_pip_path.exists():
        if not download_file(GET_PIP_URL, get_pip_path):
            return False
    
    python_exe = PYTHON_DIR / "python.exe"
    result = subprocess.run(
        [str(python_exe), str(get_pip_path), "--no-warn-script-location"],
        capture_output=True, text=True, cwd=str(PYTHON_DIR)
    )
    
    if result.returncode != 0:
        print(f"  [Error] pip installation failed: {result.stderr}")
        return False
    
    print("  pip installed successfully")
    return True


def install_dependencies():
    """Install minimal dependencies."""
    print("\n[3/5] Installing dependencies...")
    
    python_exe = PYTHON_DIR / "python.exe"
    pip_args = [str(python_exe), "-m", "pip", "install", "--no-warn-script-location"]
    
    for dep in MINIMAL_DEPS:
        print(f"  Installing: {dep}")
        result = subprocess.run(
            pip_args + [dep],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  [Warning] Failed to install {dep}: {result.stderr[:200]}")
    
    print("  Dependencies installed")
    return True


def copy_application():
    """Copy Cynapse application files."""
    print("\n[4/5] Copying application files...")
    
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    
    # Files and directories to copy
    include_items = [
        "cynapse.py",
        "hivemind.py",
        "__init__.py",
        "hivemind",
        "neurons",
        "config",
        "data",
        "temp",
        "assets",
        "airllm",
        "README.md",
        "LICENSE",
    ]
    
    APP_DIR.mkdir(parents=True, exist_ok=True)
    
    for item in include_items:
        src = SCRIPT_DIR / item
        dst = APP_DIR / item
        
        if src.exists():
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                    '__pycache__', '*.pyc', '.git', '*.egg-info', 'build'
                ))
                print(f"  Copied directory: {item}")
            else:
                shutil.copy2(src, dst)
                print(f"  Copied file: {item}")
    
    # Ensure temp/logs exists
    (APP_DIR / "temp" / "logs").mkdir(parents=True, exist_ok=True)
    
    return True


def create_launchers():
    """Create launcher scripts."""
    print("\n[5/5] Creating launcher scripts...")
    
    # Windows batch launcher
    bat_content = '''@echo off
cd /d "%~dp0"
echo ========================================
echo   Cynapse - Ghost Shell Hub
echo ========================================
echo.

set PYTHON_EXE=%~dp0python\\python.exe

if not exist "%PYTHON_EXE%" (
    echo [Error] Python not found at: %PYTHON_EXE%
    echo Please ensure the portable package is complete.
    pause
    exit /b 1
)

"%PYTHON_EXE%" cynapse\\cynapse.py %*

if "%~1"=="" (
    pause
)
'''
    
    bat_path = BUILD_DIR / "run_cynapse.bat"
    bat_path.write_text(bat_content)
    print(f"  Created: {bat_path.name}")
    
    # HiveMind launcher
    hivemind_bat = '''@echo off
cd /d "%~dp0"
echo ========================================
echo   HiveMind - AI Ecosystem Controller
echo ========================================
echo.

set PYTHON_EXE=%~dp0python\\python.exe
"%PYTHON_EXE%" cynapse\\hivemind.py menu
pause
'''
    
    hivemind_path = BUILD_DIR / "run_hivemind.bat"
    hivemind_path.write_text(hivemind_bat)
    print(f"  Created: {hivemind_path.name}")
    
    # Quick README
    readme_content = '''CYNAPSE PORTABLE
================

Quick Start:
1. Double-click "run_cynapse.bat" for the main hub
2. Double-click "run_hivemind.bat" for AI chat features

Requirements:
- Windows 7/8/10/11 (64-bit)
- No Python installation required!

For AI chat features:
- Install Ollama from https://ollama.ai
- Pull a model: ollama pull llama3.2

For more information, see cynapse/README.md
'''
    
    readme_path = BUILD_DIR / "README.txt"
    readme_path.write_text(readme_content)
    print(f"  Created: {readme_path.name}")
    
    return True


def main():
    """Main build process."""
    print("=" * 50)
    print("  CYNAPSE PORTABLE BUILDER")
    print("=" * 50)
    print(f"Python Version: {PYTHON_VERSION}")
    print(f"Output: {BUILD_DIR}")
    
    steps = [
        setup_embedded_python,
        install_pip,
        install_dependencies,
        copy_application,
        create_launchers,
    ]
    
    for step in steps:
        if not step():
            print(f"\n[Error] Build failed at: {step.__name__}")
            return 1
    
    print("\n" + "=" * 50)
    print("  BUILD COMPLETE!")
    print("=" * 50)
    print(f"\nPortable distribution created at:")
    print(f"  {BUILD_DIR}")
    print(f"\nTo deploy:")
    print(f"  1. Copy the 'portable' folder to a USB drive")
    print(f"  2. Run 'run_cynapse.bat' on any Windows PC")
    
    # Calculate size
    total_size = sum(f.stat().st_size for f in BUILD_DIR.rglob('*') if f.is_file())
    print(f"\nTotal size: {total_size / (1024*1024):.1f} MB")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
