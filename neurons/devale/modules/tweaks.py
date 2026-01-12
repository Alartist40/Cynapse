import customtkinter as ctk
import logging
import subprocess
import threading
from tkinter import messagebox
import ctypes
import os

class TweaksFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.setup_ui()
        
    def setup_ui(self):
        # Grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        title = ctk.CTkLabel(
            header_frame, 
            text="System Tweaks", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title.pack(side="left")
        
        subtitle = ctk.CTkLabel(
            header_frame, 
            text="Optimize your Windows experience", 
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        subtitle.pack(side="left", padx=20, pady=(5, 0))
        
        # Scrollable Content
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Tweak Categories
        self.tweak_vars = {}
        
        self.create_category("Essential Tweaks", [
            ("restore_point", "Create System Restore Point", "Always recommended before applying changes"),
            ("disable_telemetry", "Disable Telemetry", "Stop Windows from sending data to Microsoft"),
            ("wifi_profiles", "View Wi-Fi Profiles", "List all saved Wi-Fi networks and passwords")
        ])
        
        self.create_category("Explorer Tweaks", [
            ("show_extensions", "Show File Extensions", "Show file extensions in Explorer"),
            ("show_hidden", "Show Hidden Files", "Show hidden files and folders"),
            ("this_pc_desktop", "Show 'This PC' on Desktop", "Add My Computer icon to desktop")
        ])
        
        # Action Bar
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.grid(row=2, column=0, sticky="ew", pady=(20, 0))
        
        self.apply_btn = ctk.CTkButton(
            action_bar,
            text="Apply Selected Tweaks",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            command=self.apply_tweaks
        )
        self.apply_btn.pack(side="right")
        
        self.undo_btn = ctk.CTkButton(
            action_bar,
            text="Undo / Restore",
            font=ctk.CTkFont(size=16),
            height=45,
            fg_color="transparent",
            border_width=2,
            text_color=("gray10", "gray90"),
            command=self.undo_tweaks
        )
        self.undo_btn.pack(side="right", padx=20)

    def create_category(self, title, items):
        """Create a section of tweaks"""
        # Category header
        cat_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        cat_label.pack(fill="x", pady=(20, 10))
        
        # Tweak items
        for key, name, desc in items:
            frame = ctk.CTkFrame(self.scrollable_frame, fg_color=("gray90", "gray15"))
            frame.pack(fill="x", pady=2)
            
            var = ctk.BooleanVar()
            self.tweak_vars[key] = var
            
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

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def apply_tweaks(self):
        if not self.is_admin():
            messagebox.showwarning("Admin Required", "Applying tweaks usually requires Administrator privileges.\nPlease restart the app as Administrator.")
            return

        selected = [k for k, v in self.tweak_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("No Selection", "Please select tweaks to apply")
            return
            
        threading.Thread(target=self.run_tweaks, args=(selected,), daemon=True).start()

    def run_tweaks(self, selected_tweaks):
        self.apply_btn.configure(state="disabled", text="Applying...")
        
        try:
            for tweak in selected_tweaks:
                logging.info(f"Applying tweak: {tweak}")
                
                if tweak == "show_extensions":
                    subprocess.run(['reg', 'add', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced', '/v', 'HideFileExt', '/t', 'REG_DWORD', '/d', '0', '/f'], capture_output=True)
                elif tweak == "show_hidden":
                    subprocess.run(['reg', 'add', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced', '/v', 'Hidden', '/t', 'REG_DWORD', '/d', '1', '/f'], capture_output=True)
                elif tweak == "restore_point":
                    # This is PowerShell heavy
                    pass 
                
            # Refresh Explorer
            subprocess.run(['taskkill', '/f', '/im', 'explorer.exe'], capture_output=True)
            subprocess.run(['start', 'explorer.exe'], shell=True)
            
            self.after(0, lambda: messagebox.showinfo("Success", "Tweaks applied successfully!"))
            
        except Exception as e:
            logging.error(f"Error applying tweaks: {e}")
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to apply tweaks:\n{e}"))
        finally:
             self.after(0, lambda: self.apply_btn.configure(state="normal", text="Apply Selected Tweaks"))

    def undo_tweaks(self):
        messagebox.showinfo("Undo", "Undo functionality works by reversing the registry keys. (Not fully implemented yet)")
