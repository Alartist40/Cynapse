import customtkinter as ctk
import platform
from typing import Dict, List
import logging

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available")

# Handle GPUtil import with fallback
try:
    import GPUtil
    GPUTIL_AVAILABLE = True
    logging.info("GPUtil imported successfully")
except ImportError as e:
    logging.warning(f"GPUtil not available: {e}")
    GPUTIL_AVAILABLE = False
except Exception as e:
    logging.warning(f"GPUtil import failed: {e}")
    GPUTIL_AVAILABLE = False

class SystemInfoFrame(ctk.CTkFrame):
    def __init__(self, parent, navigate_back_callback):
        super().__init__(parent)
        self.navigate_back_callback = navigate_back_callback
        logging.info("SystemInfoFrame initialized")
        self.setup_ui()
        self.populate_system_info()
        
    def setup_ui(self):
        logging.info("Setting up System Info UI")
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            self,
            text="System Information",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=(20, 20))
        
        # Create a scrollable frame for the content
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        logging.info("System Info UI setup complete")
        
    def populate_system_info(self):
        logging.info("Starting to populate system information")
        # Get system information
        system_info = self.gather_system_info()
        logging.info(f"System info gathered: {len(system_info)} categories")
        
        # Display each category
        row = 0
        for category, data in system_info.items():
            logging.info(f"Displaying category: {category} with {len(data)} items")
            category_label = ctk.CTkLabel(
                self.scrollable_frame,
                text=category,
                font=ctk.CTkFont(size=18, weight="bold")
            )
            category_label.grid(row=row, column=0, sticky="w", pady=(10, 5))
            row += 1
            
            for key, value in data.items():
                info_text = f"{key}: {value}"
                info_label = ctk.CTkLabel(
                    self.scrollable_frame,
                    text=info_text,
                    font=ctk.CTkFont(size=14),
                    anchor="w"
                )
                info_label.grid(row=row, column=0, sticky="w", padx=(20, 0))
                row += 1
            
            # Add a separator after each category
            separator = ctk.CTkFrame(self.scrollable_frame, height=1, fg_color="gray")
            separator.grid(row=row, column=0, sticky="ew", pady=5)
            row += 1
        
        logging.info(f"Finished populating system info. Total rows: {row}")
        
    def gather_system_info(self) -> Dict[str, Dict[str, str]]:
        """Gather comprehensive system information"""
        logging.info("Gathering system information...")
        info = {}
        
        # CPU Information
        cpu_info = {}
        try:
            cpu_info["Processor"] = platform.processor()
            cpu_info["Cores (Physical)"] = str(psutil.cpu_count(logical=False))
            cpu_info["Cores (Logical)"] = str(psutil.cpu_count(logical=True))
            cpu_info["Architecture"] = platform.architecture()[0]
            
            # Get CPU frequency
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                cpu_info["Max Frequency"] = f"{cpu_freq.max:.2f} MHz"
                cpu_info["Current Frequency"] = f"{cpu_freq.current:.2f} MHz"
        except Exception as e:
            cpu_info["Error"] = f"Unable to retrieve CPU information: {e}"
            logging.error(f"CPU info error: {e}")
        info["CPU"] = cpu_info
        
        # Memory Information
        memory_info = {}
        try:
            memory = psutil.virtual_memory()
            memory_info["Total RAM"] = f"{memory.total / (1024**3):.2f} GB"
            memory_info["Available RAM"] = f"{memory.available / (1024**3):.2f} GB"
            memory_info["Used RAM"] = f"{memory.used / (1024**3):.2f} GB"
            memory_info["RAM Usage"] = f"{memory.percent}%"
        except Exception as e:
            memory_info["Error"] = f"Unable to retrieve memory information: {e}"
            logging.error(f"Memory info error: {e}")
        info["Memory"] = memory_info
        
        # Disk Information
        disk_info = {}
        try:
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info[partition.device] = f"Total: {usage.total / (1024**3):.1f} GB, Free: {usage.free / (1024**3):.1f} GB ({usage.percent}% used)"
                except PermissionError:
                    # Some partitions may not be accessible
                    disk_info[partition.device] = "Access denied"
                    continue
        except Exception as e:
            disk_info["Error"] = f"Unable to retrieve disk information: {e}"
            logging.error(f"Disk info error: {e}")
        info["Disks"] = disk_info
        
        # GPU Information - with fallback for missing GPUtil
        gpu_info = {}
        if GPUTIL_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    for i, gpu in enumerate(gpus):
                        gpu_info[f"GPU {i+1}"] = f"{gpu.name} (VRAM: {gpu.memoryTotal} MB)"
                else:
                    gpu_info["Status"] = "No dedicated GPU detected (using integrated graphics)"
            except Exception as e:
                gpu_info["Status"] = f"GPU detection error: {str(e)[:50]}..."
                logging.error(f"GPU info error: {e}")
        else:
            gpu_info["Status"] = "GPU information unavailable (GPUtil not working)"
            # Try to get basic GPU info from other methods
            try:
                # Fallback GPU detection using platform/wmi
                if platform.system() == "Windows":
                    gpu_info["Note"] = "Using system integrated graphics"
            except:
                pass
        info["GPU"] = gpu_info
        
        # Operating System
        os_info = {}
        try:
            os_info["System"] = platform.system()
            os_info["Version"] = platform.version()
            os_info["Release"] = platform.release()
            os_info["Machine"] = platform.machine()
            os_info["Platform"] = platform.platform()
        except Exception as e:
            os_info["Error"] = f"Unable to retrieve OS information: {e}"
            logging.error(f"OS info error: {e}")
        info["Operating System"] = os_info
        
        # Network Information
        network_info = {}
        try:
            net_io = psutil.net_io_counters()
            network_info["Bytes Sent"] = f"{net_io.bytes_sent / (1024**2):.2f} MB"
            network_info["Bytes Received"] = f"{net_io.bytes_recv / (1024**2):.2f} MB"
        except Exception as e:
            network_info["Error"] = f"Unable to retrieve network information: {e}"
            logging.error(f"Network info error: {e}")
        info["Network"] = network_info
        
        logging.info("System information gathering complete")
        return info