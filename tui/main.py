#!/usr/bin/env python3
"""
Cynapse TUI - The Synaptic Fortress Interface

Main entry point for the terminal user interface.
Implements the full cyberpunk-biological fusion design.

Usage:
    python -m tui.main
    python cynapse.py --tui

Author: Cynapse Team
Version: 1.0.0
"""

import sys
import os
import time
import select
from pathlib import Path

# Add parent directory for imports
_current_dir = Path(__file__).parent.resolve()
_project_root = _current_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tui.colors import Colors, RESET
from tui.symbols import get_neuron_status_symbol
from tui.state import get_state, CynapseState, Mode, NeuronStatus, SecurityStatus
from tui.layout import Layout, Terminal, get_layout
from tui.keybindings import get_key_handler, KeyAction
from tui.widgets.status_bar import StatusBar
from tui.widgets.sentinel_grid import SentinelGrid
from tui.widgets.animations import AnimationManager, ThinkingDot
from tui.modes.neural_assembly import NeuralAssemblyMode
from tui.modes.pharmacode import PharmacodeInjectionMode
from tui.modes.operations import OperationsMode
from tui.modes.breach import BreachMode


class CynapseTUI:
    """
    Main TUI application class.
    
    Orchestrates all widgets, modes, and handles the main loop.
    """
    
    REFRESH_RATE = 10  # FPS (10 = 100ms between frames)
    
    def __init__(self):
        self.state = get_state()
        self.layout = get_layout()
        self.key_handler = get_key_handler()
        self.animations = AnimationManager()
        
        self._running = False
        self._old_terminal_settings = None
        
        # Initialize with demo data
        self._load_demo_neurons()
        
        # Create widgets
        zones = self.layout.get_zone_dimensions()
        self.status_bar = StatusBar(zones['perimeter'][2])
        self.sentinel_grid = SentinelGrid(zones['sentinel'][2], zones['sentinel'][3])
        
        # Create mode renderers
        self.modes = {
            Mode.NEURAL_ASSEMBLY: NeuralAssemblyMode(
                zones['activation'][2], zones['activation'][3]
            ),
            Mode.PHARMACODE_INJECTION: PharmacodeInjectionMode(
                zones['activation'][2], zones['activation'][3]
            ),
            Mode.OPERATIONS: OperationsMode(
                zones['operations'][2], zones['operations'][3]
            ),
            Mode.PERIMETER_BREACH: BreachMode(
                self.layout.cols, self.layout.rows
            ),
        }
        
        # Add thinking animation
        self.animations.add('thinking', ThinkingDot())
        
        # Register key handlers
        self._setup_key_handlers()
    
    def _load_demo_neurons(self):
        """Load demo neuron data for testing."""
        demo_neurons = [
            ("bat_ghost", NeuronStatus.STANDBY),
            ("beaver_miner", NeuronStatus.STANDBY),
            ("canary_token", NeuronStatus.DORMANT),
            ("elara", NeuronStatus.STANDBY),
            ("elephant_sign", NeuronStatus.DORMANT),
            ("meerkat_scanner", NeuronStatus.ACTIVE),
            ("octopus_ctf", NeuronStatus.DORMANT),
            ("owl_ocr", NeuronStatus.STANDBY),
            ("parrot_wallet", NeuronStatus.DORMANT),
            ("rhino_gateway", NeuronStatus.STANDBY),
            ("tinyml_anomaly", NeuronStatus.DORMANT),
            ("wolverine_redteam", NeuronStatus.STANDBY),
        ]
        
        for neuron_id, status in demo_neurons:
            self.state.set_neuron_status(neuron_id, status)
    
    def _setup_key_handlers(self):
        """Register handlers for key actions."""
        self.key_handler.register_handler(KeyAction.QUIT, self._handle_quit)
        self.key_handler.register_handler(KeyAction.BACK, self._handle_back)
        self.key_handler.register_handler(KeyAction.HELP, self._toggle_help)
        self.key_handler.register_handler(KeyAction.VOICE_TOGGLE, 
                                          lambda: self.state.toggle_voice_monitor())
        self.key_handler.register_handler(KeyAction.MOVE_DOWN,
                                          lambda: self.state.navigate_neurons(1))
        self.key_handler.register_handler(KeyAction.MOVE_UP,
                                          lambda: self.state.navigate_neurons(-1))
        self.key_handler.register_handler(KeyAction.CYCLE_ZONE,
                                          lambda: self.state.cycle_zone())
        self.key_handler.register_handler(KeyAction.SELECT, self._handle_select)
        self.key_handler.register_handler(KeyAction.TOGGLE, self._handle_toggle)
        self.key_handler.register_handler(KeyAction.ARM_ALL, self._arm_all_neurons)
        self.key_handler.register_handler(KeyAction.DISARM_ALL, self._disarm_all_neurons)
        self.key_handler.register_handler(KeyAction.LOCKDOWN, self._trigger_lockdown)
        self.key_handler.register_handler(KeyAction.SECURITY_SCAN, self._start_security_scan)
    
    def _handle_quit(self):
        """Handle quit action."""
        self._running = False
    
    def _handle_back(self):
        """Handle back/escape action."""
        if self.state.help_visible:
            self.state.toggle_help()
        elif self.state.mode == Mode.PERIMETER_BREACH:
            # Can't easily escape breach mode
            pass
        else:
            self._running = False
    
    def _toggle_help(self):
        """Toggle help overlay."""
        self.state.toggle_help()
    
    def _handle_select(self):
        """Handle enter/select on selected item."""
        neuron = self.state.get_selected_neuron()
        if neuron:
            # Toggle the neuron's state
            current = self.state.neurons.get(neuron, NeuronStatus.DORMANT)
            if current == NeuronStatus.DORMANT:
                self.state.set_neuron_status(neuron, NeuronStatus.ACTIVE)
            elif current == NeuronStatus.ACTIVE:
                self.state.set_neuron_status(neuron, NeuronStatus.DORMANT)
    
    def _handle_toggle(self):
        """Handle space toggle on sentinel."""
        neuron = self.state.get_selected_neuron()
        if neuron:
            current = self.state.neurons.get(neuron, NeuronStatus.DORMANT)
            # Cycle through: DORMANT -> STANDBY -> ACTIVE -> DORMANT
            next_status = {
                NeuronStatus.DORMANT: NeuronStatus.STANDBY,
                NeuronStatus.STANDBY: NeuronStatus.ACTIVE,
                NeuronStatus.ACTIVE: NeuronStatus.DORMANT,
                NeuronStatus.ERROR: NeuronStatus.DORMANT,
            }
            self.state.set_neuron_status(neuron, next_status.get(current, NeuronStatus.DORMANT))
    
    def _arm_all_neurons(self):
        """Arm all dormant neurons."""
        for neuron_id, status in list(self.state.neurons.items()):
            if status == NeuronStatus.DORMANT:
                self.state.set_neuron_status(neuron_id, NeuronStatus.STANDBY)
    
    def _disarm_all_neurons(self):
        """Return all neurons to dormant."""
        for neuron_id in list(self.state.neurons.keys()):
            self.state.set_neuron_status(neuron_id, NeuronStatus.DORMANT)
    
    def _trigger_lockdown(self):
        """Trigger emergency lockdown."""
        self.state.set_security_status(SecurityStatus.BREACH)
    
    def _start_security_scan(self):
        """Start a security scan."""
        self.state.set_security_status(SecurityStatus.SCANNING)
    
    def _read_key(self) -> str:
        """Read a single key from stdin without blocking."""
        if sys.platform == 'win32':
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getch().decode('utf-8', errors='ignore')
            return ""
        else:
            # Unix: use select for non-blocking check
            if select.select([sys.stdin], [], [], 0)[0]:
                return sys.stdin.read(1)
            return ""
    
    def _render(self):
        """Render the full interface."""
        Terminal.move_cursor(1, 1)
        
        # Check for breach mode (full screen takeover)
        if self.state.mode == Mode.PERIMETER_BREACH:
            breach_lines = self.modes[Mode.PERIMETER_BREACH].render(self.state)
            for line in breach_lines:
                print(line)
            return
        
        # Refresh dimensions
        self.layout.refresh_size()
        zones = self.layout.get_zone_dimensions()
        
        # Render status bar (Zone 1)
        self.status_bar.tick()
        status_line = self.status_bar.render(self.state)
        print(f"\033[1;1H{status_line}")
        
        # Render sentinel grid (Zone 2)
        self.sentinel_grid = SentinelGrid(zones['sentinel'][2], zones['sentinel'][3])
        sentinel_lines = self.sentinel_grid.render(self.state)
        
        for i, line in enumerate(sentinel_lines):
            row = zones['sentinel'][1] + i + 1
            print(f"\033[{row};1H{line}")
        
        # Render activation chamber (Zone 3)
        activation_mode = self.modes.get(self.state.mode, self.modes[Mode.OPERATIONS])
        if hasattr(activation_mode, 'tick'):
            activation_mode.tick()
        
        if isinstance(activation_mode, (NeuralAssemblyMode, PharmacodeInjectionMode)):
            activation_lines = activation_mode.render(self.state)
        else:
            # Default to operations in the bottom zone
            activation_lines = [""] * zones['activation'][3]
        
        for i, line in enumerate(activation_lines[:zones['activation'][3]]):
            row = zones['activation'][1] + i + 1
            col = zones['activation'][0] + 1
            # Pad line to fill width
            line = line[:zones['activation'][2] - 2]
            line = line + ' ' * (zones['activation'][2] - len(line) - 2)
            print(f"\033[{row};{col}H{line}")
        
        # Render operations bay (Zone 4)
        ops_mode = self.modes.get(Mode.OPERATIONS)
        ops_mode = OperationsMode(zones['operations'][2], zones['operations'][3])
        ops_lines = ops_mode.render(self.state)
        
        for i, line in enumerate(ops_lines[:zones['operations'][3]]):
            row = zones['operations'][1] + i + 1
            col = zones['operations'][0] + 1
            print(f"\033[{row};{col}H{line}")
        
        # Render footer
        mode_str = self.state.mode.name.replace('_', ' ').title()
        hints = [('h', 'Help'), ('v', 'Voice'), ('s', 'Scan'), ('Q', 'Quit')]
        footer = self.layout.render_footer(mode_str, hints)
        footer_row = zones['footer'][1] + 1
        print(f"\033[{footer_row};1H{footer}")
        
        # Help overlay if visible
        if self.state.help_visible:
            self._render_help_overlay()
        
        sys.stdout.flush()
    
    def _render_help_overlay(self):
        """Render the help overlay."""
        help_text = self.key_handler.get_help_text()
        lines = help_text.split('\n')
        
        # Draw simple overlay box
        start_row = 5
        start_col = 10
        width = 50
        
        from .colors import DEEP_PURPLE
        
        # Header
        print(f"\033[{start_row};{start_col}H{DEEP_PURPLE}╔{'═' * (width - 2)}╗{RESET}")
        print(f"\033[{start_row + 1};{start_col}H{DEEP_PURPLE}║{RESET} KEYBINDINGS{' ' * (width - 14)}{DEEP_PURPLE}║{RESET}")
        print(f"\033[{start_row + 2};{start_col}H{DEEP_PURPLE}╠{'═' * (width - 2)}╣{RESET}")
        
        for i, line in enumerate(lines[:15]):
            row = start_row + 3 + i
            line = line[:width - 4]
            padding = width - 4 - len(line)
            print(f"\033[{row};{start_col}H{DEEP_PURPLE}║{RESET} {line}{' ' * padding} {DEEP_PURPLE}║{RESET}")
        
        # Footer
        close_row = start_row + 3 + min(15, len(lines))
        print(f"\033[{close_row};{start_col}H{DEEP_PURPLE}╠{'═' * (width - 2)}╣{RESET}")
        print(f"\033[{close_row + 1};{start_col}H{DEEP_PURPLE}║{RESET} Press 'h' or Esc to close{' ' * (width - 28)}{DEEP_PURPLE}║{RESET}")
        print(f"\033[{close_row + 2};{start_col}H{DEEP_PURPLE}╚{'═' * (width - 2)}╝{RESET}")
    
    def run(self):
        """Run the TUI main loop."""
        self._running = True
        
        try:
            # Setup terminal
            Terminal.clear()
            Terminal.hide_cursor()
            self._old_terminal_settings = Terminal.enable_raw_mode()
            
            frame_time = 1.0 / self.REFRESH_RATE
            
            while self._running:
                frame_start = time.time()
                
                # Handle input
                key = self._read_key()
                if key:
                    self.key_handler.handle_key(key)
                
                # Tick animations
                self.animations.tick_all()
                
                # Render
                self._render()
                
                # Frame rate limiting
                elapsed = time.time() - frame_start
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)
        
        except KeyboardInterrupt:
            pass
        
        finally:
            # Cleanup
            Terminal.show_cursor()
            Terminal.clear()
            if self._old_terminal_settings:
                Terminal.disable_raw_mode(self._old_terminal_settings)
            print("Cynapse TUI closed.")


def main():
    """Main entry point."""
    print("Starting Cynapse TUI - The Synaptic Fortress Interface...")
    print("Press 'Q' (Shift+Q) to quit, 'h' for help")
    time.sleep(1)
    
    tui = CynapseTUI()
    tui.run()


if __name__ == "__main__":
    main()
