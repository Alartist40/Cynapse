import customtkinter as ctk
try:
    import psutil
except ImportError:
    psutil = None
import subprocess
import logging
from tkinter import messagebox
import ctypes
import os
import sys

class ITSupportFrame(ctk.CTkFrame):
    def __init__(self, parent, navigate_back_callback):
        super().__init__(parent)
        self.navigate_back_callback = navigate_back_callback
        self.setup_ui()
        
    def setup_ui(self):
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            self,
            text="IT Support - How can I help?",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=(20, 30))
        
        # Create a scrollable frame for the content
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # IT Support Options
        options = [
            ("🔄 Is the computer slow?", self.show_slow_computer_options),
            ("🛡️ Do you suspect a virus?", self.show_virus_suspicion_options),
            ("🔧 Other maintenance options", self.show_other_options)
        ]
        
        # Create option buttons
        for i, (text, command) in enumerate(options):
            option_btn = ctk.CTkButton(
                self.scrollable_frame,
                text=text,
                command=command,
                font=ctk.CTkFont(size=16),
                height=50,
                fg_color="#2b2b2b",
                hover_color="#3a3a3a"
            )
            option_btn.grid(row=i, column=0, pady=10, sticky="ew")
        
        
    def show_slow_computer_options(self):
        """Show options for slow computer troubleshooting"""
        logging.info("Showing slow computer options")
        self.clear_scrollable_frame()
        
        # Check storage status
        storage_info = self.check_storage_status()
        
        # Display storage status
        status_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Storage Analysis:",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        status_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        if not storage_info:
            # No storage info available
            no_info_label = ctk.CTkLabel(
                self.scrollable_frame,
                text="Unable to retrieve storage information",
                font=ctk.CTkFont(size=14),
                text_color="orange"
            )
            no_info_label.grid(row=1, column=0, sticky="w", pady=2)
            row_offset = 2
        else:
            for i, (drive, info) in enumerate(storage_info.items(), 1):
                drive_text = f"{drive}: {info['percent']}% used ({info['free_gb']:.1f} GB free)"
                drive_label = ctk.CTkLabel(
                    self.scrollable_frame,
                    text=drive_text,
                    font=ctk.CTkFont(size=14),
                    text_color="red" if info["percent"] > 85 else "yellow" if info["percent"] > 70 else "green"
                )
                drive_label.grid(row=i, column=0, sticky="w", pady=2)
            
            # Recommendations based on storage
            row_offset = len(storage_info) + 1
            
            if any(info["percent"] > 85 for info in storage_info.values()):
                recommendation = "⚠️ Your storage is almost full! This can significantly slow down your computer."
                color = "red"
            elif any(info["percent"] > 70 for info in storage_info.values()):
                recommendation = "ℹ️ Your storage is getting full. Consider cleaning up some space."
                color = "yellow"
            else:
                recommendation = "✅ Your storage looks good. The slowness might be from other factors."
                color = "green"
                
            rec_label = ctk.CTkLabel(
                self.scrollable_frame,
                text=recommendation,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=color
            )
            rec_label.grid(row=row_offset, column=0, sticky="w", pady=(10, 5))
            row_offset += 1
        
        # Action buttons for slow computer
        actions = [
            ("🗑️ Clear temporary files", self.clear_temp_files),
            ("📊 Open Task Manager", self.open_task_manager),
            ("🔄 Restart computer", self.suggest_restart),
            ("🔍 Check startup programs", self.check_startup_programs),
            ("🛠️ Performance troubleshooting", self.performance_troubleshooting)
        ]
        
        for i, (text, command) in enumerate(actions, row_offset):
            action_btn = ctk.CTkButton(
                self.scrollable_frame,
                text=text,
                command=command,
                font=ctk.CTkFont(size=14),
                height=40
            )
            action_btn.grid(row=i, column=0, pady=5, sticky="ew")
        
        # Back to IT Support menu
        back_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="Back to IT Support Menu",
            command=self.setup_ui,
            font=ctk.CTkFont(size=14),
            height=40
        )
        back_btn.grid(row=row_offset + len(actions), column=0, pady=(20, 10), sticky="ew")
        
    def show_virus_suspicion_options(self):
        """Show options for virus suspicion"""
        logging.info("Showing virus suspicion options")
        self.clear_scrollable_frame()
        
        warning_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="⚠️ Important: Run these tools with caution",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="red"
        )
        warning_label.grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        info_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="These tools can help identify and remove malware:",
            font=ctk.CTkFont(size=14)
        )
        info_label.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        # Security tools
        security_tools = [
            ("🛡️ Run Windows Malicious Software Removal Tool (MRT)", self.run_mrt),
            ("🔍 Run System File Checker (sfc /scannow)", self.run_sfc),
            ("🔄 Run DISM System Health Scan", self.run_dism),
            ("📊 Check running processes", self.check_running_processes),
            ("🔒 Run Windows Security quick scan", self.run_windows_security_scan)
        ]
        
        for i, (text, command) in enumerate(security_tools, 2):
            tool_btn = ctk.CTkButton(
                self.scrollable_frame,
                text=text,
                command=command,
                font=ctk.CTkFont(size=14),
                height=40,
                fg_color="#8B0000",
                hover_color="#A00000"
            )
            tool_btn.grid(row=i, column=0, pady=5, sticky="ew")
        
        # Additional security advice
        advice_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="\nAdditional Security Tips:\n• Keep Windows Defender updated\n• Avoid suspicious emails and downloads\n• Use strong, unique passwords\n• Enable Windows Firewall",
            font=ctk.CTkFont(size=12),
            text_color="yellow"
        )
        advice_label.grid(row=len(security_tools) + 2, column=0, sticky="w", pady=(10, 0))
        
        # Back to IT Support menu
        back_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="Back to IT Support Menu",
            command=self.setup_ui,
            font=ctk.CTkFont(size=14),
            height=40
        )
        back_btn.grid(row=len(security_tools) + 3, column=0, pady=(20, 10), sticky="ew")
        
    def show_other_options(self):
        """Show other maintenance options"""
        logging.info("Showing other maintenance options")
        self.clear_scrollable_frame()
        
        info_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Additional maintenance tools:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        info_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        maintenance_tools = [
            ("🧹 Disk Cleanup", self.run_disk_cleanup),
            ("🔧 System Information", self.show_system_info),
            ("📡 Network Troubleshooter", self.run_network_troubleshooter),
            ("⚙️ System Configuration", self.open_system_config),
            ("🔍 Check for Windows Updates", self.check_windows_updates),
            ("📈 Resource Monitor", self.open_resource_monitor)
        ]
        
        for i, (text, command) in enumerate(maintenance_tools, 1):
            tool_btn = ctk.CTkButton(
                self.scrollable_frame,
                text=text,
                command=command,
                font=ctk.CTkFont(size=14),
                height=40
            )
            tool_btn.grid(row=i, column=0, pady=5, sticky="ew")
        
        # Back to IT Support menu
        back_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="Back to IT Support Menu",
            command=self.setup_ui,
            font=ctk.CTkFont(size=14),
            height=40
        )
        back_btn.grid(row=len(maintenance_tools) + 2, column=0, pady=(20, 10), sticky="ew")
        
    def clear_scrollable_frame(self):
        """Clear all widgets from the scrollable frame"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
    
    def check_storage_status(self):
        """Check storage usage for all drives"""
        try:
            storage_info = {}
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                if 'cdrom' in partition.opts or partition.fstype == '':
                    continue
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    free_gb = usage.free / (1024**3)
                    percent_used = usage.percent
                    
                    storage_info[partition.device] = {
                        'free_gb': free_gb,
                        'percent': percent_used
                    }
                except (PermissionError, OSError) as e:
                    logging.warning(f"Could not access partition {partition.device}: {e}")
                    continue
                    
            return storage_info
        except Exception as e:
            logging.error(f"Error checking storage status: {e}")
            return {}
    
    def clear_temp_files(self):
        """Clear temporary files with user confirmation"""
        if messagebox.askyesno("Confirmation", "This will clear temporary files. Continue?"):
            try:
                # Run disk cleanup for temporary files
                subprocess.run(['cleanmgr', '/sagerun:1'], capture_output=True, shell=True)
                messagebox.showinfo("Success", "Temporary files cleanup initiated.")
                logging.info("Cleared temporary files")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear temporary files: {e}")
                logging.error(f"Temp file cleanup error: {e}")
    
    def open_task_manager(self):
        """Open Windows Task Manager"""
        try:
            subprocess.Popen('taskmgr', shell=True)
            logging.info("Opened Task Manager")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Task Manager: {e}")
            logging.error(f"Task Manager error: {e}")
    
    def suggest_restart(self):
        """Suggest restarting the computer"""
        messagebox.showinfo("Restart Suggestion", 
                          "A simple restart can often fix performance issues.\n\n"
                          "Save your work and restart your computer through the Start menu.")
    
    def check_startup_programs(self):
        """Open startup programs in Task Manager"""
        try:
            subprocess.Popen(['taskmgr', '/0', '/startup'], shell=True)
            logging.info("Opened Startup Programs")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open startup programs: {e}")
            logging.error(f"Startup programs error: {e}")
    
    def performance_troubleshooting(self):
        """Provide performance troubleshooting advice"""
        advice = (
            "Performance Troubleshooting Tips:\n\n"
            "1. Check for background processes in Task Manager\n"
            "2. Disable unnecessary startup programs\n"
            "3. Run Disk Cleanup to free up space\n"
            "4. Check for malware using Windows Security\n"
            "5. Update device drivers\n"
            "6. Adjust visual effects for better performance\n"
            "7. Consider adding more RAM if frequently low on memory\n"
        )
        messagebox.showinfo("Performance Tips", advice)
    
    def run_mrt(self):
        """Run Windows Malicious Software Removal Tool"""
        if messagebox.askyesno("Confirmation", 
                             "This will run the Windows Malicious Software Removal Tool.\n\n"
                             "It may take several minutes. Continue?"):
            try:
                subprocess.Popen('mrt', shell=True)
                logging.info("Started MRT scan")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run MRT: {e}")
                logging.error(f"MRT error: {e}")
    
    def run_sfc(self):
        """Run System File Checker"""
        if messagebox.askyesno("Confirmation", 
                             "This will run System File Checker (sfc /scannow).\n\n"
                             "This requires Administrator privileges and may take time. Continue?"):
            try:
                # Note: This might require running as administrator
                result = subprocess.run(['sfc', '/scannow'], capture_output=True, text=True, shell=True)
                logging.info("Ran SFC scan")
                messagebox.showinfo("SFC Complete", "System File Checker has completed its scan.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run SFC: {e}")
                logging.error(f"SFC error: {e}")
    
    def run_dism(self):
        """Run DISM system health check"""
        if messagebox.askyesno("Confirmation",
                             "This will run DISM system health check.\n\n"
                             "This requires Administrator privileges. Continue?"):
            try:
                result = subprocess.run([
                    'DISM', '/Online', '/Cleanup-Image', '/RestoreHealth'
                ], capture_output=True, text=True, shell=True)
                logging.info("Ran DISM scan")
                messagebox.showinfo("DISM Complete", "DISM system health check completed.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run DISM: {e}")
                logging.error(f"DISM error: {e}")
    
    def run_windows_security_scan(self):
        """Run Windows Security quick scan"""
        if messagebox.askyesno("Confirmation",
                             "This will run a Windows Security quick scan.\n\n"
                             "Continue?"):
            try:
                subprocess.Popen('windowsdefender://threat/', shell=True)
                logging.info("Started Windows Security scan")
                messagebox.showinfo("Scan Started", "Windows Security quick scan has been initiated.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start Windows Security scan: {e}")
                logging.error(f"Windows Security scan error: {e}")
    
    def check_running_processes(self):
        """Show running processes info"""
        try:
            processes = []
            for proc in psutil.process_iter(['name', 'memory_percent', 'cpu_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Show top 10 processes by memory usage
            processes.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)
            
            process_info = "Top processes by memory usage:\n\n"
            for i, proc in enumerate(processes[:10]):
                memory_usage = proc['memory_percent'] or 0
                cpu_usage = proc['cpu_percent'] or 0
                process_info += f"{proc['name']}: {memory_usage:.1f}% memory, {cpu_usage:.1f}% CPU\n"
            
            messagebox.showinfo("Running Processes", process_info)
            logging.info("Checked running processes")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check processes: {e}")
            logging.error(f"Process check error: {e}")
    
    def run_disk_cleanup(self):
        """Run Disk Cleanup utility"""
        try:
            subprocess.Popen('cleanmgr', shell=True)
            logging.info("Started Disk Cleanup")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Disk Cleanup: {e}")
            logging.error(f"Disk Cleanup error: {e}")
    
    def show_system_info(self):
        """Show system information (reusing our existing module)"""
        self.clear_scrollable_frame()
        try:
            # Import here to avoid circular imports
            from modules.system_info import SystemInfoFrame
            # Create a sub-frame for system info within the scrollable frame
            system_frame = SystemInfoFrame(self.scrollable_frame, self.setup_ui)
            system_frame.grid(row=0, column=0, sticky="nsew")
        except Exception as e:
            logging.error(f"Failed to load system info: {e}")
            error_label = ctk.CTkLabel(
                self.scrollable_frame,
                text="Failed to load system information",
                font=ctk.CTkFont(size=14),
                text_color="red"
            )
            error_label.grid(row=0, column=0, pady=20)
    
    def run_network_troubleshooter(self):
        """Run Windows Network Troubleshooter"""
        try:
            subprocess.Popen('msdt.exe /id NetworkDiagnosticsNetworkAdapter', shell=True)
            logging.info("Started Network Troubleshooter")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Network Troubleshooter: {e}")
            logging.error(f"Network troubleshooter error: {e}")
    
    def open_system_config(self):
        """Open System Configuration (msconfig) with admin rights"""
        try:
            # Try to run with elevated privileges
            if ctypes.windll.shell32.IsUserAnAdmin():
                # Already running as admin
                subprocess.Popen('msconfig', shell=True)
            else:
                # Try to run as admin
                ctypes.windll.shell32.ShellExecuteW(None, "runas", "msconfig", None, None, 1)
            logging.info("Opened System Configuration")
        except Exception as e:
            messagebox.showerror(
                "Administrator Rights Required", 
                "System Configuration requires administrator privileges.\n\n"
                "Please right-click on dev_Ale and select 'Run as administrator', "
                "then try this option again."
            )
            logging.error(f"System config error: {e}")
    
    def check_windows_updates(self):
        """Check for Windows Updates"""
        try:
            subprocess.Popen('ms-settings:windowsupdate', shell=True)
            logging.info("Opened Windows Update settings")
            messagebox.showinfo("Windows Update", "Windows Update settings have been opened.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Windows Update: {e}")
            logging.error(f"Windows Update error: {e}")
    
    def open_resource_monitor(self):
        """Open Resource Monitor"""
        try:
            subprocess.Popen('resmon', shell=True)
            logging.info("Opened Resource Monitor")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Resource Monitor: {e}")
            logging.error(f"Resource Monitor error: {e}")