import customtkinter as ctk
import threading
import os

class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, runner):
        super().__init__(master)
        self.runner = runner
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Spacer
        self.grid_rowconfigure(2, weight=1) # Spacer
        
        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.grid(row=1, column=0)
        
        self.panic_btn = ctk.CTkButton(
            self.center_frame, 
            text="PANIC BUTTON\nFix my PC", 
            font=ctk.CTkFont(size=24, weight="bold"),
            fg_color="#d32f2f", 
            hover_color="#b71c1c",
            width=250,
            height=250,
            corner_radius=125, # Circle
            command=self.on_panic
        )
        self.panic_btn.pack(pady=20)
        
        self.status_label = ctk.CTkLabel(self.center_frame, text="Ready to fix", font=ctk.CTkFont(size=16))
        self.status_label.pack(pady=10)
        
        self.dry_run_var = ctk.BooleanVar(value=runner.dry_run)
        self.dry_run_chk = ctk.CTkCheckBox(self.center_frame, text="Dry-Run Mode (Simulation only, no changes)", variable=self.dry_run_var, command=self.toggle_dry_run)
        self.dry_run_chk.pack(pady=10)

    def toggle_dry_run(self):
        self.runner.dry_run = self.dry_run_var.get()

    def on_panic(self):
        self.panic_btn.configure(state="disabled", fg_color="#C62828")
        threading.Thread(target=self.run_panic_sequence, daemon=True).start()
        
    def run_panic_sequence(self):
        commands_file = os.path.join("commands", "win", "maintenance.yaml")
        if not os.path.exists(commands_file):
            # Fallback path logic if running from root vs src (simplified for now)
            # Try absolute path or relative from cwd
             if os.path.exists(os.path.join("my", "commands", "win", "maintenance.yaml")):
                 commands_file = os.path.join("my", "commands", "win", "maintenance.yaml")
        
        def update_status(text):
            self.status_label.configure(text=text)
            
        update_status("Starting maintenance...")
        self.runner.run_recipe(commands_file, progress_callback=update_status)
        update_status("All done! System cleaned.")
        
        self.panic_btn.configure(state="normal", fg_color="#d32f2f")
