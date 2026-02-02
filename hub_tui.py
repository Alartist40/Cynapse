from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, ListView, ListItem, Static, RichLog, Input, Label
from textual.reactive import reactive
from textual.screen import Screen
from textual.binding import Binding
from cynapse import CynapseHub, Neuron
import asyncio
import sys
import os
from datetime import datetime

class NeuronItem(ListItem):
    """A list item representing a neuron."""
    def __init__(self, neuron: Neuron):
        super().__init__()
        self.neuron = neuron
        self.animal = neuron.manifest.animal or "🔧"
        self.neuron_name = neuron.manifest.name

    def compose(self) -> ComposeResult:
        yield Label(f"{self.animal} {self.neuron_name}")

class NeuronSidebar(Container):
    """Sidebar containing the list of neurons."""
    def compose(self) -> ComposeResult:
        yield Label("NEURONS", id="sidebar-title")
        yield ListView(id="neuron-list")

class HubStatusBar(Static):
    """A status bar showing security info."""
    security_status = reactive("SECURE")
    integrity = reactive(100.0)
    voice = reactive(False)
    shards = reactive("●●●")

    def render(self) -> str:
        voice_icon = "○" if not self.voice else "●"
        status_color = "#fbc02d" if self.security_status == "SECURE" else "#ff1744"

        # User snippet style: ║ ● SECURE │ Integrity: 100% Voice: ○ │ Shards: ○○○ ║
        return (
            f"[#4a148c]║[/#4a148c] [bold {status_color}]● {self.security_status}[/bold {status_color}] │ "
            f"Integrity: {self.integrity:.0f}% │ "
            f"Voice: {voice_icon} │ "
            f"Shards: {self.shards} [#4a148c]║[/#4a148c]"
        )

class Dashboard(Container):
    """Main dashboard area."""
    def compose(self) -> ComposeResult:
        yield HubStatusBar(id="status-bar")
        yield RichLog(id="console", highlight=True, markup=True)
        yield Input(placeholder="Enter command or query...", id="input-box")

class CynapseApp(App):
    """Main Cynapse Textual Application."""

    CSS = """
    Screen {
        background: #0a0a0f;
        color: #e0e0e0;
    }

    #app-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 4fr;
    }

    NeuronSidebar {
        background: #12121a;
        border-right: double #4a148c;
        padding: 1;
    }

    #sidebar-title {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: #4a148c;
        color: #00e5ff;
        margin-bottom: 1;
        border: solid #00e5ff;
    }

    Dashboard {
        padding: 1;
    }

    #status-bar {
        text-align: center;
        text-style: bold;
        padding: 1;
        background: #1a1a2e;
        color: #fbc02d;
        margin-bottom: 1;
        border: double #4a148c;
    }

    #console {
        height: 1fr;
        border: solid #333333;
        background: #050508;
        color: #00ff41;
        padding: 1;
    }

    #input-box {
        margin-top: 1;
        border: solid #4a148c;
        background: #12121a;
        color: #00e5ff;
    }

    NeuronItem {
        padding: 0 1;
        color: #888888;
    }

    NeuronItem:hover {
        background: #4a148c33;
        color: #ffffff;
    }

    ListView > .list-view--highlight {
        background: #4a148c66;
        color: #00e5ff;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("v", "toggle_voice", "Toggle Voice", show=True),
        Binding("s", "security_scan", "Security Scan", show=True),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("clear", "clear_console", "Clear Console", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.hub = CynapseHub()
        self.active_neuron = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            yield NeuronSidebar()
            yield Dashboard()
        yield Footer()

    async def on_mount(self) -> None:
        """Called when the app is mounted."""
        self._populate_neurons()
        self._log_message("[bold #00e5ff]Cynapse Hub initialized.[/bold #00e5ff]")

        # Initial Discovery Scan
        self._log_message("[dim]Starting neural discovery scan...[/dim]")
        await asyncio.sleep(0.5)
        for neuron in self.hub.get_all_neurons():
            animal = neuron.manifest.animal or "🔧"
            self._log_message(f"  [green]✔[/green] Discovered {animal} [bold]{neuron.manifest.name}[/bold]")
            await asyncio.sleep(0.05)

        self._log_message(f"[bold #00ff41]Scan complete. {len(self.hub.neurons)} neurons ready.[/bold #00ff41]")
        self.set_interval(1.0, self._update_status_bar)

    def _populate_neurons(self) -> None:
        """Populate the sidebar with neurons from the hub."""
        neuron_list = self.query_one("#neuron-list", ListView)
        for neuron in self.hub.get_all_neurons():
            neuron_list.append(NeuronItem(neuron))

    def _log_message(self, message: str) -> None:
        """Log a message to the console."""
        console = self.query_one("#console", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        console.write(f"[[dim]{timestamp}[/dim]] {message}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle neuron selection."""
        if isinstance(event.item, NeuronItem):
            self.active_neuron = event.item.neuron
            self._log_message(f"Selected neuron: [bold gold1]{self.active_neuron.manifest.name}[/bold gold1]")
            self._log_message(f"Description: {self.active_neuron.manifest.description}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input."""
        cmd = event.value.strip()
        self.query_one("#input-box", Input).value = ""

        if not cmd:
            return

        self._log_message(f"[dim]> {cmd}[/dim]")

        if cmd.lower() in ["help", "?"]:
            self._log_message("Available commands: list, status, voice, clear, <neuron_name> [args...]")
        elif cmd.lower() == "list":
            self._log_message("Neurons: " + ", ".join(self.hub.list_neurons()))
        elif cmd.lower() == "status":
            self._log_message(f"Hub Status: SECURE. Neurons loaded: {len(self.hub.neurons)}")
        elif cmd.lower() == "clear":
            self.query_one("#console", RichLog).clear()
        elif cmd.lower() == "voice":
            self.action_toggle_voice()
        else:
            # Try to run as neuron
            parts = cmd.split()
            neuron_name = parts[0]
            args = parts[1:]

            await self._run_neuron_task(neuron_name, *args)

    async def _run_neuron_task(self, name: str, *args):
        """Run a neuron in the background."""
        neuron = self.hub.get_neuron(name)
        if not neuron:
            self._log_message(f"[red]Error: Neuron '{name}' not found.[/red]")
            return

        self._log_message(f"Executing [bold]{name}[/bold]...")

        # Run in a thread to not block the UI
        try:
            result = await asyncio.to_thread(self.hub.run_neuron, name, *args, silent=True)
            if result:
                if result.stdout:
                    self._log_message(f"[green]Output:[/green]\n{result.stdout}")
                if result.stderr:
                    self._log_message(f"[red]Error Output:[/red]\n{result.stderr}")
                self._log_message(f"Execution finished with code {result.returncode}")
            else:
                self._log_message(f"[red]Execution failed (check audit log for details).[/red]")
        except Exception as e:
            self._log_message(f"[red]Exception during execution: {e}[/red]")

    def action_toggle_voice(self) -> None:
        """Toggle the voice listener."""
        if not self.hub._running:
            self.hub.start_voice_listener()
            self._log_message("[bold green]Voice listener started.[/bold green]")
            self.query_one("#status-bar", HubStatusBar).voice = True
        else:
            self.hub.stop_voice_listener()
            self._log_message("[bold yellow]Voice listener stopped.[/bold yellow]")
            self.query_one("#status-bar", HubStatusBar).voice = False

    def _update_status_bar(self) -> None:
        """Update the status bar from hub state."""
        status_bar = self.query_one("#status-bar", HubStatusBar)
        status_bar.voice = self.hub._running
        # More updates could go here

    def action_cursor_down(self) -> None:
        self.query_one("#neuron-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#neuron-list", ListView).action_cursor_up()

    def action_security_scan(self) -> None:
        """Run a manual security scan."""
        self._log_message("[bold blue]Starting integrity scan...[/bold blue]")
        # Perform actual verification check
        async def run_scan():
            success = await asyncio.to_thread(self.hub._run_tests)
            if success:
                self._log_message("[bold green]Scan complete: 100% Integrity. All neurons verified.[/bold green]")
            else:
                self._log_message("[bold red]Scan complete: DISCREPANCY DETECTED. Some neurons failed verification.[/bold red]")

        asyncio.create_task(run_scan())

if __name__ == "__main__":
    app = CynapseApp()
    app.run()
