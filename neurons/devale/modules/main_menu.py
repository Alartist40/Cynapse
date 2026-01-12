import customtkinter as ctk
import logging

class MainMenu(ctk.CTkFrame):
    def __init__(self, parent, navigate_callback):
        super().__init__(parent)
        self.navigate_callback = navigate_callback
        self.setup_ui()
        
    def setup_ui(self):
        # Use pack for the main container instead of grid
        # Title
        title_label = ctk.CTkLabel(
            self,
            text="How can I help you today?",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(40, 60))
        
        # Create a container frame for the cards
        cards_container = ctk.CTkFrame(self)
        cards_container.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Use grid inside the cards container
        cards_container.grid_columnconfigure((0, 1, 2), weight=1)
        cards_container.grid_rowconfigure(0, weight=1)
        
        # Card 1: IT Support
        self.card_it_support = self.create_clickable_card(
            cards_container, "IT Support", "Troubleshooting and maintenance for your PC", "🔧", "it_support",
            row=0, column=0
        )
        
        # Card 2: Check System
        self.card_check_system = self.create_clickable_card(
            cards_container, "Check System", "Detailed hardware and software information", "💻", "check_system",
            row=0, column=1
        )
        
        # Card 3: Developer Option
        self.card_developer = self.create_clickable_card(
            cards_container, "Developer Option", "Set up your development environment", "⚙️", "developer",
            row=0, column=2
        )
        
        # Back button
        back_btn = ctk.CTkButton(
            self,
            text="Back to Welcome",
            command=self.go_back,
            font=ctk.CTkFont(size=14),
            height=40
        )
        back_btn.pack(pady=(0, 20))
        
    def create_clickable_card(self, parent, title, description, emoji, card_type, row, column):
        """Create a fully clickable card with hover effects"""
        # Create main card frame
        card = ctk.CTkFrame(parent, corner_radius=15, border_width=2, border_color="#2b2b2b")
        card.grid(row=row, column=column, padx=15, pady=15, sticky="nsew")
        
        # Make entire card clickable
        card.bind("<Button-1>", lambda e: self.card_clicked(card_type))
        card.bind("<Enter>", lambda e: self.on_card_hover(card, True))
        card.bind("<Leave>", lambda e: self.on_card_hover(card, False))
        
        # Card content with pack for simplicity
        # Emoji icon
        emoji_label = ctk.CTkLabel(
            card,
            text=emoji,
            font=ctk.CTkFont(size=40)
        )
        emoji_label.pack(pady=(25, 15))
        emoji_label.bind("<Button-1>", lambda e: self.card_clicked(card_type))
        emoji_label.bind("<Enter>", lambda e: self.on_card_hover(card, True))
        emoji_label.bind("<Leave>", lambda e: self.on_card_hover(card, False))
        
        # Title
        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=(0, 10))
        title_label.bind("<Button-1>", lambda e: self.card_clicked(card_type))
        title_label.bind("<Enter>", lambda e: self.on_card_hover(card, True))
        title_label.bind("<Leave>", lambda e: self.on_card_hover(card, False))
        
        # Description
        desc_label = ctk.CTkLabel(
            card,
            text=description,
            font=ctk.CTkFont(size=14),
            wraplength=180
        )
        desc_label.pack(pady=(0, 25), padx=20)
        desc_label.bind("<Button-1>", lambda e: self.card_clicked(card_type))
        desc_label.bind("<Enter>", lambda e: self.on_card_hover(card, True))
        desc_label.bind("<Leave>", lambda e: self.on_card_hover(card, False))
        
        return card
    
    def on_card_hover(self, card, is_hover):
        """Handle card hover effects"""
        if is_hover:
            card.configure(border_color="#3a7ebf", cursor="hand2")
        else:
            card.configure(border_color="#2b2b2b", cursor="")
        
    def card_clicked(self, card_type):
        logging.info(f"Main menu card clicked: {card_type}")
        if card_type == "it_support":
            self.show_it_support()
        elif card_type == "check_system":
            self.show_system_info()
        elif card_type == "developer":
            self.show_developer_setup()
    
    def show_it_support(self):
        """Show the IT Support module"""
        for widget in self.winfo_children():
            widget.destroy()
        
        from modules.it_support import ITSupportFrame
        it_support_frame = ITSupportFrame(self, self.show_main_menu)
        it_support_frame.pack(fill="both", expand=True)
    
    def show_system_info(self):
        """Show the system information module"""
        for widget in self.winfo_children():
            widget.destroy()
        
        from modules.system_info import SystemInfoFrame
        system_frame = SystemInfoFrame(self, self.show_main_menu)
        system_frame.pack(fill="both", expand=True)
    
    def show_developer_setup(self):
        """Show the Developer Setup module"""
        for widget in self.winfo_children():
            widget.destroy()
        
        from modules.developer_setup import DeveloperSetupFrame
        dev_setup_frame = DeveloperSetupFrame(self, self.show_main_menu)
        dev_setup_frame.pack(fill="both", expand=True)
    
    def show_main_menu(self):
        """Show the main menu (recreate it)"""
        for widget in self.winfo_children():
            widget.destroy()
        self.setup_ui()
    
    def go_back(self):
        self.navigate_callback()