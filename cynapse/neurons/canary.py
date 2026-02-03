#!/usr/bin/env python3
"""
Canary Neuron v3.0 - Distributed Deception System
Cynapse Security Integration | Behavioral Fingerprinting | Active Countermeasures
"""

import asyncio
import hashlib
import json
import os
import platform
import random
import socket
import string
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any
import ctypes
import ctypes.wintypes
import select


# Cynapse integration stubs (will bind to actual Hub at runtime)
class CynapseBridge:
    """Interface to Cynapse Hub for coordinated response"""
    
    @staticmethod
    async def alert(event: Dict) -> None:
        """Broadcast alert to all security neurons"""
        # Hook into Cynapse audit system
        pass
    
    @staticmethod
    async def trigger_lockdown(source: str) -> None:
        """Escalate to Wolverine/Beaver for active defense"""
        pass
    
    @staticmethod
    def log_audit(event_type: str, data: Dict) -> None:
        """NDJSON audit trail"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "neuron": "canary",
            "event": event_type,
            "data": data
        }
        audit_path = Path.home() / ".cynapse" / "logs" / "canary_audit.ndjson"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


@dataclass
class DecoyConfig:
    """Configuration for a single decoy deployment"""
    filename: str
    content_generator: Callable[[], bytes]
    mime_type: str
    access_trap: bool = True  # Trigger on open/read
    modify_trap: bool = True  # Trigger on write/delete
    honeytoken: Optional[str] = None  # Exfiltration tracker


@dataclass
class IntrusionEvent:
    """Structured alert data"""
    event_id: str
    timestamp: float
    decoy_path: str
    decoy_type: str
    action: str  # READ, WRITE, DELETE, RENAME
    process_name: str
    process_exe: str
    process_cmdline: str
    pid: int
    uid: int
    username: str
    hostname: str
    cwd: str
    network_connections: List[Dict]
    hash_chain: str  # Integrity verification


class StealthDecoyGenerator:
    """Generate convincing bait that withstands inspection"""
    
    # AWS credential patterns that look real but are invalid
    AWS_KEY_ID_PREFIXES = ["AKIA", "ASIA", "AROA", "AIDA"]
    AWS_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
    
    # Realistic model architectures
    MODEL_ARCHITECTURES = [
        ("transformer_encoder", [768, 12, 12]),  # hidden, layers, heads
        ("llama_7b", [4096, 32, 32]),
        ("clip_vit_l", [1024, 24, 16]),
        ("diffusion_unet", [320, 4, 8]),
    ]
    
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed or int(time.time()))
    
    def generate_aws_credentials(self) -> bytes:
        """Generate fake AWS creds with valid format but invalid checksum"""
        key_id = self.rng.choice(self.AWS_KEY_ID_PREFIXES)
        key_id += ''.join(self.rng.choices(string.ascii_uppercase + string.digits, k=16))
        
        # Secret key looks real but fails AWS validation
        secret = ''.join(self.rng.choices(string.ascii_letters + string.digits + '+/', k=40))
        
        creds = {
            "Version": 1,
            "AccessKeyId": key_id,
            "SecretAccessKey": secret,
            "SessionToken": None,
            "Region": self.rng.choice(self.AWS_REGIONS),
            "Expiration": (datetime.utcnow().isoformat() + "Z"),
            "_meta": {
                "source": "env",
                "loaded_at": int(time.time())
            }
        }
        return json.dumps(creds, indent=2).encode()
    
    def generate_onnx_model(self, size_mb: int = 10) -> bytes:
        """Generate fake model weights with valid ONNX header + unique fingerprint"""
        # ONNX protobuf header (magic + version + length)
        header = b"\x08\x08"  # ONNX magic
        header += b"\x00\x00\x00\x00"  # IR version
        header += b"\x00\x00\x00\x00"  # Opset version
        
        # Unique fingerprint embedded in padding (for tracking exfiltration)
        fingerprint = uuid.uuid4().bytes
        
        # Random "weights" that compress poorly (looks like real data)
        payload = bytes(self.rng.randint(0, 255) for _ in range(size_mb * 1024 * 1024 - len(header) - 16))
        
        return header + fingerprint + payload
    
    def generate_chrome_cookies(self) -> bytes:
        """Generate fake Chrome cookie database entries"""
        domains = [
            "github.com", "huggingface.co", "wandb.ai", 
            "aws.amazon.com", "console.cloud.google.com"
        ]
        
        cookies = []
        for domain in self.rng.sample(domains, k=self.rng.randint(2, 4)):
            cookies.append({
                "domain": f".{domain}",
                "expirationDate": time.time() + 86400 * 30,
                "hostOnly": False,
                "httpOnly": True,
                "name": f"session_{self.rng.randint(1000, 9999)}",
                "path": "/",
                "sameSite": "lax",
                "secure": True,
                "value": hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]
            })
        
        return json.dumps(cookies, indent=2).encode()
    
    def generate_ssh_key(self) -> bytes:
        """Generate fake SSH private key"""
        key_types = ["OPENSSH PRIVATE KEY", "RSA PRIVATE KEY", "EC PRIVATE KEY"]
        key_type = self.rng.choice(key_types)
        
        # Looks like base64 but is random
        fake_key = ''.join(self.rng.choices(string.ascii_letters + string.digits + '+/=', k=2100))
        lines = [fake_key[i:i+70] for i in range(0, len(fake_key), 70)]
        
        content = f"-----BEGIN {key_type}-----\n"
        content += '\n'.join(lines)
        content += f"\n-----END {key_type}-----\n"
        
        return content.encode()
    
    def generate_env_file(self) -> bytes:
        """Generate fake .env with juicy-looking secrets"""
        vars = [
            ("OPENAI_API_KEY", f"sk-{''.join(self.rng.choices(string.ascii_letters + string.digits, k=48))}"),
            ("HF_TOKEN", f"hf_{''.join(self.rng.choices(string.ascii_letters + string.digits, k=40))}"),
            ("WANDB_API_KEY", f"{''.join(self.rng.choices(string.hexdigits, k=40))}"),
            ("AWS_DEFAULT_REGION", self.rng.choice(self.AWS_REGIONS)),
            ("DATABASE_URL", f"postgresql://admin:{''.join(self.rng.choices(string.ascii_letters, k=16))}@prod.db.internal:5432/elara"),
            ("ELARA_MODEL_KEY", hashlib.sha256(str(time.time()).encode()).hexdigest()),
        ]
        
        lines = [f"{k}={v}" for k, v in vars]
        lines.append(f"# Generated: {datetime.utcnow().isoformat()}")
        return '\n'.join(lines).encode()


class DistributedWatcher:
    """
    Cross-platform filesystem watcher using native APIs
    Monitors multiple decoy locations simultaneously
    """
    
    def __init__(self, callback: Callable[[str, str, Any], None]):
        self.callback = callback
        self.watch_descriptors: Dict[str, Any] = {}  # path -> handle/fd
        self.running = False
        self._platform = platform.system()
    
    def _get_process_info(self, pid: int) -> Dict:
        """Extract detailed process information"""
        try:
            if self._platform == "Windows":
                return self._get_process_info_win(pid)
            else:
                return self._get_process_info_posix(pid)
        except Exception as e:
            return {"error": str(e), "pid": pid}
    
    def _get_process_info_win(self, pid: int) -> Dict:
        """Windows process enumeration via ctypes"""
        # Simplified - full implementation would use psutil or native APIs
        return {
            "pid": pid,
            "name": "unknown",
            "exe": "unknown",
            "cmdline": "",
            "cwd": "",
            "connections": []
        }
    
    def _get_process_info_posix(self, pid: int) -> Dict:
        """Linux/Mac process info via /proc"""
        try:
            proc_path = Path(f"/proc/{pid}")
            
            # Read cmdline
            cmdline = (proc_path / "cmdline").read_text().replace('\x00', ' ')
            
            # Read exe symlink
            exe = os.readlink(proc_path / "exe")
            
            # Read cwd
            cwd = os.readlink(proc_path / "cwd")
            
            # Parse status for name
            status = (proc_path / "status").read_text()
            name = [l for l in status.split('\n') if l.startswith('Name:')][0].split()[1]
            
            # Network connections (basic)
            connections = []
            try:
                net_tcp = (proc_path / "net" / "tcp").read_text().split('\n')[1:-1]
                for line in net_tcp:
                    parts = line.split()
                    if len(parts) > 4:
                        connections.append({
                            "local": parts[1],
                            "remote": parts[2],
                            "state": parts[3]
                        })
            except:
                pass
            
            return {
                "pid": pid,
                "name": name,
                "exe": exe,
                "cmdline": cmdline,
                "cwd": cwd,
                "connections": connections[:5]  # Limit to first 5
            }
        except Exception as e:
            return {"error": str(e), "pid": pid}
    
    async def add_watch(self, path: Path) -> bool:
        """Add a new path to watch list"""
        path_str = str(path.resolve())
        
        if self._platform == "Windows":
            return await self._add_watch_win(path_str)
        else:
            return await self._add_watch_posix(path_str)
    
    async def _add_watch_win(self, path_str: str) -> bool:
        """Windows: ReadDirectoryChangesW"""
        FILE_LIST_DIRECTORY = 0x0001
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        
        handle = ctypes.windll.kernel32.CreateFileW(
            path_str,
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None
        )
        
        if handle == -1:
            return False
        
        self.watch_descriptors[path_str] = {
            "handle": handle,
            "type": "windows"
        }
        return True
    
    async def _add_watch_posix(self, path_str: str) -> bool:
        """Linux/Mac: inotify"""
        try:
            libc = ctypes.CDLL("libc.so.6")
        except:
            try:
                libc = ctypes.CDLL(None)
            except:
                return False
        
        inotify_init = libc.inotify_init
        inotify_init.restype = ctypes.c_int
        inotify_add_watch = libc.inotify_add_watch
        inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        
        IN_ACCESS = 0x00000001
        IN_MODIFY = 0x00000002
        IN_ATTRIB = 0x00000004
        IN_CLOSE_WRITE = 0x00000008
        IN_CLOSE_NOWRITE = 0x00000010
        IN_OPEN = 0x00000020
        IN_MOVED_FROM = 0x00000040
        IN_MOVED_TO = 0x00000080
        IN_CREATE = 0x00000100
        IN_DELETE = 0x00000200
        
        fd = inotify_init()
        if fd < 0:
            return False
        
        wd = inotify_add_watch(
            fd, 
            path_str.encode(), 
            IN_ACCESS | IN_MODIFY | IN_OPEN | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_DELETE
        )
        
        if wd < 0:
            os.close(fd)
            return False
        
        self.watch_descriptors[path_str] = {
            "fd": fd,
            "wd": wd,
            "type": "inotify"
        }
        return True
    
    async def run(self):
        """Main event loop"""
        self.running = True
        
        if self._platform == "Windows":
            await self._run_win()
        else:
            await self._run_posix()
    
    async def _run_win(self):
        """Windows event loop"""
        while self.running:
            for path_str, desc in list(self.watch_descriptors.items()):
                handle = desc["handle"]
                
                # Non-blocking check with 100ms timeout
                result = ctypes.windll.kernel32.WaitForSingleObject(handle, 100)
                
                if result == 0:  # WAIT_OBJECT_0 - event occurred
                    buf = ctypes.create_string_buffer(4096)
                    bytes_returned = ctypes.wintypes.DWORD()
                    
                    success = ctypes.windll.kernel32.ReadDirectoryChangesW(
                        handle,
                        buf,
                        len(buf),
                        True,  # Watch subtree
                        0x000001FF,  # All meaningful events
                        ctypes.byref(bytes_returned),
                        None,
                        None
                    )
                    
                    if success and bytes_returned.value > 0:
                        # Parse FILE_NOTIFY_INFORMATION
                        self._parse_win_notify(buf.raw[:bytes_returned.value], path_str)
            
            await asyncio.sleep(0.05)  # 50ms cooperative yield
    
    def _parse_win_notify(self, data: bytes, watch_path: str):
        """Parse Windows notify structure"""
        offset = 0
        while offset < len(data):
            next_entry = int.from_bytes(data[offset:offset+4], 'little')
            action = int.from_bytes(data[offset+4:offset+8], 'little')
            name_len = int.from_bytes(data[offset+8:offset+12], 'little')
            
            if name_len > 0:
                filename = data[offset+12:offset+12+name_len].decode('utf-16-le')
                
                action_map = {
                    1: "ADDED",
                    2: "REMOVED", 
                    3: "MODIFIED",
                    4: "RENAMED_OLD",
                    5: "RENAMED_NEW"
                }
                
                action_str = action_map.get(action, f"UNKNOWN({action})")
                
                # Get current process info (Windows-specific)
                pid = ctypes.windll.kernel32.GetCurrentProcessId()  # Placeholder
                proc_info = self._get_process_info(pid)
                
                self.callback(watch_path, filename, {
                    "action": action_str,
                    "process": proc_info,
                    "timestamp": time.time()
                })
            
            if next_entry == 0:
                break
            offset += next_entry
    
    async def _run_posix(self):
        """Linux/Mac event loop using asyncio"""
        poll = select.poll()
        fd_to_path = {}
        
        for path_str, desc in self.watch_descriptors.items():
            poll.register(desc["fd"], select.POLLIN)
            fd_to_path[desc["fd"]] = path_str
        
        while self.running:
            # 100ms timeout for responsiveness
            events = poll.poll(100)
            
            for fd, mask in events:
                if mask & select.POLLIN:
                    path_str = fd_to_path[fd]
                    desc = self.watch_descriptors[path_str]
                    
                    # Read inotify event
                    try:
                        data = os.read(fd, 4096)
                        self._parse_inotify(data, path_str)
                    except Exception as e:
                        print(f"Read error: {e}")
            
            await asyncio.sleep(0.05)
    
    def _parse_inotify(self, data: bytes, watch_path: str):
        """Parse inotify_event structures"""
        offset = 0
        while offset < len(data):
            wd = int.from_bytes(data[offset:offset+4], 'little')
            mask = int.from_bytes(data[offset+4:offset+8], 'little')
            cookie = int.from_bytes(data[offset+8:offset+12], 'little')
            name_len = int.from_bytes(data[offset+12:offset+16], 'little')
            
            name = ""
            if name_len > 0:
                name_end = offset + 16 + name_len
                name = data[offset+16:name_end].split(b'\x00')[0].decode('utf-8', errors='ignore')
            
            # Decode mask
            actions = []
            if mask & 0x00000001: actions.append("ACCESS")
            if mask & 0x00000002: actions.append("MODIFY")
            if mask & 0x00000004: actions.append("ATTRIB")
            if mask & 0x00000008: actions.append("CLOSE_WRITE")
            if mask & 0x00000010: actions.append("CLOSE_NOWRITE")
            if mask & 0x00000020: actions.append("OPEN")
            if mask & 0x00000040: actions.append("MOVED_FROM")
            if mask & 0x00000080: actions.append("MOVED_TO")
            if mask & 0x00000100: actions.append("CREATE")
            if mask & 0x00000200: actions.append("DELETE")
            
            if actions and name:
                # Try to find which process accessed it (best effort on Linux)
                proc_info = self._find_accessor_process(watch_path, name)
                
                self.callback(watch_path, name, {
                    "actions": actions,
                    "process": proc_info,
                    "timestamp": time.time()
                })
            
            offset += 16 + name_len
            if offset % 8 != 0:
                offset += 8 - (offset % 8)  # Align to 8 bytes
    
    def _find_accessor_process(self, watch_path: str, filename: str) -> Dict:
        """Attempt to find which process accessed the file"""
        full_path = Path(watch_path) / filename
        
        try:
            # Check /proc for processes with open file descriptors
            for pid_dir in Path("/proc").glob("[0-9]*"):
                try:
                    pid = int(pid_dir.name)
                    fd_dir = pid_dir / "fd"
                    
                    for fd in fd_dir.glob("*"):
                        try:
                            if os.readlink(fd) == str(full_path):
                                return self._get_process_info_posix(pid)
                        except:
                            continue
                except:
                    continue
        except:
            pass
        
        return {"pid": -1, "name": "unknown", "method": "untraced"}
    
    def stop(self):
        """Cleanup and stop"""
        self.running = False
        
        for desc in self.watch_descriptors.values():
            if desc["type"] == "windows":
                ctypes.windll.kernel32.CloseHandle(desc["handle"])
            else:
                os.close(desc["fd"])


class CanaryNeuron:
    """
    Main Canary controller - distributed deception and intrusion detection
    """
    
    # Stealth deployment locations (blend with normal dev environment)
    DECOY_LOCATIONS = [
        ("~/.aws", "credentials"),
        ("~/.ssh", "id_rsa_backup"),
        ("~/projects/elara/models", "checkpoint_final.onnx"),
        ("~/projects/elara", ".env.production"),
        ("~/.cache/huggingface", "token"),
        ("~/Downloads", "model_weights_fp16.onnx"),
        ("~/workspace", "cookies_backup.json"),
    ]
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".cynapse" / "canary_config.json"
        self.decoys: Dict[str, DecoyConfig] = {}
        self.deployed_paths: Set[Path] = set()
        self.watcher = DistributedWatcher(self._on_intrusion)
        self.event_history: List[IntrusionEvent] = []
        self.generator = StealthDecoyGenerator(seed=int(time.time()))
        
        # Alert hooks
        self.webhook_url: Optional[str] = None
        self.email_config: Optional[Dict] = None
        self.cynapse_bridge = CynapseBridge()
        
        self._load_config()
    
    def _load_config(self):
        """Load or create configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                config = json.load(f)
                self.webhook_url = config.get("webhook_url")
                self.email_config = config.get("email")
        else:
            self._save_config()
    
    def _save_config(self):
        """Persist configuration"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump({
                "webhook_url": self.webhook_url,
                "email": self.email_config,
                "deployed": [str(p) for p in self.deployed_paths]
            }, f, indent=2)
    
    def _generate_decoy_config(self, location_type: str) -> DecoyConfig:
        """Select appropriate decoy for location"""
        configs = {
            "credentials": DecoyConfig(
                filename="credentials",
                content_generator=self.generator.generate_aws_credentials,
                mime_type="application/json",
                honeytoken=f"aws-{uuid.uuid4().hex[:8]}"
            ),
            "id_rsa_backup": DecoyConfig(
                filename="id_rsa_backup",
                content_generator=self.generator.generate_ssh_key,
                mime_type="text/plain",
                honeytoken=f"ssh-{uuid.uuid4().hex[:8]}"
            ),
            "checkpoint_final.onnx": DecoyConfig(
                filename="checkpoint_final.onnx",
                content_generator=lambda: self.generator.generate_onnx_model(50),
                mime_type="application/octet-stream",
                honeytoken=f"model-{uuid.uuid4().hex[:8]}"
            ),
            ".env.production": DecoyConfig(
                filename=".env.production",
                content_generator=self.generator.generate_env_file,
                mime_type="text/plain",
                honeytoken=f"env-{uuid.uuid4().hex[:8]}"
            ),
            "token": DecoyConfig(
                filename="token",
                content_generator=self.generator.generate_chrome_cookies,
                mime_type="application/json",
                honeytoken=f"hf-{uuid.uuid4().hex[:8]}"
            ),
            "model_weights_fp16.onnx": DecoyConfig(
                filename="model_weights_fp16.onnx",
                content_generator=lambda: self.generator.generate_onnx_model(100),
                mime_type="application/octet-stream",
                honeytoken=f"model-{uuid.uuid4().hex[:8]}"
            ),
            "cookies_backup.json": DecoyConfig(
                filename="cookies_backup.json",
                content_generator=self.generator.generate_chrome_cookies,
                mime_type="application/json",
                honeytoken=f"cookie-{uuid.uuid4().hex[:8]}"
            ),
        }
        return configs.get(location_type, configs["credentials"])
    
    async def deploy(self, selective: bool = False):
        """
        Plant decoys across filesystem
        selective=True only deploys to existing directories (stealthier)
        """
        print("[*] Deploying canary decoys...")
        
        for dir_template, file_type in self.DECOY_LOCATIONS:
            dir_path = Path(dir_template).expanduser()
            
            if selective and not dir_path.exists():
                continue
            
            # Create directory if needed (but only if not selective)
            if not selective:
                dir_path.mkdir(parents=True, exist_ok=True)
            
            if not dir_path.exists():
                continue
            
            config = self._generate_decoy_config(file_type)
            decoy_path = dir_path / config.filename
            
            # Skip if already deployed
            if decoy_path in self.deployed_paths:
                continue
            
            # Write decoy
            content = config.content_generator()
            decoy_path.write_bytes(content)
            
            # Set realistic timestamps (backdated slightly)
            past_time = time.time() - random.randint(86400 * 7, 86400 * 30)  # 1-4 weeks ago
            os.utime(decoy_path, (past_time, past_time))
            
            # Set permissions (AWS creds should be 600, model files 644)
            if "credentials" in config.filename or "id_rsa" in config.filename:
                os.chmod(decoy_path, 0o600)
            else:
                os.chmod(decoy_path, 0o644)
            
            self.deployed_paths.add(decoy_path)
            self.decoys[str(decoy_path)] = config
            
            # Add to watcher
            await self.watcher.add_watch(dir_path)
            
            print(f"  [+] Planted: {decoy_path} ({len(content)} bytes, token: {config.honeytoken})")
        
        self._save_config()
        print(f"[*] Deployed {len(self.deployed_paths)} decoys across filesystem")
    
    async def _on_intrusion(self, watch_path: str, filename: str, details: Dict):
        """Handle detected file access"""
        full_path = Path(watch_path) / filename
        path_str = str(full_path)
        
        # Check if this is one of our decoys
        decoy_config = None
        for deployed_path in self.deployed_paths:
            if deployed_path.name == filename and str(deployed_path.parent) == watch_path:
                decoy_config = self.decoys.get(str(deployed_path))
                break
        
        if not decoy_config:
            return  # Not our decoy, ignore
        
        # Build intrusion event
        process = details.get("process", {})
        actions = details.get("actions", [details.get("action", "UNKNOWN")])
        
        event = IntrusionEvent(
            event_id=uuid.uuid4().hex,
            timestamp=details["timestamp"],
            decoy_path=path_str,
            decoy_type=decoy_config.filename,
            action="/".join(actions) if isinstance(actions, list) else actions,
            process_name=process.get("name", "unknown"),
            process_exe=process.get("exe", "unknown"),
            process_cmdline=process.get("cmdline", ""),
            pid=process.get("pid", -1),
            uid=process.get("uid", -1) if "uid" in process else -1,
            username=process.get("username", "unknown"),
            hostname=socket.gethostname(),
            cwd=process.get("cwd", ""),
            network_connections=process.get("connections", []),
            hash_chain=hashlib.sha256(f"{path_str}{details['timestamp']}".encode()).hexdigest()[:16]
        )
        
        self.event_history.append(event)
        
        # Immediate response
        await self._trigger_alert(event)
    
    async def _trigger_alert(self, event: IntrusionEvent):
        """Multi-channel alerting"""
        event_dict = asdict(event)
        
        # 1. Local audit log (NDJSON)
        CynapseBridge.log_audit("intrusion_detected", event_dict)
        
        # 2. Console output (rich formatting)
        print("\n" + "="*60)
        print(f"🚨 CANARY TRIPPED: {event.decoy_type}")
        print("="*60)
        print(f"  Time:     {datetime.fromtimestamp(event.timestamp).isoformat()}")
        print(f"  Decoy:    {event.decoy_path}")
        print(f"  Action:   {event.action}")
        print(f"  Process:  {event.process_name} (PID: {event.pid})")
        print(f"  Command:  {event.process_cmdline[:80]}...")
        print(f"  CWD:      {event.cwd}")
        print(f"  Network:  {len(event.network_connections)} active connections")
        print("="*60)
        
        # 3. Voice alert (if TTS available)
        try:
            msg = f"Canary tripped. {event.action} on {event.decoy_type} by {event.process_name}"
            subprocess.run(
                [sys.executable, "-c", f"import pyttsx3; e=pyttsx3.init(); e.say('{msg}'); e.runAndWait()"],
                capture_output=True,
                timeout=5
            )
        except:
            pass  # TTS optional
        
        # 4. Webhook alert
        if self.webhook_url:
            await self._send_webhook(event_dict)
        
        # 5. Cynapse Hub integration - escalate to other neurons
        await CynapseBridge.alert({
            "type": "canary_triggered",
            "severity": "critical",
            "source": "canary_neuron",
            "event": event_dict
        })
        
        # If critical decoy (model weights), trigger lockdown review
        if "onnx" in event.decoy_type or "checkpoint" in event.decoy_type:
            await CynapseBridge.trigger_lockdown(f"canary:{event.event_id}")
    
    async def _send_webhook(self, event: Dict):
        """Async webhook delivery"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=event,
                    headers={"X-Canary-Auth": hashlib.sha256(b"secret").hexdigest()},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        print(f"[-] Webhook failed: {resp.status}")
        except Exception as e:
            print(f"[-] Webhook error: {e}")
    
    async def monitor(self):
        """Start monitoring loop"""
        if not self.deployed_paths:
            print("[-] No decoys deployed. Run deploy() first.")
            return
        
        print(f"[*] Monitoring {len(self.deployed_paths)} decoys...")
        print("[*] Press Ctrl+C to stop")
        
        try:
            await self.watcher.run()
        except KeyboardInterrupt:
            print("\n[+] Stopping canary monitor...")
            self.watcher.stop()
    
    def status(self) -> Dict:
        """Return current status"""
        return {
            "decoys_deployed": len(self.deployed_paths),
            "locations": [str(p) for p in self.deployed_paths],
            "events_recorded": len(self.event_history),
            "monitoring_active": self.watcher.running
        }


# CLI Interface
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Canary Neuron v3.0 - Distributed Deception")
    parser.add_argument("command", choices=["deploy", "monitor", "status", "test-alert"])
    parser.add_argument("--selective", action="store_true", help="Only deploy to existing dirs")
    parser.add_argument("--webhook", help="Webhook URL for alerts")
    
    args = parser.parse_args()
    
    canary = CanaryNeuron()
    
    if args.webhook:
        canary.webhook_url = args.webhook
        canary._save_config()
    
    if args.command == "deploy":
        await canary.deploy(selective=args.selective)
    
    elif args.command == "monitor":
        await canary.monitor()
    
    elif args.command == "status":
        import pprint
        pprint.pprint(canary.status())
    
    elif args.command == "test-alert":
        # Simulate an intrusion event
        test_event = IntrusionEvent(
            event_id="test-001",
            timestamp=time.time(),
            decoy_path="/test/decoy.onnx",
            decoy_type="test",
            action="READ",
            process_name="test-process",
            process_exe="/usr/bin/test",
            process_cmdline="test --intrusion",
            pid=1234,
            uid=1000,
            username="tester",
            hostname="test-host",
            cwd="/tmp",
            network_connections=[],
            hash_chain="test-hash"
        )
        await canary._trigger_alert(test_event)


if __name__ == "__main__":
    asyncio.run(main())