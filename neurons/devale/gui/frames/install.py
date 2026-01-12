import customtkinter as ctk
import json
import os
import threading
import subprocess
from lib.helpers import get_resource_path

class InstallFrame(ctk.CTkFrame):
    def __init__(self, master, runner):
        super().__init__(master)
        self.runner = runner
        self.apps_data = {}
        self.selected_apps = set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(10, 5))
        
        title = ctk.CTkLabel(header, text="App Store (Winget)", font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(side="left", padx=10)
        
        self.search_var = ctk.StringVar()
        self.search_var.trace("w", self.update_list)
        search_entry = ctk.CTkEntry(header, placeholder_text="Search apps...", textvariable=self.search_var, width=250)
        search_entry.pack(side="right", padx=10)

        # Controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=1, column=0, sticky="ew", pady=5)
        
        self.install_btn = ctk.CTkButton(ctrl_frame, text="Install Selected (0)", command=self.run_install, state="disabled")
        self.install_btn.pack(side="right", padx=10)

        # Tab view for categories
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        # Start loading in background
        self.log("Loading app catalog...")
        threading.Thread(target=self.load_data, daemon=True).start()

    def log(self, text):
        # Log to global console ONLY
        if hasattr(self.runner, 'log'):
             self.runner.log(f"[AppStore] {text}")

    def load_data(self):
        json_path = get_resource_path(os.path.join("data", "applications.json"))
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                self.apps_data = json.load(f)
            
            # Group by category
            self.categories = {}
            for key, app in self.apps_data.items():
                cat = app.get('category', 'Uncategorized')
                if cat not in self.categories:
                    self.categories[cat] = []
                # store key for lookup
                app['key'] = key
                self.categories[cat].append(app)
            
            # Schedule UI update on main thread
            self.after(0, self.create_category_tabs)
            self.after(0, lambda: self.log(f"Catalog loaded: {len(self.apps_data)} apps found."))
            
        except Exception as e:
            self.after(0, lambda: self.log(f"Error loading apps data: {e}"))

    def create_category_tabs(self):
        # Create tabs sorted by name
        for cat in sorted(self.categories.keys()):
            self.tabview.add(cat)
            self.build_app_list(cat)

    def build_app_list(self, category):
        tab = self.tabview.tab(category)
        tab.grid_columnconfigure(0, weight=1)
        
        # Scrollable frame inside tab
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        apps = self.categories[category]
        for app in apps:
            # We use a frame for each app row
            row = ctk.CTkFrame(scroll, fg_color=("gray95", "gray20"))
            row.pack(fill="x", pady=2, padx=5)
            
            # Checkbox
            var = ctk.BooleanVar()
            cb = ctk.CTkCheckBox(
                row, 
                text=app.get('content', app['key']), 
                variable=var,
                command=lambda k=app['key'], v=var: self.toggle_app(k, v)
            )
            cb.pack(side="left", padx=10, pady=10)
            
            # Description (truncated)
            desc = app.get('description', '')
            if len(desc) > 60: desc = desc[:57] + "..."
            lbl = ctk.CTkLabel(row, text=desc, text_color="gray")
            lbl.pack(side="left", padx=10)

    def update_list(self, *args):
        # Search not fully implemented in this matching step due to complexity of tab updates
        pass

    def toggle_app(self, key, var):
        if var.get():
            self.selected_apps.add(key)
        else:
            self.selected_apps.discard(key)
        
        count = len(self.selected_apps)
        self.install_btn.configure(text=f"Install Selected ({count})", state="normal" if count > 0 else "disabled")

    def run_install(self):
        self.install_btn.configure(state="disabled")
        threading.Thread(target=self._install_thread, daemon=True).start()

    def _install_thread(self):
        total = len(self.selected_apps)
        current = 0
        
        # Update Winget Source first to prevent hash mismatch
        self.log("Updating Winget sources...")
        self.runner.run_step({'cmd': 'winget source update', 'friendly': 'Updating Winget Source', 'timeout': 120})
        
        for key in list(self.selected_apps):
            current += 1
            app = self.apps_data[key]
            name = app.get('content', key)
            winget_id = app.get('winget')
            
            self.log(f"[{current}/{total}] Installing {name} ({winget_id})...")
            
            if not winget_id or winget_id == "na":
                self.log(f"  -> Skipped (No Winget ID)")
                continue
                
            # Use runner to leverage streaming and encoding fixes
            # Refactored to Legacy Method: shell=False, list args, no -e
            # cmd = f"winget install --id {winget_id} -e --silent --accept-source-agreements --accept-package-agreements"
            
            cmd_list = [
                'winget', 'install', '--id', winget_id, 
                '--silent', 
                '--accept-package-agreements', 
                '--accept-source-agreements'
            ]
            
            self.runner.log(f"Installing {name} (Native Mode)...")
            success, output = self.runner.run_native_cmd(cmd_list)
            
            if success:
                self.log(f"  -> Success")
            else:
                self.log(f"  -> Failed") # Output is already in global log
        
        self.log("Batch installation complete.")
        self.selected_apps.clear()
        
        # Reset UI
        self.after(0, lambda: self.install_btn.configure(text="Install Selected (0)", state="disabled"))
