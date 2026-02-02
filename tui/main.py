#!/usr/bin/env python3
"""
Cynapse TUI - Synaptic Fortress
Proper Textual implementation - High performance, stable, and reactive.
"""

import sys
import os
import asyncio
from typing import List, Tuple
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical, Horizontal, Container
from textual.reactive import reactive
from textual.widgets import Static, Header, Footer, ListView, ListItem, RichLog, Input, Label
from textual.binding import Binding
from textual.worker import Worker

# Ensure we can import cynapse
sys.path.append(str(Path(__file__).parent.parent.resolve()))
from cynapse import CynapseHub, Neuron
from tui.symbols import ACTIVE, CHARGED, DORMANT, FUSED, BREACH, OSCILLATING


class NeuronItem(ListItem):
    """A list item representing a neuron."""
    def __init__(self, name: str, animal: str, status: str = "dormant"):
        super().__init__()
        self.neuron_name = name
        self.animal = animal
        self.status = status

    def compose(self) -> ComposeResult:
        yield Label(f"{self.animal} {self.neuron_name}", id=f"label-{self.neuron_name}")

    def update_status(self, new_status: str):
        self.status = new_status
        # In a more advanced version, we'd change colors here


class SynapticFortress(App):
    """The main TUI application."""

    CSS_PATH = "styles.css"

    # Reactive state
    security_status = reactive("secure")
    voice_active = reactive(False)
    integrity = reactive(100.0)

    BINDINGS = [
        Binding("h", "help", "Help"),
        Binding("v", "toggle_voice", "Voice"),
        Binding("s", "scan", "Scan"),
        Binding("L", "lockdown", "Lockdown", show=False),
        Binding("q", "quit", "Quit"),
        Binding("space", "toggle_neuron", "Run Selected"),
    ]

    def __init__(self):
        super().__init__()
        self.hub = CynapseHub()
        self.selected_neuron_name = None

    def compose(self) -> ComposeResult:
        """Build the four-zone layout."""
        with Container(id="app-container"):
            # Zone 1: Perimeter (Header bar)
            with Horizontal(id="perimeter"):
                yield Static("● SECURE", id="status-text", classes="status-secure")
                yield Static("Integrity: 100%", id="integrity-text")
                yield Static("Voice: ○", id="voice-status")
                yield Static("Shards: ●●●", id="shards-text")

            with Horizontal(id="main-content"):
                # Zone 2: Sentinel Grid (Left sidebar)
                with Vertical(id="sentinel"):
                    yield Static("SENTINEL GRID", id="sentinel-title")
                    neuron_items = []
                    for name in self.hub.list_neurons():
                        neuron = self.hub.get_neuron(name)
                        animal = neuron.manifest.animal or "🔧"
                        neuron_items.append(NeuronItem(name, animal))

                    yield ListView(*neuron_items, id="neuron-list")

                # Zone 3 & 4: Right side split
                with Vertical(id="right-panel"):
                    # Zone 3: Activation Chamber
                    with Vertical(id="activation"):
                        yield Static("ACTIVATION CHAMBER", id="activation-title")
                        yield RichLog(id="activation-log", highlight=True, markup=True)

                    # Zone 4: Operations Bay
                    with Vertical(id="operations"):
                        yield Static("OPERATIONS BAY", id="operations-title")
                        yield RichLog(id="console", highlight=True, markup=True)
                        yield Input(placeholder="Enter command or query...", id="chat-input")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the TUI."""
        self.log_message("[bold cyan]Cynapse Hub v1.0 [Synaptic Fortress][/bold cyan]")
        self.log_message(f"Detected {len(self.hub.neurons)} security neurons.")

        # Start background voice listener if it was already running in hub
        if self.hub._running:
            self.voice_active = True
            self.run_worker(self._voice_monitor_loop, thread=True, name="voice_monitor")

    def log_message(self, message: str, zone: str = "console") -> None:
        """Log a message to one of the RichLog widgets."""
        widget_id = "#console" if zone == "console" else "#activation-log"
        try:
            log = self.query_one(widget_id, RichLog)
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            log.write(f"[[dim]{timestamp}[/dim]] {message}")
        except Exception:
            pass

    # --- Reactive Watchers ---

    def watch_security_status(self, status: str) -> None:
        try:
            text = "● SECURE" if status == "secure" else "✗ BREACH"
            css_class = "status-secure" if status == "secure" else "status-breach"

            widget = self.query_one("#status-text", Static)
            widget.update(text)
            widget.set_classes(css_class)
        except Exception:
            pass

    def watch_voice_active(self, active: bool) -> None:
        try:
            widget = self.query_one("#voice-status", Static)
            widget.update(f"Voice: {'●' if active else '○'}")
        except Exception:
            pass

    # --- Actions ---

    def action_toggle_voice(self) -> None:
        """Toggle the voice listener."""
        if not self.voice_active:
            self.hub.start_voice_listener()
            self.voice_active = True
            self.run_worker(self._voice_monitor_loop, thread=True, name="voice_monitor")
            self.log_message("[bold green]Voice monitoring activated (18kHz).[/bold green]")
        else:
            self.hub.stop_voice_listener()
            self.voice_active = False
            self.log_message("[bold yellow]Voice monitoring deactivated.[/bold yellow]")

    def action_scan(self) -> None:
        """Run security integrity scan."""
        self.log_message("[bold blue]Initiating system-wide integrity scan...[/bold blue]")
        self.run_worker(self._perform_scan, exclusive=True)

    async def _perform_scan(self) -> None:
        """Background task for scanning."""
        success = await asyncio.to_thread(self.hub._run_tests)
        if success:
            self.log_message("[bold green]Scan complete: 100% Integrity. All neurons verified.[/bold green]")
        else:
            self.log_message("[bold red]Scan complete: DISCREPANCY DETECTED. Some neurons failed verification.[/bold red]")

    def action_lockdown(self) -> None:
        """Trigger emergency lockdown."""
        self.security_status = "breach"
        self.log_message("[bold red]CRITICAL: System lockdown initiated.[/bold red]")
        self.notify("LOCKDOWN ACTIVE", severity="error")

    def action_toggle_neuron(self) -> None:
        """Execute the currently selected neuron."""
        list_view = self.query_one("#neuron-list", ListView)
        if list_view.highlighted_child:
            item = list_view.highlighted_child
            if isinstance(item, NeuronItem):
                self.run_worker(self._execute_neuron(item.neuron_name))

    async def _execute_neuron(self, name: str):
        """Run a neuron and capture output."""
        self.log_message(f"Starting activation: [bold gold1]{name}[/bold gold1]", zone="activation")

        # Run in thread to keep UI alive
        result = await asyncio.to_thread(self.hub.run_neuron, name, silent=True)

        if result:
            if result.stdout:
                self.log_message(f"[dim]{result.stdout}[/dim]", zone="activation")
            if result.stderr:
                self.log_message(f"[red]{result.stderr}[/red]", zone="activation")
            self.log_message(f"Activation [green]successful[/green] (Code {result.returncode})", zone="activation")
        else:
            self.log_message(f"Activation [red]failed[/red]. Check audit logs.", zone="activation")

    # --- Events ---

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, NeuronItem):
            self.selected_neuron_name = event.item.neuron_name

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        self.query_one("#chat-input", Input).value = ""
        if not cmd:
            return

        self.log_message(f"[dim]> {cmd}[/dim]")

        # Handle internal commands or pass to neuron execution
        parts = cmd.split()
        base_cmd = parts[0].lower()
        args = parts[1:]

        if base_cmd in ["help", "?"]:
            self.log_message("Commands: scan, voice, clear, lockdown, <neuron_name> [args...]")
        elif base_cmd == "clear":
            self.query_one("#console", RichLog).clear()
            self.query_one("#activation-log", RichLog).clear()
        elif base_cmd == "scan":
            self.action_scan()
        elif base_cmd == "voice":
            self.action_toggle_voice()
        elif base_cmd == "lockdown":
            self.action_lockdown()
        else:
            # Try running as neuron
            self.run_worker(self._execute_neuron_with_args(base_cmd, args))

    async def _execute_neuron_with_args(self, name: str, args: List[str]):
        """Helper for command line execution."""
        neuron = self.hub.get_neuron(name)
        if not neuron:
            self.log_message(f"[red]Error: Unknown neuron or command '{name}'[/red]")
            return
        await self._execute_neuron(name) # Simplification: doesn't pass args yet in this helper

    # --- Background Workers ---

    async def _voice_monitor_loop(self) -> None:
        """Monitors the Hub's background voice state."""
        # The Hub already runs the detector in a thread.
        # Here we just wait for events if we had a queue.
        # For now, let's just keep the worker alive to represent the thread.
        while self.voice_active:
            await asyncio.sleep(1)
            # In a real implementation, we'd check a shared queue for 'WHISTLE_DETECTED'
            # and call self.app.call_from_thread(self.handle_whistle)

    def handle_whistle(self):
        """React to whistle trigger."""
        self.log_message("[bold magenta]🦇 WHISTLE DETECTED! Awakening Ghost Shell...[/bold magenta]")
        self.notify("Ghost Shell Awakening", severity="warning")


if __name__ == "__main__":
    app = SynapticFortress()
    app.run()
