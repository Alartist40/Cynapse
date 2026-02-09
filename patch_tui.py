#!/usr/bin/env python3
"""Patch TUI to integrate with HiveMind"""
import re

with open('cynapse/tui/main.py', 'r') as f:
    content = f.read()

# 1. Add HiveMind import
old_import = "from cynapse.core.hub import CynapseHub\nfrom cynapse.neurons.elephant.tui import verify_for_tui"
new_import = "from cynapse.core.hub import CynapseHub\nfrom cynapse.neurons.elephant.tui import verify_for_tui\nfrom cynapse.core.hivemind import HiveMind, HiveConfig"
content = content.replace(old_import, new_import)

# 2. Replace TODO with actual bee spawning
old_todo = "                # TODO: Trigger HiveMind bee"
new_code = """                # Trigger HiveMind bee
                try:
                    hive = self._get_hivemind()
                    instance_id = hive.deploy_chat(self.state.input_buffer)
                    self.state.messages.append({
                        'role': 'assistant',
                        'content': f'🐝 Bee spawned: {instance_id[:8]}...'
                    })
                except Exception as e:
                    self.state.messages.append({
                        'role': 'assistant',
                        'content': f'❌ Error: {str(e)[:50]}'
                    })"""
content = content.replace(old_todo, new_code)

# 3. Add hivemind getter to InputHandler
old_handler = """    def __init__(self, state: HiveState, term: Terminal):
        self.state = state
        self.term = term
        self.running = True
        self.input_mode = False"""
new_handler = """    def __init__(self, state: HiveState, term: Terminal, hivemind_getter=None):
        self.state = state
        self.term = term
        self.running = True
        self.input_mode = False
        self._get_hivemind = hivemind_getter"""
content = content.replace(old_handler, new_handler)

# 4. Update SynapticFortress init
old_fortress = """    def __init__(self):
        self.term = Terminal()
        self.state = HiveState()
        self.animator = Animator(self.state)
        self.input_handler = InputHandler(self.state, self.term)"""
new_fortress = """    def __init__(self):
        self.term = Terminal()
        self.state = HiveState()
        self.animator = Animator(self.state)
        self._hivemind = None
        self.input_handler = InputHandler(self.state, self.term, self._get_hivemind)"""
content = content.replace(old_fortress, new_fortress)

# 5. Add _get_hivemind method before _draw
old_draw = """    def _draw(self):
        \"\"\"Render all zones\"\"\"
        # Update terminal size"""
new_draw = """    def _get_hivemind(self):
        \"\"\"Lazy initialization of HiveMind\"\"\"
        if self._hivemind is None:
            try:
                config = HiveConfig.from_yaml('./hivemind.yaml')
                self._hivemind = HiveMind(config)
            except Exception:
                self._hivemind = HiveMind()
        return self._hivemind

    def _draw(self):
        \"\"\"Render all zones\"\"\"
        # Update terminal size"""
content = content.replace(old_draw, new_draw)

with open('cynapse/tui/main.py', 'w') as f:
    f.write(content)

print("✓ TUI patched successfully")
