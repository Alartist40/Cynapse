"""
Cynapse TUI State Management

Centralized state management for the Synaptic Fortress Interface.
Uses Observer pattern for efficient UI updates.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Any, Callable, Optional
from datetime import datetime


class Mode(Enum):
    """Interface modes."""
    NEURAL_ASSEMBLY = auto()    # USB shard combination
    PHARMACODE_INJECTION = auto()  # Model loading/training
    OPERATIONS = auto()          # RAG Laboratory
    PERIMETER_BREACH = auto()    # Emergency mode
    MAINTENANCE = auto()         # System idle


class NeuronStatus(Enum):
    """Status of individual neurons."""
    DORMANT = "dormant"
    STANDBY = "standby"
    ACTIVE = "active"
    ERROR = "error"


class SecurityStatus(Enum):
    """Overall security status."""
    SECURE = "secure"
    SCANNING = "scanning"
    BREACH = "breach"


@dataclass
class ShardStatus:
    """Status of a Ghost Shell shard."""
    shard_id: int
    mounted: bool = False
    verified: bool = False
    progress: float = 0.0
    
    @property
    def status_text(self) -> str:
        if not self.mounted:
            return "not mounted"
        if not self.verified:
            return "verifying"
        return "ready"


@dataclass 
class DocumentStatus:
    """Status of a RAG document."""
    path: str
    name: str
    embedded: bool = False
    timestamp: Optional[datetime] = None


@dataclass
class CynapseState:
    """
    Centralized state for the TUI.
    
    This is the single source of truth for all interface state.
    UI updates are triggered by state changes through observers.
    """
    
    # Current interface mode
    mode: Mode = Mode.MAINTENANCE
    
    # Security status
    security_status: SecurityStatus = SecurityStatus.SECURE
    integrity_percentage: float = 100.0
    last_breach: Optional[datetime] = None
    voice_monitor_active: bool = False
    
    # Neuron states (neuron_id -> status)
    neurons: Dict[str, NeuronStatus] = field(default_factory=dict)
    selected_neuron_index: int = 0
    
    # Ghost Shell assembly
    shards: List[ShardStatus] = field(default_factory=lambda: [
        ShardStatus(1), ShardStatus(2), ShardStatus(3)
    ])
    assembly_progress: float = 0.0
    assembly_throughput: float = 0.0
    
    # Pharmacode injection
    model_name: str = ""
    model_progress: float = 0.0
    model_status: str = "standby"
    
    # Operations Bay
    documents: List[DocumentStatus] = field(default_factory=list)
    document_count: int = 0
    training_progress: float = 0.0
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    current_prompt: str = ""
    
    # UI state
    active_zone: int = 2  # 1=Perimeter, 2=Sentinel, 3=Activation, 4=Operations
    help_visible: bool = False
    
    # Observers for state changes
    _observers: List[Callable[['CynapseState', str], None]] = field(
        default_factory=list, repr=False
    )
    
    def add_observer(self, callback: Callable[['CynapseState', str], None]):
        """Add an observer callback for state changes."""
        self._observers.append(callback)
    
    def remove_observer(self, callback: Callable[['CynapseState', str], None]):
        """Remove an observer callback."""
        if callback in self._observers:
            self._observers.remove(callback)
    
    def _notify(self, changed_field: str):
        """Notify all observers of a state change."""
        for observer in self._observers:
            try:
                observer(self, changed_field)
            except Exception:
                pass  # Don't let observer errors crash the UI
    
    # State update methods
    def set_mode(self, mode: Mode):
        """Change the interface mode."""
        self.mode = mode
        self._notify('mode')
    
    def set_security_status(self, status: SecurityStatus):
        """Update security status."""
        self.security_status = status
        if status == SecurityStatus.BREACH:
            self.last_breach = datetime.now()
            self.mode = Mode.PERIMETER_BREACH
        self._notify('security_status')
    
    def set_neuron_status(self, neuron_id: str, status: NeuronStatus):
        """Update a neuron's status."""
        self.neurons[neuron_id] = status
        self._notify('neurons')
    
    def toggle_voice_monitor(self):
        """Toggle voice monitor on/off."""
        self.voice_monitor_active = not self.voice_monitor_active
        self._notify('voice_monitor')
    
    def update_shard(self, shard_id: int, **kwargs):
        """Update a shard's status."""
        for shard in self.shards:
            if shard.shard_id == shard_id:
                for key, value in kwargs.items():
                    if hasattr(shard, key):
                        setattr(shard, key, value)
                break
        self._notify('shards')
    
    def update_assembly_progress(self, progress: float, throughput: float = 0.0):
        """Update Ghost Shell assembly progress."""
        self.assembly_progress = progress
        self.assembly_throughput = throughput
        self._notify('assembly')
    
    def add_document(self, path: str, name: str, embedded: bool = False):
        """Add a document to the RAG system."""
        doc = DocumentStatus(path=path, name=name, embedded=embedded, timestamp=datetime.now())
        self.documents.insert(0, doc)
        self.document_count = len(self.documents)
        self._notify('documents')
    
    def add_chat_message(self, role: str, content: str):
        """Add a message to chat history."""
        self.chat_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        self._notify('chat')
    
    def cycle_zone(self):
        """Cycle to the next zone."""
        self.active_zone = (self.active_zone % 4) + 1
        self._notify('zone')
    
    def navigate_neurons(self, direction: int):
        """Navigate through neuron list."""
        neuron_count = len(self.neurons)
        if neuron_count > 0:
            self.selected_neuron_index = (self.selected_neuron_index + direction) % neuron_count
            self._notify('selection')
    
    def toggle_help(self):
        """Toggle help overlay visibility."""
        self.help_visible = not self.help_visible
        self._notify('help')
    
    # Query methods
    @property
    def mounted_shards(self) -> int:
        """Count of mounted shards."""
        return sum(1 for s in self.shards if s.mounted)
    
    @property
    def shard_status_string(self) -> str:
        """Format shard status like ●●○"""
        return ''.join('●' if s.mounted else '○' for s in self.shards)
    
    def get_neuron_list(self) -> List[tuple]:
        """Get sorted list of (neuron_id, status) tuples."""
        return sorted(self.neurons.items())
    
    def get_selected_neuron(self) -> Optional[str]:
        """Get the currently selected neuron ID."""
        neurons = self.get_neuron_list()
        if neurons and 0 <= self.selected_neuron_index < len(neurons):
            return neurons[self.selected_neuron_index][0]
        return None


# Global state instance (singleton pattern)
_state: Optional[CynapseState] = None


def get_state() -> CynapseState:
    """Get the global state instance."""
    global _state
    if _state is None:
        _state = CynapseState()
    return _state


def reset_state():
    """Reset the global state (mainly for testing)."""
    global _state
    _state = CynapseState()
