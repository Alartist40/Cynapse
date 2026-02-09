#!/usr/bin/env python3
"""
Synaptic Fortress TUI — Cynapse Terminal Interface
===================================================
A cyberpunk-biological fusion interface for the Cynapse security ecosystem.

Design Philosophy:
- The computer is a living organism
- Four security zones reflecting neural architecture
- Minimal CPU usage (static skeletons, moving pulses)
- 4fps max animation, single-character updates

Zones:
  1. PERIMETER (Top): Global status, integrity, alerts
  2. SENTINEL GRID (Left): Neuron/Bees status, 25% width
  3. ACTIVATION CHAMBER (Top-Right): Dynamic visualizations
  4. OPERATIONS BAY (Bottom-Right): RAG lab, chat, execution

Usage:
    python tui.py                    # Launch TUI
    python tui.py --mode operations  # Start in specific mode
"""

import os
import sys
import time
import json
import threading
import select
import termios
import tty
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from cynapse.core.hub import CynapseHub
from cynapse.neurons.elephant.tui import verify_for_tui
from cynapse.core.hivemind import HiveMind, HiveConfig

# ---------------------------------------------------------------------------
# ANSI Color Palette (256-color)
# ---------------------------------------------------------------------------

class Colors:
    """ANSI 256-color palette — Purple Dynasty theme"""
    # Primary - Purple Dynasty
    DEEP_PURPLE = "\033[38;5;93m"
    SYNAPSE_VIOLET = "\033[38;5;141m"
    ACTIVE_MAGENTA = "\033[38;5;201m"
    ROYAL_PURPLE = "\033[38;5;129m"

    # Secondary - Electric Blue
    CYAN_ELECTRIC = "\033[38;5;51m"
    DEEP_BLUE = "\033[38;5;27m"
    CYBER_BLUE = "\033[38;5;33m"
    MUTED_BLUE = "\033[38;5;67m"

    # Complement - Alert Gold
    COMPLEMENT_GOLD = "\033[38;5;220m"
    WARNING_AMBER = "\033[38;5;178m"
    BREACH_RED = "\033[38;5;196m"
    INTERRUPT_ORANGE = "\033[38;5;208m"

    # Neutral
    DORMANT_GRAY = "\033[38;5;245m"
    WHITE_MATTER = "\033[38;5;255m"
    DEEP_BACKGROUND = "\033[48;5;17m"
    BREACH_BG = "\033[48;5;52m"

    # Reset
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

# ---------------------------------------------------------------------------
# Semantic Symbols
# ---------------------------------------------------------------------------

class Symbols:
    """Universal semantic symbols"""
    ACTIVE = "●"           # Live, processing
    CHARGED = "▸"          # Armed, standby
    DORMANT = "○"          # Offline, sleeping
    FUSED = "✓"            # Complete, success
    OSCILLATING = "∿"      # Training, adapting
    BREACH = "✗"           # Error, compromised
    WARNING = "⚠"          # Alert
    CURSOR = "►"           # Selection
    SHARD = "◆"            # USB shard
    SIGNAL = "~"           # Pulse

    # Box drawing
    HLINE = "─"
    VLINE = "│"
    TL = "┌"
    TR = "┐"
    BL = "└"
    BR = "┘"
    CROSS = "┼"
    T_DOWN = "┬"
    T_UP = "┴"

# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------

class UIMode(Enum):
    NEURAL_ASSEMBLY = auto()    # USB shard combination
    PHARMACODE = auto()         # Model loading/training
    OPERATIONS = auto()         # RAG lab, chat
    BREACH = auto()             # Emergency alert
    MAINTENANCE = auto()        # Idle/system menu

class SecurityStatus(Enum):
    SECURE = auto()
    SCANNING = auto()
    BREACH_DETECTED = auto()
    LOCKDOWN = auto()

@dataclass
class NeuronStatus:
    """Status of a single neuron/bee"""
    name: str
    animal: str
    state: str  # "active", "standby", "dormant", "error"
    alert: Optional[str] = None
    progress: float = 0.0  # 0-100

@dataclass
class ShardStatus:
    """Ghost Shell shard status"""
    id: int
    present: bool
    verified: bool
    progress: float = 0.0

@dataclass
class HiveState:
    """Central state - single source of truth"""
    # Mode
    mode: UIMode = UIMode.OPERATIONS
    previous_mode: Optional[UIMode] = None

    # Security
    security: SecurityStatus = SecurityStatus.SECURE
    integrity: float = 100.0
    last_breach: Optional[str] = None

    # Voice
    voice_listening: bool = False
    voice_frequency: int = 18000

    # Shards (Ghost Shell)
    shards: List[ShardStatus] = field(default_factory=lambda: [
        ShardStatus(1, False, False),
        ShardStatus(2, False, False),
        ShardStatus(3, False, False)
    ])
    assembly_progress: float = 0.0

    # Neurons/Bees
    neurons: List[NeuronStatus] = field(default_factory=list)
    selected_neuron: int = 0

    # Operations (Chat/RAG)
    messages: List[Dict[str, str]] = field(default_factory=list)
    input_buffer: str = ""
    documents: List[Dict] = field(default_factory=list)

    # Pharmacode (Training/Loading)
    ampules: Dict[str, Dict] = field(default_factory=lambda: {
        "TiDAR": {"progress": 0, "status": "standby"},
        "RoPE": {"progress": 0, "status": "standby"},
        "MoE": {"progress": 0, "status": "standby"}
    })

    # Animation
    frame: int = 0
    spinner_idx: int = 0

    def __post_init__(self):
        if not self.neurons:
            self.neurons = [
                NeuronStatus("bat_ghost", "🦇", "dormant"),
                NeuronStatus("beaver_miner", "🦫", "dormant"),
                NeuronStatus("canary_token", "🐤", "dormant"),
                NeuronStatus("elara", "🌙", "standby"),
                NeuronStatus("elephant_sign", "🐘", "dormant"),
                NeuronStatus("meerkat_scanner", "🦔", "dormant"),
                NeuronStatus("wolverine_redteam", "🐺", "dormant"),
                NeuronStatus("hivemind", "🐝", "active"),
            ]

# ---------------------------------------------------------------------------
# Terminal Control
# ---------------------------------------------------------------------------

class Terminal:
    """Raw terminal mode for instant key response"""

    def __init__(self):
        self.old_settings = None
        self.width = 80
        self.height = 24

    def setup(self):
        """Enter raw mode"""
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        self.update_size()

    def restore(self):
        """Restore original terminal settings"""
        if self.old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def update_size(self):
        """Get terminal dimensions"""
        try:
            import fcntl
            import struct
            import termios
            h, w, hp, wp = struct.unpack('HHHH',
                fcntl.ioctl(0, termios.TIOCGWINSZ,
                struct.pack('HHHH', 0, 0, 0, 0)))
            self.width = w
            self.height = h
        except:
            pass

    def clear(self):
        """Clear screen"""
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def move(self, x: int, y: int):
        """Move cursor to position (1-indexed)"""
        sys.stdout.write(f"\033[{y};{x}H")


    def write(self, text: str):
        """Write to buffer (no flush)"""
        sys.stdout.write(text)

    def flush(self):
        """Flush buffer to screen"""
        sys.stdout.flush()

    def print_at(self, x: int, y: int, text: str):
        """Move cursor and write text in one operation"""
        self.move(x, y)
        self.write(text)

    def hide_cursor(self):
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def show_cursor(self):
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    def read_key(self, timeout: float = 0.05) -> Optional[str]:
        """Non-blocking key read"""
        if select.select([sys.stdin], [], [], timeout)[0]:
            return sys.stdin.read(1)
        return None

# ---------------------------------------------------------------------------
# Animation System
# ---------------------------------------------------------------------------

class Animator:
    """Minimal animation system - 4fps max, single char updates"""

    SPINNER = ["|", "/", "-", "\\"]
    PULSE = ["●", "◐", "◑", "◒"]

    def __init__(self, state: HiveState):
        self.state = state
        self.last_frame = 0
        self.frame_interval = 0.1  # 10fps for smoother UI

    def tick(self) -> bool:
        """Update animation state, return True if frame changed"""
        now = time.time()
        if now - self.last_frame >= self.frame_interval:
            self.state.frame += 1

            self.state.spinner_idx = self.state.frame % len(self.SPINNER)
            self.last_frame = now
            return True
        return False

    def get_spinner(self) -> str:
        return self.SPINNER[self.state.spinner_idx]

    def get_pulse(self, speed: int = 1) -> str:
        return self.PULSE[(self.state.frame // speed) % len(self.PULSE)]

# ---------------------------------------------------------------------------
# Zone Renderers
# ---------------------------------------------------------------------------

class ZoneRenderer:
    """Base class for zone renderers"""

    def __init__(self, term: Terminal, state: HiveState, animator: Animator):
        self.term = term
        self.state = state
        self.anim = animator
        self.colors = Colors()
        self.sym = Symbols()

    def draw(self):
        """Override in subclasses"""
        pass

    def color(self, code: str, text: str) -> str:
        return f"{code}{text}{self.colors.RESET}"
    
    def print_at(self, x: int, y: int, text: str):
        """Helper to move and print in one go"""
        self.term.move(x, y)
        self.term.write(text)

class PerimeterZone(ZoneRenderer):
    """Zone 1: Top status bar"""

    def draw(self):
        w = self.term.width

        # Security icon
        if self.state.security == SecurityStatus.SECURE:
            sec_icon = self.color(self.colors.CYAN_ELECTRIC, self.sym.ACTIVE)
            sec_text = "SECURE"
        elif self.state.security == SecurityStatus.SCANNING:
            sec_icon = self.color(self.colors.WARNING_AMBER, self.anim.get_pulse())
            sec_text = "SCANNING"
        elif self.state.security == SecurityStatus.BREACH_DETECTED:
            sec_icon = self.color(self.colors.BREACH_RED, self.sym.BREACH)
            sec_text = "BREACH"
        else:
            sec_icon = self.color(self.colors.BREACH_RED, "█")
            sec_text = "LOCKDOWN"

        # Shards status
        shards_str = ""
        for s in self.state.shards:
            if s.present and s.verified:
                shards_str += self.color(self.colors.COMPLEMENT_GOLD, self.sym.SHARD)
            elif s.present:
                shards_str += self.color(self.colors.WARNING_AMBER, self.sym.SHARD)
            else:
                shards_str += self.color(self.colors.DORMANT_GRAY, "○")

        # Voice status
        voice = self.color(self.colors.ACTIVE_MAGENTA, "V") if self.state.voice_listening else                 self.color(self.colors.DORMANT_GRAY, "v")

        # Integrity percentage
        integrity = f"{self.state.integrity:.0f}%"

        # Build line
        left = f" {sec_icon} {sec_text}"
        right = f"SHARDS:[{shards_str}] {voice} {integrity} "
        center_space = w - len(left) - len(right) - 2

        line = f"{self.colors.DEEP_PURPLE}{self.sym.TL}{self.sym.HLINE * (w-2)}{self.sym.TR}{self.colors.RESET}"
        content = f"{self.colors.DEEP_PURPLE}{self.sym.VLINE}{self.colors.RESET}{left}{' ' * center_space}{right}{self.colors.DEEP_PURPLE}{self.sym.VLINE}{self.colors.RESET}"

        self.term.move(1, 1)
        self.term.write(line)
        self.term.move(1, 2)
        self.term.write(content)

class SentinelGridZone(ZoneRenderer):
    """Zone 2: Left sidebar - neuron/bee status"""

    def draw(self):
        w = max(20, self.term.width // 4)  # 25% width
        h = self.term.height - 3
        start_y = 3

        # Draw border
        for y in range(start_y, start_y + h):
            self.term.print_at(w, y, f"{self.colors.DEEP_PURPLE}{self.sym.VLINE}{self.colors.RESET}")

        # Title
        self.term.print_at(2, start_y, f"{self.colors.SYNAPSE_VIOLET}SENTINEL GRID{self.colors.RESET}")

        # Neuron list
        for i, neuron in enumerate(self.state.neurons):
            y = start_y + 2 + i
            if y >= start_y + h:
                break

            self.term.move(2, y)

            # Selection cursor
            cursor = self.sym.CURSOR if i == self.state.selected_neuron else " "

            # State symbol
            if neuron.state == "active":
                sym = self.color(self.colors.ACTIVE_MAGENTA, self.sym.ACTIVE)
                status = "[running]"
                color = self.colors.ACTIVE_MAGENTA
            elif neuron.state == "standby":
                sym = self.color(self.colors.CYAN_ELECTRIC, self.sym.CHARGED)
                status = "[standby]"
                color = self.colors.CYAN_ELECTRIC
            elif neuron.state == "error":
                sym = self.color(self.colors.BREACH_RED, self.sym.BREACH)
                status = "[arrested]"
                color = self.colors.BREACH_RED
            else:
                sym = self.color(self.colors.DORMANT_GRAY, self.sym.DORMANT)
                status = "[dormant]"
                color = self.colors.DORMANT_GRAY

            line = f"{cursor} {neuron.animal} {neuron.name[:15]:<15} {sym} {self.color(color, status)}"
            self.term.print_at(2, y, line[:w-2])

            # Alert if present
            if neuron.alert:
                y += 1
                if y < start_y + h:
                    self.term.move(4, y)
                    alert_text = f"└ {neuron.alert[:w-6]}"
                    self.term.write(self.color(self.colors.WARNING_AMBER, alert_text))

class ActivationChamberZone(ZoneRenderer):
    """Zone 3: Top-right - dynamic visualization"""

    def draw(self):
        w = self.term.width
        h = self.term.height
        left_w = max(20, w // 4)
        zone_w = w - left_w - 1
        zone_h = (h - 3) // 2

        start_x = left_w + 2
        start_y = 3

        # Mode-specific rendering
        if self.state.mode == UIMode.NEURAL_ASSEMBLY:
            self._draw_assembly(start_x, start_y, zone_w, zone_h)
        elif self.state.mode == UIMode.PHARMACODE:
            self._draw_pharmacode(start_x, start_y, zone_w, zone_h)
        elif self.state.mode == UIMode.BREACH:
            self._draw_breach(start_x, start_y, zone_w, zone_h)
        else:
            self._draw_maintenance(start_x, start_y, zone_w, zone_h)

    def _draw_assembly(self, x: int, y: int, w: int, h: int):
        """Ghost Shell shard assembly visualization"""
        self.term.print_at(x, y, f"{self.colors.SYNAPSE_VIOLET}NEURAL ASSEMBLY MODE{self.colors.RESET}")

        # Draw synaptic pathways
        for i, shard in enumerate(self.state.shards):
            row_y = y + 2 + i * 3
            if row_y >= y + h:
                break

            self.term.move(x, row_y)

            # Pre/Post nodes
            pre = f"PRE_0{i+1}"
            post = f"POST_0{i+1}"

            # Connection status
            if shard.verified:
                conn = self.color(self.colors.COMPLEMENT_GOLD, f"{self.sym.ACTIVE}───────{self.sym.FUSED}")
                status = self.color(self.colors.COMPLEMENT_GOLD, "[complete]")
            elif shard.present:
                conn = self.color(self.colors.CYAN_ELECTRIC, f"{self.anim.get_pulse()}───────{self.sym.CHARGED}")
                status = self.color(self.colors.CYAN_ELECTRIC, "[charging]")
            else:
                conn = self.color(self.colors.DORMANT_GRAY, f"{self.sym.DORMANT}───────{self.sym.DORMANT}")
                status = self.color(self.colors.DORMANT_GRAY, "[standby]")

            line = f"{pre} >{conn}> {post}  {status}"
            self.term.print_at(x, row_y, line[:w])

            # Progress bar (if assembling)
            if shard.present and not shard.verified:
                bar_y = row_y + 1
                if bar_y < y + h:
                    self.term.move(x + 10, bar_y)
                    filled = int(shard.progress / 100 * 20)
                    bar = "█" * filled + "░" * (20 - filled)
                    bar = "█" * filled + "░" * (20 - filled)
                    self.term.write(f"{self.colors.CYAN_ELECTRIC}└ decrypting... [{bar}]{self.colors.RESET}")

        # Bottom stats
        stats_y = y + h - 2
        if stats_y > y + 2:
            self.term.move(x, stats_y)
            stats = f"CHARGE: {self.state.assembly_progress:.0f}% | NODES: {sum(1 for s in self.state.shards if s.present)}/3"
            print(self.color(self.colors.MUTED_BLUE, stats))

    def _draw_pharmacode(self, x: int, y: int, w: int, h: int):
        """Model loading/training visualization"""
        self.term.print_at(x, y, f"{self.colors.SYNAPSE_VIOLET}PHARMACODE INJECTION{self.colors.RESET}")

        ampule_names = ["TiDAR_DIFFUSION", "ROPE_EMBEDDINGS", "EXPERT_MoE"]

        for i, name in enumerate(ampule_names):
            row_y = y + 2 + i * 3
            if row_y >= y + h - 1:
                break

            ampule = self.state.ampules.get(name.split("_")[0], {"progress": 0, "status": "standby"})

            self.term.move(x, row_y)

            # 8-segment progress bar (efficient)
            prog = ampule["progress"]
            filled = int(prog / 100 * 8)
            bar = "█" * filled + "▒" * (8 - filled)

            # Status indicator
            if ampule["status"] == "running":
                status_sym = self.color(self.colors.WARNING_AMBER, self.anim.get_spinner())
                status_text = self.color(self.colors.WARNING_AMBER, "[running]")
            elif ampule["status"] == "complete":
                status_sym = self.color(self.colors.COMPLEMENT_GOLD, self.sym.FUSED)
                status_text = self.color(self.colors.COMPLEMENT_GOLD, "[complete]")
            else:
                status_sym = self.color(self.colors.DORMANT_GRAY, self.sym.DORMANT)
                status_text = self.color(self.colors.DORMANT_GRAY, "[standby]")

            line = f"{name[:15]:<15} [{self.colors.CYAN_ELECTRIC}{bar}{self.colors.RESET}] {prog:>3}% {status_sym} {status_text}"
            self.term.print_at(x, row_y, line[:w])

        # Metrics
        self.term.move(x, y + h - 2)
        metrics = f"VISCOSITY: 1.2cp | pH: 7.35 | TEMP: 310K"
        print(self.color(self.colors.MUTED_BLUE, metrics))

    def _draw_breach(self, x: int, y: int, w: int, h: int):
        """Breach alert overlay"""
        # Full zone red background
        for row in range(y, y + h):
            self.term.print_at(x, row, f"{self.colors.BREACH_BG}{' ' * (w-1)}{self.colors.RESET}")

        # Center text
        center_y = y + h // 2
        self.term.print_at(x + 2, center_y - 2, f"{self.colors.BREACH_RED}{self.sym.BREACH} BREACH DETECTED{self.colors.RESET}")

        self.term.print_at(x + 2, center_y, f"{self.colors.WHITE_MATTER}Critical: {self.state.last_breach or 'Unknown'}{self.colors.RESET}")

        self.term.print_at(x + 2, center_y + 2, f"{self.colors.WARNING_AMBER}[Enter] Isolate  [s] Audit  [L] Lockdown{self.colors.RESET}")

    def _draw_maintenance(self, x: int, y: int, w: int, h: int):
        """Idle/Maintenance view"""
        self.term.print_at(x, y, f"{self.colors.SYNAPSE_VIOLET}SYSTEM MAINTENANCE{self.colors.RESET}")

        info = [
            f"Mode: {self.state.mode.name}",
            f"Neurons: {len(self.state.neurons)}",
            f"Documents: {len(self.state.documents)}",
            "",
            "Press 'h' for help"
        ]

        for i, line in enumerate(info):
            row_y = y + 2 + i
            if row_y >= y + h:
                break
            self.term.print_at(x, row_y, self.color(self.colors.MUTED_BLUE, line))

class OperationsBayZone(ZoneRenderer):
    """Zone 4: Bottom-right - RAG lab and chat"""

    def draw(self):
        w = self.term.width
        h = self.term.height
        left_w = max(20, w // 4)
        zone_w = w - left_w - 1
        zone_h = (h - 3) // 2
        top_h = zone_h

        start_x = left_w + 2
        start_y = 3 + top_h

        # Border line above
        self.term.print_at(left_w + 1, start_y - 1, f"{self.colors.DEEP_PURPLE}{self.sym.HLINE * (zone_w)}{self.colors.RESET}")

        # Title
        self.term.print_at(start_x, start_y, f"{self.colors.CYBER_BLUE}OPERATIONS BAY{self.colors.RESET}")

        # Document list (last 3)
        doc_y = start_y + 2
        self.term.print_at(start_x, doc_y, self.color(self.colors.MUTED_BLUE, "Recent Documents:"))

        for i, doc in enumerate(self.state.documents[-3:]):
            row_y = doc_y + 1 + i
            if row_y >= start_y + zone_h - 3:
                break
            self.term.move(start_x + 2, row_y)
            status = self.sym.FUSED if doc.get('embedded') else self.sym.DORMANT
            color = self.colors.COMPLEMENT_GOLD if doc.get('embedded') else self.colors.DORMANT_GRAY
            self.term.write(f"{self.color(color, status)} {doc.get('name', 'Unknown')[:30]}")

        # Chat area
        chat_y = start_y + zone_h - 5

        # Messages (last 2)
        for msg in self.state.messages[-2:]:
            chat_y += 1
            if chat_y >= start_y + zone_h - 2:
                break
            content = msg.get('content', '')[:zone_w-10]
            role = msg.get('role', 'assistant')
            if role == 'user':
                self.term.print_at(start_x, chat_y, f"{self.colors.WHITE_MATTER}> {content}{self.colors.RESET}")
            else:
                self.term.print_at(start_x, chat_y, f"{self.colors.CYAN_ELECTRIC}🐝 {content}{self.colors.RESET}")

        # Input prompt
        input_y = start_y + zone_h - 1
        self.term.move(start_x, input_y)
        prompt = f">>> {self.state.input_buffer}"
        self.term.write(f"{self.colors.ACTIVE_MAGENTA}{prompt}{self.colors.RESET}")

class CommandFooterZone(ZoneRenderer):
    """Bottom command bar"""

    def draw(self):
        w = self.term.width
        h = self.term.height

        self.term.move(1, h - 1)

        # Global hotkeys
        keys = [
            ("h", "Help"),
            ("v", "Voice"),
            ("s", "Scan"),
            ("L", "Lockdown"),
            (":q", "Back"),
            ("Q", "Quit")
        ]

        footer = "  ".join([f"[{self.colors.COMPLEMENT_GOLD}{k}{self.colors.RESET}] {self.colors.MUTED_BLUE}{v}{self.colors.RESET}" 
                          for k, v in keys])

        # Mode indicator
        mode_str = f"[{self.state.mode.name}]"

        space = w - len(footer.replace(self.colors.COMPLEMENT_GOLD, "").replace(self.colors.MUTED_BLUE, "").replace(self.colors.RESET, "")) - len(mode_str) - 4

        line = f"{footer}{' ' * space}{self.colors.SYNAPSE_VIOLET}{mode_str}{self.colors.RESET}"
        self.term.print_at(1, h - 1, line)

# ---------------------------------------------------------------------------
# Input Handler
# ---------------------------------------------------------------------------

class InputHandler:
    """Keyboard input processing"""

    def __init__(self, state: HiveState, term: Terminal, hivemind_getter=None):
        self.state = state
        self.term = term
        self.running = True
        self.input_mode = False
        self._get_hivemind = hivemind_getter  # True when typing in Operations Bay

    def process(self, key: str) -> bool:
        """Process key press, return False to quit"""
        if not key:
            return True

        # Global hotkeys (always active)
        if key == 'Q':  # Shift+Q - Quit
            return False

        if key == 'h':  # Help
            self._show_help()
            return True

        if key == 'v':  # Voice toggle
            self.state.voice_listening = not self.state.voice_listening
            return True

        if key == 's':  # Security scan
            self.state.security = SecurityStatus.SCANNING
            threading.Timer(3.0, lambda: setattr(self.state, 'security', SecurityStatus.SECURE)).start()
            return True

        if key == 'L':  # Lockdown
            self.state.security = SecurityStatus.LOCKDOWN
            return True

        if key == ':':  # Command mode prefix
            self._command_mode()
            return True

        # Mode-specific handling
        if self.state.mode == UIMode.BREACH:
            self._handle_breach(key)
        elif self.state.mode == UIMode.OPERATIONS:
            self._handle_operations(key)
        else:
            self._handle_navigation(key)

        return True

    def _handle_navigation(self, key: str):
        """Vim-style navigation"""
        if key == 'j':  # Down
            self.state.selected_neuron = min(len(self.state.neurons) - 1, 
                                            self.state.selected_neuron + 1)
        elif key == 'k':  # Up
            self.state.selected_neuron = max(0, self.state.selected_neuron - 1)
        elif key == ' ':  # Toggle neuron
            neuron = self.state.neurons[self.state.selected_neuron]
            if neuron.state == "dormant":
                neuron.state = "standby"
            elif neuron.state == "standby":
                neuron.state = "active"
            else:
                neuron.state = "dormant"
        elif key == 'a':  # Arm all
            for n in self.state.neurons:
                if n.state == "dormant":
                    n.state = "standby"
        elif key == 'd':  # Disarm all
            for n in self.state.neurons:
                if n.state in ("active", "standby"):
                    n.state = "dormant"

    def _handle_operations(self, key: str):
        """Operations Bay input handling"""
        if key == 'i':  # Enter input mode
            self.input_mode = True
        elif self.input_mode:
            if key == '\r':  # Enter - submit
                self.state.messages.append({
                    'role': 'user',
                    'content': self.state.input_buffer
                })
                self.state.input_buffer = ""
                self.input_mode = False
                
                # Non-blocking input handling
                def _bg_process():
                    try:
                        hive = self._get_hivemind()
                        if hive:
                            instance_id = hive.deploy_chat(self.state.input_buffer)
                            self.state.messages.append({
                                'role': 'assistant',
                                'content': f'🐝 Bee spawned: {instance_id[:8]}...'
                            })
                    except Exception as e:
                         self.state.messages.append({
                            'role': 'assistant',
                            'content': f'❌ Error: {str(e)[:50]}'
                        })
                
                threading.Thread(target=_bg_process, daemon=True).start()
            elif key == '\x7f':  # Backspace
                self.state.input_buffer = self.state.input_buffer[:-1]
            elif ord(key) >= 32:  # Printable
                self.state.input_buffer += key
        else:
            self._handle_navigation(key)

    def _handle_breach(self, key: str):
        """Breach mode handling"""
        if key == '\r':  # Enter - isolate
            self.state.security = SecurityStatus.LOCKDOWN
        elif key == 's':  # Scan
            self.state.security = SecurityStatus.SCANNING
        elif key == 'L':  # Lockdown
            self.state.security = SecurityStatus.LOCKDOWN

    def _show_help(self):
        """Show help overlay"""
        # Simple help - in full implementation, overlay on current screen
        pass

    def _command_mode(self):
        """Handle : commands"""
        # Read command
        cmd = ""
        while True:
            key = self.term.read_key(0.1)
            if key == '\r':
                break
            if key:
                cmd += key

        if cmd == 'q':
            if self.state.previous_mode:
                self.state.mode = self.state.previous_mode
                self.state.previous_mode = None
        elif cmd == ' assembly':
            self.state.previous_mode = self.state.mode
            self.state.mode = UIMode.NEURAL_ASSEMBLY
        elif cmd == ' pharmacode':
            self.state.previous_mode = self.state.mode
            self.state.mode = UIMode.PHARMACODE
        elif cmd == ' operations':
            self.state.previous_mode = self.state.mode
            self.state.mode = UIMode.OPERATIONS

# ---------------------------------------------------------------------------
# Main TUI Application
# ---------------------------------------------------------------------------

class SynapticFortress:
    """Main TUI application"""

    def __init__(self):
        self.term = Terminal()
        self.state = HiveState()
        self.animator = Animator(self.state)
        self._hivemind = None
        self.input_handler = InputHandler(self.state, self.term, self._get_hivemind)

        # Zone renderers
        self.perimeter = PerimeterZone(self.term, self.state, self.animator)
        self.sentinel = SentinelGridZone(self.term, self.state, self.animator)
        self.activation = ActivationChamberZone(self.term, self.state, self.animator)
        self.operations = OperationsBayZone(self.term, self.state, self.animator)
        self.footer = CommandFooterZone(self.term, self.state, self.animator)

    def run(self):
        """Main loop"""
        try:
            self.term.setup()
            self.term.hide_cursor()
            self.term.clear()

            last_draw = 0

            while self.input_handler.running:
                # Animation tick
                frame_changed = self.animator.tick()

                # Draw at 4fps or on input
                now = time.time()
                if frame_changed or now - last_draw > 0.25:
                    self._draw()
                    last_draw = now

                # Handle input
                key = self.term.read_key(0.05)
                if key:
                    if not self.input_handler.process(key):
                        break

        finally:
            self.term.show_cursor()
            self.term.restore()
            print("\nSynaptic Fortress terminated.")

    def _get_hivemind(self):
        """Lazy initialization of HiveMind"""
        if self._hivemind is None:
            try:
                config = HiveConfig.from_yaml('./hivemind.yaml')
                self._hivemind = HiveMind(config)
            except Exception:
                self._hivemind = HiveMind()
        return self._hivemind

    def _draw(self):
        """Render all zones"""
        # Update terminal size
        self.term.update_size()

        # Draw zones
        self.perimeter.draw()
        self.sentinel.draw()
        self.activation.draw()
        self.operations.draw()
        self.footer.draw()

        # Flush output
        sys.stdout.flush()

    # --- Public API for external integration ---

    def set_mode(self, mode: UIMode):
        """Change UI mode programmatically"""
        self.state.previous_mode = self.state.mode
        self.state.mode = mode

    def update_neuron(self, name: str, state: str, alert: str = None):
        """Update neuron status from external system"""
        for neuron in self.state.neurons:
            if neuron.name == name:
                neuron.state = state
                neuron.alert = alert
                break

    def add_message(self, role: str, content: str):
        """Add chat message"""
        self.state.messages.append({'role': role, 'content': content})

    def set_shard_status(self, shard_id: int, present: bool, verified: bool):
        """Update Ghost Shell shard status"""
        for shard in self.state.shards:
            if shard.id == shard_id:
                shard.present = present
                shard.verified = verified
                break

    def trigger_breach(self, message: str):
        """Trigger breach alert"""
        self.state.security = SecurityStatus.BREACH_DETECTED
        self.state.last_breach = message
        self.state.mode = UIMode.BREACH

# ---------------------------------------------------------------------------
# Integration Helpers
# ---------------------------------------------------------------------------

def launch_tui(**kwargs):
    """Launch TUI with optional initial state"""
    fortress = SynapticFortress()

    # Apply initial state
    if 'mode' in kwargs:
        fortress.set_mode(kwargs['mode'])
    if 'neurons' in kwargs:
        fortress.state.neurons = kwargs['neurons']

    fortress.run()

def tui_thread(**kwargs) -> threading.Thread:
    """Launch TUI in background thread, return control immediately"""
    thread = threading.Thread(target=launch_tui, kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Synaptic Fortress TUI")
    parser.add_argument("--mode", choices=["assembly", "pharmacode", "operations", "maintenance"],
                       default="operations", help="Initial mode")
    parser.add_argument("--test-data", action="store_true", help="Load test data")

    args = parser.parse_args()

    mode_map = {
        "assembly": UIMode.NEURAL_ASSEMBLY,
        "pharmacode": UIMode.PHARMACODE,
        "operations": UIMode.OPERATIONS,
        "maintenance": UIMode.MAINTENANCE
    }

    fortress = SynapticFortress()
    fortress.state.mode = mode_map.get(args.mode, UIMode.OPERATIONS)

    if args.test_data:
        # Load demo data
        fortress.state.shards[0].present = True
        fortress.state.shards[0].verified = True
        fortress.state.shards[1].present = True
        fortress.state.assembly_progress = 66.0
        fortress.state.documents = [
            {'name': 'security_audit.pdf', 'embedded': True},
            {'name': 'research_notes.md', 'embedded': True},
            {'name': 'todo.txt', 'embedded': False}
        ]
        fortress.state.messages = [
            {'role': 'user', 'content': 'Analyze the security audit'},
            {'role': 'assistant', 'content': 'I found 3 critical vulnerabilities...'}
        ]

    fortress.run()