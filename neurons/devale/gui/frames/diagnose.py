import customtkinter as ctk
import platform
import psutil
import threading
import subprocess

class DiagnoseFrame(ctk.CTkFrame):
    def __init__(self, master, runner):
        super().__init__(master)
        self.runner = runner
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        title = ctk.CTkLabel(self, text="System Diagnosis", font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=20, sticky="w")
        
        # Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew")
        
        self.tab_overview = self.tabview.add("Overview")
        self.tab_processes = self.tabview.add("Processes")
        self.tab_startup = self.tabview.add("Start-up")
        
        self.setup_overview()
        self.setup_processes()
        self.setup_startup()

    def setup_overview(self):
        self.tab_overview.grid_columnconfigure(0, weight=1)
        self.tab_overview.grid_rowconfigure(0, weight=1) # Expand text area
        
        self.info_text = ctk.CTkTextbox(self.tab_overview, width=600, height=350)
        self.info_text.grid(row=0, column=0, sticky="nsew", pady=10)
        self.info_text.configure(state="disabled")
        
        btn = ctk.CTkButton(self.tab_overview, text="Refresh Specs", command=self.load_info)
        btn.grid(row=1, column=0, pady=10, sticky="ew") # Anchor button
        
        self.load_info()

    def setup_processes(self):
        self.tab_processes.grid_columnconfigure(0, weight=1)
        self.tab_processes.grid_rowconfigure(0, weight=1)
        
        self.proc_text = ctk.CTkTextbox(self.tab_processes, width=600, height=350)
        self.proc_text.grid(row=0, column=0, sticky="nsew", pady=10)
        
        btn = ctk.CTkButton(self.tab_processes, text="Scan Heavy Processes", command=self.load_processes)
        btn.grid(row=1, column=0, pady=10, sticky="ew")

    def setup_startup(self):
        self.tab_startup.grid_columnconfigure(0, weight=1)
        self.tab_startup.grid_rowconfigure(0, weight=1)
        
        self.startup_text = ctk.CTkTextbox(self.tab_startup, width=600, height=350)
        self.startup_text.grid(row=0, column=0, sticky="nsew", pady=10)
        
        btn = ctk.CTkButton(self.tab_startup, text="List Startup Items", command=self.load_startup)
        btn.grid(row=1, column=0, pady=10, sticky="ew")

    def load_info(self):
        threading.Thread(target=self._fetch_info, daemon=True).start()

    def _fetch_info(self):
        info = []
        info.append(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
        info.append(f"Machine: {platform.machine()}")
        info.append(f"Processor: {platform.processor()}")
        info.append("-" * 30)
        
        info.append(f"CPU Usage: {psutil.cpu_percent(interval=1)}%")
        info.append(f"Cores: {psutil.cpu_count(logical=False)} (Physical), {psutil.cpu_count(logical=True)} (Logical)")
        info.append("-" * 30)

        mem = psutil.virtual_memory()
        info.append(f"Memory Total: {mem.total / (1024**3):.2f} GB")
        info.append(f"Memory Used: {mem.used / (1024**3):.2f} GB ({mem.percent}%)")
        
        self.update_text(self.info_text, "\n".join(info))

    def load_processes(self):
        threading.Thread(target=self._fetch_processes, daemon=True).start()

    def _fetch_processes(self):
        self.update_text(self.proc_text, "Scanning processes...")
        procs = []
        for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            try:
                p.info['cpu_percent']  # Trigger lazy load
                procs.append(p.info)
            except: pass
            
        # Sort by memory
        procs.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
        
        lines = ["Top 15 Memory Hogs:\n"]
        for p in procs[:15]:
            lines.append(f"{p['name']}: {p['memory_percent']:.1f}% RAM")
            
        self.update_text(self.proc_text, "\n".join(lines))

    def load_startup(self):
        threading.Thread(target=self._fetch_startup, daemon=True).start()
    
    def _fetch_startup(self):
        self.update_text(self.startup_text, "Querying startup items (via wmic)...")
        try:
            # Simple wmic call to get startup
            cmd = "wmic startup get caption,command"
            creation = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            self.update_text(self.startup_text, creation.stdout)
        except Exception as e:
            self.update_text(self.startup_text, f"Error: {e}")

    def update_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("0.0", "end")
        widget.insert("0.0", text)
        widget.configure(state="disabled")
