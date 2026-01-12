import customtkinter as ctk
from modules.dashboard import Dashboard
import logging
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

class DevAleApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure main window
        self.title("dev_Ale - WinUtility")
        self.geometry("1100x700") # Wider for sidebar
        self.minsize(900, 600)
        
        # Center the window on screen
        self.center_window()
        
        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Set icon if available
        self.set_window_icon()
        
        # Initialize Dashboard
        self.dashboard = Dashboard(self)
        self.dashboard.pack(fill="both", expand=True)
        
        logging.info("dev_Ale application initialized successfully")
    
    def center_window(self):
        """Center the window on the screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def set_window_icon(self):
        """Set the window icon if available"""
        try:
            icon_path = os.path.join('assets', 'icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                logging.info("Icon file not found, using default")
        except Exception as e:
            logging.warning(f"Could not set window icon: {e}")

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# Set global exception handler
sys.excepthook = handle_exception

if __name__ == "__main__":
    try:
        app = DevAleApp()
        app.mainloop()
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        # Show error message to user
        error_root = ctk.CTk()
        error_root.title("Error - dev_Ale")
        error_label = ctk.CTkLabel(
            error_root, 
            text=f"Failed to start dev_Ale:\n{str(e)}",
            font=ctk.CTkFont(size=14),
            text_color="red"
        )
        error_label.pack(padx=20, pady=20)
        error_root.mainloop()
        raise
