import customtkinter as ctk
import logging
import subprocess
import threading
from tkinter import messagebox

class UpdatesFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.setup_ui()
        
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        title = ctk.CTkLabel(header_frame, text="Windows Updates", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left")
        
        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        
        self.status_label = ctk.CTkLabel(content, text="Current Status: Unknown", font=ctk.CTkFont(size=16))
        self.status_label.pack(pady=20)
        
        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(btn_frame, text="Disable Updates", command=lambda: self.set_updates("disable"), 
                     height=50, width=200, fg_color="#c0392b", hover_color="#e74c3c").grid(row=0, column=0, padx=10)
                     
        ctk.CTkButton(btn_frame, text="Security Only", command=lambda: self.set_updates("security"), 
                     height=50, width=200, fg_color="#f39c12", hover_color="#f1c40f").grid(row=0, column=1, padx=10)
                     
        ctk.CTkButton(btn_frame, text="Enable All", command=lambda: self.set_updates("enable"), 
                     height=50, width=200, fg_color="#27ae60", hover_color="#2ecc71").grid(row=0, column=2, padx=10)

        self.check_status()

    def check_status(self):
        # Check wuauserv service status
        try:
            res = subprocess.run("sc query wuauserv", shell=True, capture_output=True, text=True)
            if "RUNNING" in res.stdout:
                self.status_label.configure(text="Current Status: ✅ Updates Enabled (Running)", text_color="green")
            else:
                self.status_label.configure(text="Current Status: ❌ Updates Disabled/Stopped", text_color="red")
        except:
             self.status_label.configure(text="Current Status: Unknown")

    def set_updates(self, mode):
        threading.Thread(target=self.run_update_tweak, args=(mode,), daemon=True).start()

    def run_update_tweak(self, mode):
        try:
            if mode == "disable":
                subprocess.run("net stop wuauserv", shell=True)
                subprocess.run("sc config wuauserv start= disabled", shell=True)
            elif mode == "enable":
                subprocess.run("sc config wuauserv start= auto", shell=True)
                subprocess.run("net start wuauserv", shell=True)
            elif mode == "security":
                # Complex registry hacks usually, for now just enable
                subprocess.run("sc config wuauserv start= manual", shell=True)
            
            self.after(0, self.check_status)
            self.after(0, lambda: messagebox.showinfo("Success", f"Updates set to: {mode}"))
        except Exception as e:
            logging.error(f"Update tweak error: {e}")
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
