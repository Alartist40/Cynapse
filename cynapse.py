#!/usr/bin/env python3
"""
Cynapse v1.0 - Ghost Shell Hub
The orchestrator for 12 security neurons with voice control and distributed AI.

Author: Alejandro Eduardo Garcia Romero
License: MIT
"""

import json
import time
import hashlib
import logging
import subprocess
import threading
import configparser
import sys
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass  # Ignore if reconfigure not available

# ASCII Art Logo
LOGO = r"""
   _____                                  
  / ____|                                 
 | |    _   _ _ __   __ _ _ __  ___  ___ 
 | |   | | | | '_ \ / _` | '_ \/ __|/ _ \
 | |___| |_| | | | | (_| | |_) \__ \  __/
  \_____\__, |_| |_|\__,_| .__/|___/\___|
         __/ |           | |             
        |___/            |_|   Ghost Shell Hub
"""

# Get base directory
BASE_DIR = Path(__file__).parent.resolve()
# Security: Keywords that trigger redaction in audit logs
SENSITIVE_KEYWORDS = [
    'key', 'secret', 'token', 'password', 'seed', 'auth', 'private',
    'apikey', 'bearer', 'passphrase', 'access_key', 'secret_key', 'credentials'
]
NEURONS_DIR = BASE_DIR / "neurons"
TEMP_DIR = BASE_DIR / "temp"
CONFIG_DIR = BASE_DIR / "config"
LOG_FILE = BASE_DIR / ".cynapse" / "logs" / "audit.ndjson"


@dataclass
class NeuronManifest:
    """Represents a neuron's manifest.json"""
    name: str
    version: str
    description: str
    author: str
    animal: str
    platform: List[str]
    entry_point: str
    requires_signature: bool
    dependencies: List[str]
    commands: Dict[str, str]
    path: Path


class Neuron:
    """Represents a single neuron (tool) in the Cynapse ecosystem."""
    
    def __init__(self, path: Path):
        self.path = path
        self.manifest = self._load_manifest()
        self.binary = self._find_binary()
        self.signature = path / "signature.sig" if self.manifest.requires_signature else None
        
    def _load_manifest(self) -> NeuronManifest:
        """Load the neuron's manifest.json"""
        manifest_path = self.path / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return NeuronManifest(
            name=data.get("name", self.path.name),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
            animal=data.get("animal", ""),
            platform=data.get("platform", ["win", "linux", "mac"]),
            entry_point=data.get("entry_point", "main.py"),
            requires_signature=data.get("requires_signature", False),
            dependencies=data.get("dependencies", []),
            commands=data.get("commands", {}),
            path=self.path
        )
    
    def _find_binary(self) -> Optional[Path]:
        """Find the entry point binary/script"""
        from utils.security import validate_path_traversal

        entry = self.path / self.manifest.entry_point

        # Security: Prevent path traversal using a robust method.
        if not validate_path_traversal(self.path, entry, f"neuron '{self.manifest.name}'"):
            return None

        if entry.exists():
            return entry
        
        # Try common extensions, ensuring they are also validated.
        for ext in ['.py', '.exe', '.sh', '.ps1']:
            for candidate in self.path.glob(f"*{ext}"):
                # Perform the same path traversal check on the fallback candidate.
                if validate_path_traversal(self.path, candidate, f"neuron '{self.manifest.name}' fallback"):
                    return candidate  # Return the first valid candidate.
        return None
    
    def verify(self) -> bool:
        """Verify the neuron's signature if required."""
        if not self.manifest.requires_signature:
            return True
            
        if not self.signature or not self.signature.exists():
            return False
            
        # Use elephant_sign verifier if available
        verifier = NEURONS_DIR / "elephant_sign" / "verify.py"
        if not verifier.exists():
            print(f"CRITICAL: Signature verifier 'elephant_sign' not found. Cannot verify neuron '{self.manifest.name}'.")
            return False

        if self.binary:
            try:
                result = subprocess.run(
                    [sys.executable, str(verifier), str(self.binary)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0
            except Exception:
                return False

        # Fails if binary does not exist
        return False
    
    def execute(self, *args, **kwargs) -> subprocess.CompletedProcess:
        """Execute the neuron with given arguments."""
        if not self.binary:
            raise RuntimeError(f"No binary found for neuron: {self.manifest.name}")
        
        cmd = []
        if self.binary.suffix == '.py':
            cmd = [sys.executable, str(self.binary)]
        elif self.binary.suffix in ['.exe', '']:
            cmd = [str(self.binary)]
        elif self.binary.suffix == '.sh':
            cmd = ['bash', str(self.binary)]
        elif self.binary.suffix == '.ps1':
            cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(self.binary)]
        
        cmd.extend(args)
        
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.path),
            timeout=kwargs.get('timeout', 300)
        )


class AuditLogger:
    """NDJSON audit logger for Cynapse events."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Security: Restrict directory permissions to owner only (0700)
        if os.name != 'nt':
            try:
                os.chmod(self.log_file.parent, 0o700)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Security: Failed to set restricted permissions on log directory {self.log_file.parent}",
                    exc_info=True
                )
        
    def log(self, event: str, data: Dict[str, Any] = None):
        """Log an event in NDJSON format."""
        entry = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            "data": data or {}
        }

        with self._lock:
            try:
                # Security: Use os.open with O_CREAT and mode 0o600 for restricted file creation.
                # Use explicit utf-8 encoding for consistency.
                flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
                fd = os.open(self.log_file, flags, 0o600)
                with os.fdopen(fd, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + '\n')

                # Best effort: ensure existing file permissions are also restricted
                if os.name != 'nt':
                    os.chmod(self.log_file, 0o600)
            except Exception as e:
                # Fail securely: log to stderr but don't crash the hub if logging fails
                print(f"CRITICAL: Failed to write to audit log: {e}", file=sys.stderr)


class CynapseHub:
    """The main orchestrator for all Cynapse neurons."""
    
    def __init__(self):
        self.config = self._load_config()
        self.logger = AuditLogger(LOG_FILE)
        self.neurons: Dict[str, Neuron] = {}
        self._voice_thread = None
        self._running = False
        self._lock = threading.RLock()  # Thread safety for Hub state and execution
        
        # Discover neurons
        self._discover_neurons()
        self.logger.log("hub_initialized", {"neurons_count": len(self.neurons)})
        
    def _load_config(self) -> configparser.ConfigParser:
        """Load configuration from config.ini"""
        config = configparser.ConfigParser()
        config_file = CONFIG_DIR / "config.ini"
        example_file = CONFIG_DIR / "config.ini.example"
        
        if config_file.exists():
            config.read(config_file)
        elif example_file.exists():
            config.read(example_file)
            
        return config
    
    def _discover_neurons(self):
        """Discover all neurons in the neurons/ directory."""
        if not NEURONS_DIR.exists():
            return
            
        with self._lock:
            for path in NEURONS_DIR.iterdir():
                if not path.is_dir():
                    continue
                if path.name.startswith('_'):
                    continue

                manifest_file = path / "manifest.json"
                if not manifest_file.exists():
                    continue

                try:
                    neuron = Neuron(path)
                    self.neurons[neuron.manifest.name.lower()] = neuron
                except Exception as e:
                    print(f"Warning: Failed to load neuron {path.name}: {e}")
    
    def list_neurons(self) -> List[str]:
        """List all available neuron names."""
        return list(self.neurons.keys())

    def get_all_neurons(self) -> List[Neuron]:
        """Get all loaded neuron objects."""
        return list(self.neurons.values())
    
    def get_neuron(self, name: str) -> Optional[Neuron]:
        """Get a neuron by name."""
        return self.neurons.get(name.lower())
    
    def run_neuron(self, name: str, *args, **kwargs) -> Optional[subprocess.CompletedProcess]:
        """
        Run a neuron with given arguments (thread-safe).

        Args:
            name: Name of the neuron
            *args: Arguments to pass to the neuron
            **kwargs:
                silent: If True, don't print errors to stdout
                timeout: Custom timeout for execution
        """
        with self._lock:
            silent = kwargs.get('silent', False)
            neuron = self.get_neuron(name)

            if not neuron:
                self.logger.log("neuron_not_found", {"name": name})
                if not silent:
                    print(f"Error: Neuron '{name}' not found")
                return None

            if not neuron.verify():
                self.logger.log("signature_verification_failed", {"name": name})
                if not silent:
                    print(f"Error: Signature verification failed for '{name}'")
                return None

            # Security: Redact potentially sensitive arguments to prevent information disclosure in logs.
            redacted_args = []
            for arg in args:
                arg_str = str(arg)
                if len(arg_str) > 64 or any(kw in arg_str.lower() for kw in SENSITIVE_KEYWORDS):
                    redacted_args.append(f"<redacted:{len(arg_str)} chars>")
                else:
                    redacted_args.append(arg_str)

            self.logger.log("neuron_execute_start", {"name": name, "args": redacted_args})

            try:
                result = neuron.execute(*args, timeout=kwargs.get('timeout', 300))
                self.logger.log("neuron_execute_complete", {
                    "name": name,
                    "returncode": result.returncode,
                    "stdout_len": len(result.stdout),
                    "stderr_len": len(result.stderr)
                })
                return result
            except Exception as e:
                # Security: Subprocess errors often contain the full command line with arguments.
                error_type = type(e).__name__
                if isinstance(e, subprocess.TimeoutExpired):
                    error_msg = f"Command timed out after {e.timeout}s"
                elif isinstance(e, subprocess.CalledProcessError):
                    error_msg = f"Command failed with return code {e.returncode}"
                else:
                    error_msg = str(e)

                # Final safety check for sensitive keywords in any error message
                if any(kw in error_msg.lower() for kw in SENSITIVE_KEYWORDS) or len(error_msg) > 256:
                    error_msg = f"{error_type} (sensitive or verbose details redacted)"

                self.logger.log("neuron_execute_error", {"name": name, "error": error_msg})
                if not silent:
                    print(f"Error executing {name}: {error_msg}")
                return None
    
    def start_voice_listener(self):
        """Start the voice control listener in a background thread."""
        if self._voice_thread and self._voice_thread.is_alive():
            return
            
        self._running = True
        self._voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self._voice_thread.start()
        self.logger.log("voice_listener_started", {})
        
    def stop_voice_listener(self):
        """Stop the voice control listener."""
        self._running = False
        if self._voice_thread:
            self._voice_thread.join(timeout=2)
        self.logger.log("voice_listener_stopped", {})
        
    def _voice_loop(self):
        """Background voice detection loop."""
        # Check if whistle detector is available
        whistle_detector = NEURONS_DIR / "bat_ghost" / "whistle_detector.py"
        if not whistle_detector.exists():
            print("Warning: Whistle detector not found, voice control disabled")
            return
            
        while self._running:
            try:
                result = subprocess.run(
                    [sys.executable, str(whistle_detector), "--detect-once"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "WHISTLE_DETECTED" in result.stdout:
                    self.logger.log("whistle_detected", {})
                    self._handle_whistle()
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                # Security: Sanitize error messages in the voice loop to prevent information leakage.
                error_msg = str(e)
                if any(kw in error_msg.lower() for kw in SENSITIVE_KEYWORDS) or len(error_msg) > 256:
                    error_msg = f"{type(e).__name__} (redacted)"
                self.logger.log("voice_loop_error", {"error": error_msg})
            
            time.sleep(0.1)
    
    def _handle_whistle(self):
        """Handle whistle detection - assemble Ghost Shell and respond."""
        print("\n🦇 Whistle detected! Assembling Ghost Shell...")
        
        assembler = NEURONS_DIR / "bat_ghost" / "assemble.py"
        if assembler.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(assembler)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print("✅ Ghost Shell assembled successfully!")
                    self.logger.log("ghost_shell_assembled", {})
                else:
                    print(f"⚠️ Assembly warning: {result.stderr}")
            except Exception as e:
                print(f"❌ Assembly failed: {e}")
    
    def cli_loop(self):
        """Run the interactive CLI loop."""
        print(LOGO)
        print(f"\n🦌 Cynapse Hub v1.0 initialized")
        print(f"📦 {len(self.neurons)} neurons loaded: {', '.join(n.manifest.animal or n.manifest.name for n in self.neurons.values())}")
        print("\nType 'help' for commands, 'list' for neurons, or a neuron name to run it.")
        print("Type 'voice' to enable voice control, 'exit' to quit.\n")
        
        while True:
            try:
                cmd = input("cynapse> ").strip()
                if not cmd:
                    continue
                    
                parts = cmd.split()
                command = parts[0].lower()
                args = parts[1:]
                
                if command in ['exit', 'quit', 'q']:
                    self.stop_voice_listener()
                    print("Goodbye!")
                    break
                elif command == 'help':
                    self._show_help()
                elif command == 'list':
                    self._list_neurons()
                elif command == 'voice':
                    print("Starting voice listener...")
                    self.start_voice_listener()
                    print("Whistle 18 kHz to wake Ghost Shell")
                elif command == 'status':
                    self._show_status()
                elif command == 'test':
                    self._run_tests()
                else:
                    # Try to run as neuron
                    result = self.run_neuron(command, *args)
                    if result:
                        if result.stdout:
                            print(result.stdout)
                        if result.stderr:
                            print(f"[stderr] {result.stderr}", file=sys.stderr)
                            
            except KeyboardInterrupt:
                print("\nInterrupted. Type 'exit' to quit.")
            except EOFError:
                break
    
    def _show_help(self):
        """Show help information."""
        print("""
Cynapse Hub Commands:
  help      - Show this help message
  list      - List all available neurons
  status    - Show hub status
  voice     - Start voice control listener
  test      - Run verification tests
  exit      - Exit the hub
  
Neuron Commands:
  <neuron_name> [args...]  - Run a neuron with optional arguments
  
Examples:
  cynapse> list
  cynapse> meerkat scan 192.168.1.0/24
  cynapse> owl redact document.pdf
  cynapse> voice
""")
    
    def _list_neurons(self):
        """List all available neurons."""
        print("\nAvailable Neurons:")
        print("-" * 60)
        for name, neuron in sorted(self.neurons.items()):
            animal = neuron.manifest.animal or "🔧"
            desc = neuron.manifest.description[:40] + "..." if len(neuron.manifest.description) > 40 else neuron.manifest.description
            print(f"  {animal:12} {name:20} - {desc}")
        print("-" * 60)
        print(f"Total: {len(self.neurons)} neurons")
    
    def _show_status(self):
        """Show current hub status."""
        print(f"""
Cynapse Hub Status:
  Neurons loaded: {len(self.neurons)}
  Voice control:  {'Active' if self._voice_thread and self._voice_thread.is_alive() else 'Inactive'}
  Log file:       {LOG_FILE}
  Temp dir:       {TEMP_DIR}
""")
    
    def _run_tests(self):
        """Run basic verification tests."""
        print("Running verification tests...")
        passed = 0
        failed = 0
        
        for name, neuron in self.neurons.items():
            try:
                if neuron.verify():
                    print(f"  ✅ {name}: signature OK")
                    passed += 1
                else:
                    print(f"  ❌ {name}: signature FAILED")
                    failed += 1
            except Exception as e:
                print(f"  ⚠️ {name}: error - {e}")
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        return failed == 0


def supports_tui() -> bool:
    """Check if the current terminal supports the modern TUI."""
    if not sys.stdout.isatty():
        return False

    term = os.getenv('TERM', '').lower()
    if term in ['dumb', 'vt100', 'linux']:
        return False

    return True


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            hub = CynapseHub()
            success = hub._run_tests()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == '--list':
            hub = CynapseHub()
            hub._list_neurons()
            sys.exit(0)
        elif sys.argv[1] == '--tui':
            if not supports_tui():
                print("Warning: Terminal does not support modern TUI. Falling back to CLI.")
                hub = CynapseHub()
                hub.cli_loop()
                sys.exit(0)

            # Launch the Textual-based TUI
            try:
                # Redirect stderr to devnull to avoid UI corruption from warnings/noise
                # but keep a reference to original for cleanup
                original_stderr = sys.stderr
                sys.stderr = open(os.devnull, 'w')

                from hub_tui import CynapseApp
                app = CynapseApp()
                app.run()

                sys.stderr = original_stderr
            except ImportError:
                sys.stderr = sys.__stderr__
                print("Error: 'textual' package not found. Modern TUI requires 'pip install textual'.")
                print("Falling back to CLI mode...")
                hub = CynapseHub()
                hub.cli_loop()
            except Exception as e:
                sys.stderr = sys.__stderr__
                print(f"TUI Error: {e}")
                sys.exit(1)
            sys.exit(0)
        elif sys.argv[1] == '--cli':
            hub = CynapseHub()
            hub.cli_loop()
            sys.exit(0)
        elif sys.argv[1] == '--help':
            print("Cynapse Hub - Ghost Shell Security Ecosystem")
            print("\nUsage: python cynapse.py [options] [neuron] [args...]")
            print("\nOptions:")
            print("  --tui     Launch modern reactive TUI (default if supported)")
            print("  --cli     Force legacy interactive CLI mode")
            print("  --test    Run verification tests")
            print("  --list    List all neurons")
            print("  --help    Show this help")
            print("\nRun without arguments to start TUI (if supported) or CLI.")
            sys.exit(0)
        else:
            # Run neuron directly
            hub = CynapseHub()
            neuron_name = sys.argv[1]
            args = sys.argv[2:]
            result = hub.run_neuron(neuron_name, *args)
            if result:
                print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                sys.exit(result.returncode)
            sys.exit(1)
    else:
        if supports_tui():
            # Try to launch TUI by default
            try:
                from hub_tui import CynapseApp
                app = CynapseApp()
                app.run()
            except ImportError:
                hub = CynapseHub()
                hub.cli_loop()
        else:
            hub = CynapseHub()
            hub.cli_loop()


if __name__ == "__main__":
    main()
