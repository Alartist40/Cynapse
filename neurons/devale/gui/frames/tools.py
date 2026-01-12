import customtkinter as ctk
import os
import threading
import subprocess
from lib.helpers import get_resource_path

class ToolsFrame(ctk.CTkFrame):
    def __init__(self, master, runner):
        super().__init__(master)
        self.runner = runner
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        title = ctk.CTkLabel(self, text="Utilities & Tools", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=20, sticky="w")
        
        self.tools_container = ctk.CTkScrollableFrame(self, label_text="Available Tools")
        self.tools_container.grid(row=1, column=0, sticky="nsew")
        self.tools_container.grid_columnconfigure(0, weight=1)
        
        # Quick Actions Bar
        quick_frame = ctk.CTkFrame(self, fg_color="transparent")
        quick_frame.grid(row=2, column=0, sticky="ew", pady=10)
        
        btn_tm = ctk.CTkButton(quick_frame, text="Open Task Manager", command=lambda: os.system("taskmgr"), fg_color="#455A64")
        btn_tm.pack(side="left", padx=5)

        btn_temp = ctk.CTkButton(quick_frame, text="Clean Temp", command=self.open_temp_cleaner, fg_color="#D32F2F")
        btn_temp.pack(side="left", padx=5)

        btn_restore = ctk.CTkButton(quick_frame, text="Create Restore Point", command=self.create_restore_point, fg_color="#F57C00")
        btn_restore.pack(side="left", padx=5)

        self.load_tools()

    def log(self, text):
        if hasattr(self.runner, 'log'):
            self.runner.log(f"[Tools] {text}")

    def create_restore_point(self):
        # User requested "Manual" option that runs visibly/natively
        # SystemPropertiesProtection.exe opens the native Restore Point dialog
        # Requires elevation to work properly
        self.log("Opening System Protection properties (Admin)...")
        try:
            import ctypes
            # ShellExecute with "runas" triggers UAC prompt
            ctypes.windll.shell32.ShellExecuteW(None, "runas", "SystemPropertiesProtection.exe", None, None, 1)
            self.log("Window opened (Elevation requested).")
        except Exception as e:
            self.log(f"Error opening properties: {e}")

    def open_temp_cleaner(self):
        # User requested "Manual" option that runs visibly/natively
        # cleanmgr.exe opens the native Disk Cleanup dialog
        self.log("Opening Disk Cleanup...")
        try:
            subprocess.Popen("cleanmgr")
            self.log("Window opened.")
        except Exception as e:
            self.log(f"Error opening cleanmgr: {e}")

    def load_tools(self):
        categories = ["security", "tweaks", "maintenance", "network"]
        row = 0
        
        self.tools_container.grid_columnconfigure(0, weight=1) # Ensure container expands

        for cat in categories:
            # Header
            lbl = ctk.CTkLabel(self.tools_container, text=cat.upper(), font=ctk.CTkFont(size=14, weight="bold"))
            lbl.grid(row=row, column=0, sticky="w", padx=10, pady=(15, 5))
            row += 1
            
            yaml_rel = os.path.join("commands", "win", f"{cat}.yaml")
            commands = self.runner.load_commands(yaml_rel)
            
            if not commands:
                err_lbl = ctk.CTkLabel(self.tools_container, text="No commands found", text_color="gray")
                err_lbl.grid(row=row, column=0, sticky="w", padx=20)
                row += 1
                continue
                
            btn_frame = ctk.CTkFrame(self.tools_container, fg_color="transparent")
            btn_frame.grid(row=row, column=0, sticky="ew", padx=10)
            btn_frame.grid_columnconfigure((0, 1), weight=1) # 2 columns expand equally
            
            for i, cmd in enumerate(commands):
                btn = ctk.CTkButton(
                    btn_frame, 
                    text=cmd['name'], 
                    command=lambda c=cmd: self.run_single_tool(c),
                    height=35
                )
                r = i // 2
                c = i % 2
                btn.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            
            row += 1

    def run_single_tool(self, cmd_step):
        threading.Thread(target=self._run_tool, args=(cmd_step,), daemon=True).start()

    def _run_tool(self, step):
        self.log(f"--- Running {step['name']} ---")
        success, output = self.runner.run_step(step)
        if success:
            self.log(f"SUCCESS:\n{output}")
        else:
            self.log(f"FAILED:\n{output}")
        self.log("-" * 30)
