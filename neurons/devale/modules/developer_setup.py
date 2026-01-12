import customtkinter as ctk
import json
import subprocess
import logging
from tkinter import messagebox
import threading
import os
import sys

class DeveloperSetupFrame(ctk.CTkFrame):
    def __init__(self, parent, navigate_back_callback):
        super().__init__(parent)
        self.navigate_back_callback = navigate_back_callback
        self.selected_tools = []
        self.tools_data = self.load_tools_data()
        self.setup_ui()
        
    def load_tools_data(self):
        """Load tools data from JSON file - works in both dev and compiled versions"""
        try:
            # Try multiple possible paths for the data file
            possible_paths = [
                'data/tools.json',  # Development path
                os.path.join(sys._MEIPASS, 'data', 'tools.json') if hasattr(sys, '_MEIPASS') else None,  # Compiled path
                'tools.json'  # Fallback
            ]
            
            tools_data = None
            for path in possible_paths:
                if path and os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            tools_data = json.load(f)
                        logging.info(f"✅ Loaded tools data from: {path}")
                        break
                    except Exception as e:
                        logging.warning(f"Failed to load from {path}: {e}")
                        continue
            
            if tools_data is None:
                logging.error("Could not load tools data from any path, using fallback")
                # Return comprehensive fallback data
                tools_data = {
                    "beginner": {
                        "frontend": ["vscode", "git.git", "nodejs", "google.chrome"],
                        "backend": ["vscode", "git.git", "python", "postman"],
                        "data_science": ["vscode", "git.git", "python", "anaconda"],
                        "mobile": ["vscode", "git.git", "android-studio"],
                        "game_dev": ["vscode", "git.git", "unity"],
                        "devops": ["vscode", "git.git", "docker-desktop"]
                    },
                    "professional": {
                        "frontend": ["vscode", "git.git", "nodejs", "google.chrome", "docker-desktop", "figma", "postman", "github.cli"],
                        "backend": ["vscode", "git.git", "python", "postman", "docker-desktop", "mysql", "redis", "nginx", "wireshark"],
                        "data_science": ["vscode", "git.git", "python", "anaconda", "docker-desktop", "jupyter", "r.project", "tableau.public"],
                        "mobile": ["vscode", "git.git", "android-studio", "flutter", "react-native", "xamarin"],
                        "game_dev": ["vscode", "git.git", "unity", "unreal-engine", "blender", "audacity"],
                        "devops": ["vscode", "git.git", "docker-desktop", "kubernetes-cli", "terraform", "aws-cli", "azure-cli"]
                    }
                }
            
            return tools_data
            
        except Exception as e:
            logging.error(f"Failed to load tools data: {e}")
            # Return comprehensive fallback structure
            return {
                "beginner": {
                    "frontend": ["vscode", "git.git", "nodejs", "google.chrome"],
                    "backend": ["vscode", "git.git", "python", "postman"],
                    "data_science": ["vscode", "git.git", "python", "anaconda"],
                    "mobile": ["vscode", "git.git", "android-studio"],
                    "game_dev": ["vscode", "git.git", "unity"],
                    "devops": ["vscode", "git.git", "docker-desktop"]
                },
                "professional": {
                    "frontend": ["vscode", "git.git", "nodejs", "google.chrome", "docker-desktop", "figma", "postman", "github.cli"],
                    "backend": ["vscode", "git.git", "python", "postman", "docker-desktop", "mysql", "redis", "nginx", "wireshark"],
                    "data_science": ["vscode", "git.git", "python", "anaconda", "docker-desktop", "jupyter", "r.project", "tableau.public"],
                    "mobile": ["vscode", "git.git", "android-studio", "flutter", "react-native", "xamarin"],
                    "game_dev": ["vscode", "git.git", "unity", "unreal-engine", "blender", "audacity"],
                    "devops": ["vscode", "git.git", "docker-desktop", "kubernetes-cli", "terraform", "aws-cli", "azure-cli"]
                }
            }
        
    def setup_ui(self):
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Title
        title_label = ctk.CTkLabel(
            self,
            text="Developer Environment Setup",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, pady=(20, 30))
        
        # Create a scrollable frame for the content
        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # Show skill level selection
        self.show_skill_level_selection()
        
        
    def show_skill_level_selection(self):
        """Show skill level selection (Beginner/Professional)"""
        self.clear_scrollable_frame()
        
        instruction_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Select your skill level:",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        instruction_label.grid(row=0, column=0, pady=(0, 20))
        
        # Beginner button
        beginner_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="🚀 Beginner\nEssential tools to get started",
            command=lambda: self.show_profession_selection("beginner"),
            font=ctk.CTkFont(size=16),
            height=80,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a"
        )
        beginner_btn.grid(row=1, column=0, pady=10, sticky="ew")
        
        # Professional button
        pro_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="💼 Professional\nComprehensive toolkit for experts",
            command=lambda: self.show_profession_selection("professional"),
            font=ctk.CTkFont(size=16),
            height=80,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a"
        )
        pro_btn.grid(row=2, column=0, pady=10, sticky="ew")
        
    def show_profession_selection(self, skill_level):
        """Show profession selection after skill level is chosen"""
        self.skill_level = skill_level
        self.clear_scrollable_frame()
        
        instruction_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="Select your development focus:",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        instruction_label.grid(row=0, column=0, pady=(0, 20))
        
        professions = {
            "frontend": "🌐 Frontend Development\n(Web interfaces, JavaScript, React)",
            "backend": "⚙️ Backend Development\n(Servers, APIs, Databases)",
            "data_science": "📊 Data Science\n(Python, ML, Analytics)",
            "mobile": "📱 Mobile Development\n(Android, iOS, Cross-platform)",
            "game_dev": "🎮 Game Development\n(Unity, Unreal, 3D tools)",
            "devops": "🔧 DevOps\n(Containers, Cloud, Automation)"
        }
        
        # Show all professions for both skill levels
        row = 1
        for profession_key, profession_text in professions.items():
            # Check if this profession exists in our data
            if (self.skill_level in self.tools_data and 
                profession_key in self.tools_data[self.skill_level]):
                
                profession_btn = ctk.CTkButton(
                    self.scrollable_frame,
                    text=profession_text,
                    command=lambda p=profession_key: self.show_tool_selection(p),
                    font=ctk.CTkFont(size=14),
                    height=70,
                    fg_color="#2b2b2b",
                    hover_color="#3a3a3a"
                )
                profession_btn.grid(row=row, column=0, pady=8, sticky="ew")
                row += 1
        
        # If no professions were found, show error
        if row == 1:
            error_label = ctk.CTkLabel(
                self.scrollable_frame,
                text="No profession data available.\nUsing default tools.",
                font=ctk.CTkFont(size=14),
                text_color="orange"
            )
            error_label.grid(row=1, column=0, pady=20)
            
            # Show at least some basic options
            basic_professions = {
                "general": "⚡ General Development\n(Basic tools for all developers)"
            }
            
            for profession_key, profession_text in basic_professions.items():
                profession_btn = ctk.CTkButton(
                    self.scrollable_frame,
                    text=profession_text,
                    command=lambda p=profession_key: self.show_tool_selection(p),
                    font=ctk.CTkFont(size=14),
                    height=70,
                    fg_color="#2b2b2b",
                    hover_color="#3a3a3a"
                )
                profession_btn.grid(row=row, column=0, pady=8, sticky="ew")
                row += 1
        
        # Back to skill level selection
        back_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="Back to Skill Level Selection",
            command=self.show_skill_level_selection,
            font=ctk.CTkFont(size=14),
            height=40
        )
        back_btn.grid(row=row, column=0, pady=(20, 10), sticky="ew")
        
    def show_tool_selection(self, profession):
        """Show tool selection for the chosen profession and skill level"""
        self.profession = profession
        self.clear_scrollable_frame()
        
        # Get tools for this profession and skill level
        available_tools = []
        if (self.skill_level in self.tools_data and 
            profession in self.tools_data[self.skill_level]):
            available_tools = self.tools_data[self.skill_level][profession]
        else:
            # Fallback tools
            available_tools = ["vscode", "git.git", "python"]
            logging.warning(f"No tools found for {self.skill_level}.{profession}, using fallback")
        
        instruction_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=f"Select tools to install for {profession.replace('_', ' ').title()} ({self.skill_level.title()}):",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        instruction_label.grid(row=0, column=0, sticky="w", pady=(0, 20))
        
        # Select All checkbox
        self.select_all_var = ctk.BooleanVar()
        select_all_cb = ctk.CTkCheckBox(
            self.scrollable_frame,
            text="Select All Tools",
            variable=self.select_all_var,
            command=self.toggle_select_all,
            font=ctk.CTkFont(size=14)
        )
        select_all_cb.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        # Tool checkboxes
        self.tool_vars = {}
        row = 2
        
        for tool in available_tools:
            var = ctk.BooleanVar()
            self.tool_vars[tool] = var
            
            tool_cb = ctk.CTkCheckBox(
                self.scrollable_frame,
                text=self.format_tool_name(tool),
                variable=var,
                font=ctk.CTkFont(size=14)
            )
            tool_cb.grid(row=row, column=0, sticky="w", pady=5)
            row += 1
        
        # Install button
        self.install_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="🚀 Install Selected Tools",
            command=self.install_selected_tools,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color="#0C6B3A",
            hover_color="#0E7C43"
        )
        self.install_btn.grid(row=row, column=0, pady=(20, 10), sticky="ew")
        
        # Progress label
        self.progress_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="",
            font=ctk.CTkFont(size=14)
        )
        self.progress_label.grid(row=row + 1, column=0, pady=(10, 5))
        
        # Progress bar (initially hidden)
        self.progress_bar = ctk.CTkProgressBar(self.scrollable_frame)
        self.progress_bar.grid(row=row + 2, column=0, pady=(5, 10), sticky="ew")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()  # Hide initially
        
        # Back to profession selection
        back_btn = ctk.CTkButton(
            self.scrollable_frame,
            text="Back to Profession Selection",
            command=lambda: self.show_profession_selection(self.skill_level),
            font=ctk.CTkFont(size=14),
            height=40
        )
        back_btn.grid(row=row + 3, column=0, pady=(10, 10), sticky="ew")
        
    def toggle_select_all(self):
        """Toggle all tool checkboxes based on Select All state"""
        for var in self.tool_vars.values():
            var.set(self.select_all_var.get())
    
    def format_tool_name(self, tool_id):
        """Format tool ID for display"""
        name_map = {
            "vscode": "Visual Studio Code",
            "git.git": "Git",
            "nodejs": "Node.js",
            "google.chrome": "Google Chrome",
            "python": "Python",
            "postman": "Postman",
            "anaconda": "Anaconda",
            "docker-desktop": "Docker Desktop",
            "figma": "Figma",
            "github.cli": "GitHub CLI",
            "mysql": "MySQL",
            "redis": "Redis",
            "nginx": "Nginx",
            "wireshark": "Wireshark",
            "jupyter": "Jupyter",
            "r.project": "R Programming Language",
            "tableau.public": "Tableau Public",
            "android-studio": "Android Studio",
            "flutter": "Flutter",
            "react-native": "React Native",
            "xamarin": "Xamarin",
            "unity": "Unity",
            "unreal-engine": "Unreal Engine",
            "blender": "Blender",
            "audacity": "Audacity",
            "kubernetes-cli": "Kubernetes CLI",
            "terraform": "Terraform",
            "aws-cli": "AWS CLI",
            "azure-cli": "Azure CLI"
        }
        return name_map.get(tool_id, tool_id)
    
    def install_selected_tools(self):
        """Install the selected tools using winget"""
        selected_tools = [tool for tool, var in self.tool_vars.items() if var.get()]
        
        if not selected_tools:
            messagebox.showwarning("No Selection", "Please select at least one tool to install.")
            return
        
        if not messagebox.askyesno("Confirmation", 
                                 f"This will install {len(selected_tools)} tool(s) using winget.\n\n"
                                 "This may take several minutes. Continue?"):
            return
        
        # Disable the install button during installation
        self.install_btn.configure(state="disabled")
        
        # Show progress bar
        self.progress_bar.grid()
        self.progress_bar.set(0)
        
        # Start installation in a separate thread to avoid freezing the UI
        thread = threading.Thread(target=self.run_installation, args=(selected_tools,))
        thread.daemon = True
        thread.start()
    
    def run_installation(self, tools):
        """Run the actual installation process"""
        successful_installs = []
        failed_installs = []
        
        for i, tool in enumerate(tools):
            progress_percent = (i / len(tools)) * 100
            self.update_progress(f"Installing {self.format_tool_name(tool)}... ({i+1}/{len(tools)})")
            self.update_progress_bar(progress_percent)
            
            try:
                # Use winget to install the tool
                result = subprocess.run(
                    ['winget', 'install', '--id', tool, '--silent', '--accept-package-agreements', '--accept-source-agreements'],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per tool
                )
                
                if result.returncode == 0:
                    successful_installs.append(tool)
                    logging.info(f"Successfully installed: {tool}")
                else:
                    failed_installs.append((tool, result.stderr))
                    logging.error(f"Failed to install {tool}: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                failed_installs.append((tool, "Installation timeout"))
                logging.error(f"Timeout installing: {tool}")
            except Exception as e:
                failed_installs.append((tool, str(e)))
                logging.error(f"Error installing {tool}: {e}")
        
        # Complete progress bar
        self.update_progress_bar(100)
        self.update_progress("Installation complete!")
        
        # Show results
        self.show_installation_results(successful_installs, failed_installs)
    
    def update_progress(self, message):
        """Update the progress label (thread-safe)"""
        def update():
            self.progress_label.configure(text=message)
        self.after(0, update)
    
    def update_progress_bar(self, value):
        """Update the progress bar (thread-safe)"""
        def update():
            self.progress_bar.set(value / 100)
        self.after(0, update)
    
    def show_installation_results(self, successful, failed):
        """Show installation results to the user"""
        def show_results():
            result_message = "Installation Complete!\n\n"
            
            if successful:
                result_message += f"✅ Successfully installed {len(successful)} tool(s):\n"
                for tool in successful:
                    result_message += f"   • {self.format_tool_name(tool)}\n"
            
            if failed:
                result_message += f"\n❌ Failed to install {len(failed)} tool(s):\n"
                for tool, error in failed:
                    result_message += f"   • {self.format_tool_name(tool)}\n"
                    if "elevation" in error.lower():
                        result_message += "     (Administrator rights may be required)\n"
            
            messagebox.showinfo("Installation Results", result_message)
            
            # Re-enable the install button and hide progress bar
            self.install_btn.configure(state="normal")
            self.progress_bar.grid_remove()
            self.update_progress("")
        
        self.after(0, show_results)
    
    def clear_scrollable_frame(self):
        """Clear all widgets from the scrollable frame"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()