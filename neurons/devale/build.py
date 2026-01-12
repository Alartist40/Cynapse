import os
import subprocess
import sys
import shutil

def build_app():
    print(">>> Building dev_Ale...")
    print("=" * 50)
    
    # Check if PyInstaller is available
    try:
        import PyInstaller
    except ImportError:
        print("[!] PyInstaller not found! Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller==6.16.0"])

    # Install other requirements to ensure they are available for bundling
    print(">>> Checking and installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    except Exception as e:
        print(f"[!] Warning: Failed to install requirements: {e}")
    
    # Check if required directories exist
    required_dirs = ['data', 'modules']
    for dir in required_dirs:
        if not os.path.exists(dir):
            print(f"[!] Error: '{dir}' directory not found!")
            return
    
    # Clean previous builds
    print(">>> Cleaning previous builds...")
    for folder in ['dist', 'build']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    # Create assets directory if it doesn't exist
    if not os.path.exists('assets'):
        os.makedirs('assets')
    
    print(">>> Building executable...")
    
    # Build command with proper data inclusion
    build_cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=dev_Ale',
        '--onefile',
        '--windowed',
        '--add-data=data/tools.json;data',
        '--add-data=modules;modules',  # Changed from modules/* to capture the whole directory
        '--hidden-import=customtkinter',
        '--hidden-import=psutil',
        '--hidden-import=GPUtil',  # Added GPUtil
        '--hidden-import=ctypes',
        '--hidden-import=json',
        '--hidden-import=logging',
        '--hidden-import=subprocess',
        '--hidden-import=threading',
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.messagebox',
        '--collect-all=customtkinter',
        '--collect-all=GPUtil',  # Collect GPUtil data/libs if any
        '--clean',
        '--noconfirm',
        'main.py'
    ]
    
    # Add icon only if it exists
    if os.path.exists('assets/icon.ico'):
        build_cmd.insert(1, '--icon=assets/icon.ico')
        print("[+] Using custom icon")
    else:
        print("[i] Using default icon (no custom icon found)")
    
    # Run the build
    result = subprocess.run(build_cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("[+] Build complete!")
        print(">>> Your executable: dist/dev_Ale.exe")
        print("\n>>> To share with others:")
        print("   Simply send them the 'dev_Ale.exe' file from the dist folder")
        
        # Test if data files are accessible
        test_data_access()
    else:
        print("[!] Build failed!")

def test_data_access():
    """Test if data files can be accessed in the build"""
    print("\n>>> Testing data file access...")
    
    # Check if tools.json exists and is readable
    try:
        import json
        with open('data/tools.json', 'r') as f:
            data = json.load(f)
            beginner_count = len(data.get('beginner', {}))
            pro_count = len(data.get('professional', {}))
            print(f"[+] tools.json loaded: {beginner_count} beginner, {pro_count} professional categories")
    except Exception as e:
        print(f"[!] Failed to load tools.json: {e}")

if __name__ == "__main__":
    build_app()