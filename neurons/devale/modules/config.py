import customtkinter as ctk
import logging
import subprocess
import threading
from tkinter import messagebox, simpledialog
import ctypes

class ConfigFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.setup_ui()
        
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        title = ctk.CTkLabel(header_frame, text="System Configuration", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left")
        
        subtitle = ctk.CTkLabel(
            header_frame, 
            text="Manage Windows Features and Settings", 
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        subtitle.pack(side="left", padx=20, pady=(5, 0))
        
        # Content
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Features
        self.feature_vars = {}
        
        self.create_section("Windows Features", [
            ("NetFx3", "NET Framework 3.5", "Required for many older apps"),
            ("Microsoft-Hyper-V-All", "Hyper-V", "Virtualization Platform"),
            ("Subsystem-Linux", "Windows Subsystem for Linux", "Run Linux on Windows")
        ])
        
        self.create_section("Power Configuration", [
            ("Hibernate", "Enable Hibernate", "Show Hibernate in Power Menu"),
            ("UltimatePerformance", "Ultimate Performance Mode", "Enable High Performance Power Plan")
        ])

        # Action Bar
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        
        self.apply_btn = ctk.CTkButton(
            action_bar,
            text="Apply Configuration",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            command=self.apply_config
        )
        self.apply_btn.pack(side="right")

    def create_section(self, title, items):
        """Create a section of features"""
        cat_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        cat_label.pack(fill="x", pady=(20, 10))
        
        for key, name, desc in items:
            frame = ctk.CTkFrame(self.scrollable_frame, fg_color=("gray90", "gray15"))
            frame.pack(fill="x", pady=2)
            
            var = ctk.BooleanVar()
            self.feature_vars[key] = var
            
            cb = ctk.CTkCheckBox(
                frame,
                text=name,
                variable=var,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            cb.pack(side="left", padx=10, pady=10)
            
            desc_label = ctk.CTkLabel(
                frame,
                text=desc,
                font=ctk.CTkFont(size=12),
                text_color="gray"
            )
            desc_label.pack(side="left", padx=10)

    def apply_config(self):
        # Basic implementation of feature enabling
        selected = [k for k, v in self.feature_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("No Selection", "Please select features to configure")
            return
            
        threading.Thread(target=self.run_config, args=(selected,), daemon=True).start()

    def run_config(self, selected):
        self.apply_btn.configure(state="disabled", text="Working...")
        try:
            for feature in selected:
                logging.info(f"Configuring: {feature}")
                if feature == "NetFx3" or feature == "Microsoft-Hyper-V-All" or feature == "Subsystem-Linux":
                    # Use DISM
                    cmd = f"dism /online /enable-feature /featurename:{feature} /all /norestart"
                    subprocess.run(cmd, shell=True, check=True)
                elif feature == "Hibernate":
                    subprocess.run("powercfg /hibernate on", shell=True)
                elif feature == "UltimatePerformance":
                    subprocess.run("powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61", shell=True)
            
            self.after(0, lambda: messagebox.showinfo("Success", "Configuration applied successfully!"))
        except Exception as e:
            logging.error(f"Config Error: {e}")
            self.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
        finally:
            self.after(0, lambda: self.apply_btn.configure(state="normal", text="Apply Configuration"))
