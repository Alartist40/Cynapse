import customtkinter as ctk
import logging
from modules.developer_setup import DeveloperSetupFrame
from modules.system_info import SystemInfoFrame
from modules.it_support import ITSupportFrame
from modules.tweaks import TweaksFrame
from modules.config import ConfigFrame
from modules.updates import UpdatesFrame

class Dashboard(ctk.CTkFrame):
    def __init__(self, parent, logout_callback=None):
        super().__init__(parent)
        self.logout_callback = logout_callback
        
        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        self.setup_content_area()
        
        # Default to first tab
        self.select_nav_item("install")

    def setup_sidebar(self):
        """Create the sidebar with navigation buttons"""
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(10, weight=1) # Spacer at bottom

        # Logo / Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="dev_Ale", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Navigation Buttons
        self.nav_buttons = {}
        
        nav_items = [
            ("install", "Install"),
            ("tweaks", "Tweaks"),
            ("config", "Config"),
            ("updates", "Updates"),
            ("system", "System Info"),
            ("support", "IT Support") # Legacy feature
        ]
        
        for i, (key, text) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=text,
                height=40,
                corner_radius=10,
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                command=lambda k=key: self.select_nav_item(k)
            )
            btn.grid(row=i+1, column=0, padx=10, pady=5, sticky="ew")
            self.nav_buttons[key] = btn

        # Appearance Mode switch at bottom
        self.appearance_mode_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Appearance Mode:", 
            anchor="w"
        )
        self.appearance_mode_label.grid(row=11, column=0, padx=20, pady=(10, 0))
        
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(
            self.sidebar_frame, 
            values=["System", "Light", "Dark"],
            command=self.change_appearance_mode_event
        )
        self.appearance_mode_optionemenu.grid(row=12, column=0, padx=20, pady=(10, 20))
        # Set default value
        self.appearance_mode_optionemenu.set("Dark") 

    def setup_content_area(self):
        """Create the main area where views will be swapped"""
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # Store active frames to avoid recreating them constantly (optional optimization)
        self.frames = {}

    def select_nav_item(self, key):
        """Handle navigation item selection"""
        # Update selection visual
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")
        
        # Show content
        self.show_frame(key)

    def show_frame(self, key):
        """Display the requested frame in the content area"""
        # Clear current content
        for widget in self.content_frame.winfo_children():
            widget.grid_forget()
            
        if key not in self.frames:
            # Lazy load frames
            if key == "install":
                self.frames[key] = DeveloperSetupFrame(self.content_frame, lambda: None)
            elif key == "system":
                self.frames[key] = SystemInfoFrame(self.content_frame, lambda: None)
            elif key == "support":
                self.frames[key] = ITSupportFrame(self.content_frame, lambda: None)
            elif key == "tweaks":
                self.frames[key] = TweaksFrame(self.content_frame)
            elif key == "config":
                self.frames[key] = ConfigFrame(self.content_frame)
            elif key == "updates":
                self.frames[key] = UpdatesFrame(self.content_frame)
            else:
                self.frames[key] = self.create_placeholder("Unknown Module")
        
        # Grid the frame
        frame = self.frames[key]
        frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure expansion
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

    def create_placeholder(self, text):
        frame = ctk.CTkFrame(self.content_frame)
        label = ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=20))
        label.place(relx=0.5, rely=0.5, anchor="center")
        return frame

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
