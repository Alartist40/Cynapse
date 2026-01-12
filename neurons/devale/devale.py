import sys
import argparse
import customtkinter as ctk
import platform
import ctypes
from lib.runner import CommandRunner
from gui.app import DevAleGUI

def make_single_instance():
    # Windows only single instance check
    if platform.system() == "Windows":
        mutex_name = "Global\\DevAle_Variable_Mutex_998877"
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, True, mutex_name)
        last_error = kernel32.GetLastError()
        
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            return False
    return True

def main():
    if not make_single_instance():
        print("DevAle is already running.")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="DevAle - Cross Platform System Utility")
    parser.add_argument("--dry-run", action="store_true", help="Simulate commands without execution")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode (not implemented yet)")
    args = parser.parse_args()

    # Initialize Runner
    runner = CommandRunner(dry_run=args.dry_run)

    # Launch GUI
    # Using 'System' can cause delays if it queries OS heavily, ensuring it's fast enough.
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    
    app = DevAleGUI(runner)
    app.mainloop()

if __name__ == "__main__":
    main()
