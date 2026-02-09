#!/usr/bin/env python3
"""
Cynapse TUI Logic
"""
import time
import sys
from .terminal import Terminal
from .state import TUIState, Message
from .view import Renderer

class CynapseTUI:
    def __init__(self):
        self.term = Terminal()
        self.state = TUIState()
        self.renderer = Renderer(self.term)
        self.last_render = 0
        self.fps = 30
        
    def start(self):
        self.term.setup()
        try:
            # Initial Greeting
            self.state.add_message("assistant", "How can I help you today?")
            
            while self.state.running:
                # Handle Input
                key = self.term.read_key()
                if key:
                    self.handle_input(key)
                
                # Update Animation/State
                # (Future: simulate "thinking" animation tick here)
                
                # Render
                now = time.time()
                if now - self.last_render > 1.0 / self.fps:
                    self.renderer.render(self.state)
                    self.last_render = now
                    
                time.sleep(0.01) # CPU Saver
                
        except KeyboardInterrupt:
            pass
        finally:
            self.term.restore()
            print("Cynapse Terminated.")

    def handle_input(self, key: str):
        # Global Shortcuts
        if key == '\x11': # Ctrl+Q
            self.state.running = False
            return
        if key == '\t': # Ctrl+I (Tab is \t, Ctrl+I is same as Tab)
            # Wait, Ctrl+I is often Tab code 9. 
            # Let's assume Tab is for threading, maybe reuse for Help if not in threaded mode?
            # TUI_SPEC says Ctrl+I is Info.
            self.state.show_help = not self.state.show_help
            return
            
        # Context-Specific handling
        if self.state.show_palette:
            self.handle_palette_input(key)
        elif self.state.show_help:
            if key == '\x1b': # Esc
                self.state.show_help = False
        else:
            self.handle_chat_input(key)

    def handle_chat_input(self, key: str):
        if key == '/': 
            if len(self.state.input_buffer) == 0:
                self.state.show_palette = True
                self.state.palette_query = ""
                return
            else:
                self.state.input_buffer += key
                self.state.cursor_position += 1
                
        elif key == '\r': # Enter
            self.send_message()
            
        elif key == '\x7f': # Backspace
            if len(self.state.input_buffer) > 0:
                self.state.input_buffer = self.state.input_buffer[:-1]
                self.state.cursor_position = max(0, self.state.cursor_position - 1)
                
        elif key == '\x1b': # Esc
            pass # Close things?
            
        elif len(key) == 1 and ord(key) >= 32:
            self.state.input_buffer += key
            self.state.cursor_position += 1

    def handle_palette_input(self, key: str):
        if key == '\x1b': # Esc
            self.state.show_palette = False
            self.state.input_buffer = "" # Clear buffer so / doesn't remain? 
            # Actually spec says / opens palette.
            return
            
        if key == '\r': # Enter
            self.execute_palette_command()
            self.state.show_palette = False
            return
            
        if key == '\x7f': # Backspace
            self.state.palette_query = self.state.palette_query[:-1]
            if len(self.state.palette_query) == 0:
                # Optional: close if empty backspace?
                pass
                
        elif len(key) == 1 and ord(key) >= 32:
            self.state.palette_query += key
            
        # Selection navigation (up/down) could go here

    def execute_palette_command(self):
        cmd = self.state.palette_query.strip()
        if cmd == "quit":
            self.state.running = False
        elif cmd == "clear":
            self.state.messages = []
            self.state.threads[self.state.active_thread] = []
        elif cmd.startswith("agent "):
            role = cmd.split(" ")[1]
            self.state.add_message("system", f"Spawning {role} agent... (Mock)")
            # Here we would call HiveMind to spawn
        
        # Reset
        self.state.palette_query = ""

    def send_message(self):
        content = self.state.input_buffer.strip()
        if not content: return
        
        # Add User Message
        self.state.add_message("user", content)
        self.state.input_buffer = ""
        self.state.cursor_position = 0
        
        # Trigger response (Mock for TUI test)
        self.state.model_state = "thinking"
        # In real impl, this would be an async task or thread
        # For now, immediate mock response
        import threading
        def mock_reply():
            time.sleep(1)
            self.state.model_state = "executing"
            time.sleep(0.5)
            self.state.add_message("assistant", f"I received your message: '{content}'.\nThis is a mock response from Elara.")
            self.state.model_state = "ready"
            
        threading.Thread(target=mock_reply, daemon=True).start()

def main():
    tui = CynapseTUI()
    tui.start()

if __name__ == "__main__":
    main()