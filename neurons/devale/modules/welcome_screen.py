import customtkinter as ctk
import logging

class WelcomeScreen(ctk.CTkFrame):
    def __init__(self, parent, navigate_callback):
        super().__init__(parent)
        self.navigate_callback = navigate_callback
        self.setup_ui()
        
    def setup_ui(self):
        # Main container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Welcome title
        title_label = ctk.CTkLabel(
            self,
            text="Welcome to dev_Ale",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=(80, 20))
        
        # Subtitle
        subtitle_label = ctk.CTkLabel(
            self,
            text="Your all-in-one IT support and development environment setup tool",
            font=ctk.CTkFont(size=16)
        )
        subtitle_label.grid(row=1, column=0, pady=(0, 60))
        
        # Features list
        features = [
            "✅ IT Support & Troubleshooting",
            "✅ System Diagnostics & Hardware Info", 
            "✅ Developer Tool Installation",
            "✅ Windows Optimization Tools",
            "✅ Security & Maintenance Utilities"
        ]
        
        for i, feature in enumerate(features):
            feature_label = ctk.CTkLabel(
                self,
                text=feature,
                font=ctk.CTkFont(size=14)
            )
            feature_label.grid(row=2+i, column=0, pady=5)
        
        # Start button
        start_button = ctk.CTkButton(
            self,
            text="Get Started",
            command=self.start_app,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            width=200
        )
        start_button.grid(row=7, column=0, pady=(40, 20))
        
        # Version info
        version_label = ctk.CTkLabel(
            self,
            text="dev_Ale v1.0 - Windows Edition\nYour IT Assistant & Developer Setup Tool",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        version_label.grid(row=8, column=0, pady=(20, 20))
        
    def start_app(self):
        """Handle start button click"""
        logging.info("User started dev_Ale from welcome screen")
        self.navigate_callback()