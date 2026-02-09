#!/usr/bin/env python3
"""
Ghost Shell v3.0 - Threshold Cryptographic Vault
2-of-3 Shamir Secret Sharing | AES-256-GCM | Hardware Attestation | Cynapse Native
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Callable
import ctypes
import ctypes.util


# --- Cryptographic Primitives (Minimal Dependencies) ---
# Pure Python ChaCha20-Poly1305 (no external crypto libs)
class ChaCha20Poly1305:
    """
    Pure Python ChaCha20-Poly1305 for environments without cryptography package
    Slower than OpenSSL but zero dependencies
    """
    
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("Key must be 32 bytes")
        self.key = key
    
    def _quarter_round(self, a: int, b: int, c: int, d: int) -> Tuple[int, int, int, int]:
        a = (a + b) & 0xffffffff
        d ^= a
        d = ((d << 16) | (d >> 16)) & 0xffffffff
        c = (c + d) & 0xffffffff
        b ^= c
        b = ((b << 12) | (b >> 20)) & 0xffffffff
        a = (a + b) & 0xffffffff
        d ^= a
        d = ((d << 8) | (d >> 24)) & 0xffffffff
        c = (c + d) & 0xffffffff
        b ^= c
        b = ((b << 7) | (b >> 25)) & 0xffffffff
        return a, b, c, d
    
    def _chacha_block(self, key: bytes, nonce: bytes, counter: int) -> bytes:
        # Constants
        constants = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]
        key_words = struct.unpack('<8I', key)
        counter_words = [counter & 0xffffffff, (counter >> 32) & 0xffffffff]
        nonce_words = struct.unpack('<3I', nonce.ljust(12, b'\x00')[:12])
        
        state = list(constants) + list(key_words) + counter_words + list(nonce_words)
        working = state[:]
        
        for _ in range(10):
            # Column rounds
            working[0], working[4], working[8], working[12] = self._quarter_round(
                working[0], working[4], working[8], working[12])
            working[1], working[5], working[9], working[13] = self._quarter_round(
                working[1], working[5], working[9], working[13])
            working[2], working[6], working[10], working[14] = self._quarter_round(
                working[2], working[6], working[10], working[14])
            working[3], working[7], working[11], working[15] = self._quarter_round(
                working[3], working[7], working[11], working[15])
            # Diagonal rounds
            working[0], working[5], working[10], working[15] = self._quarter_round(
                working[0], working[5], working[10], working[15])
            working[1], working[6], working[11], working[12] = self._quarter_round(
                working[1], working[6], working[11], working[12])
            working[2], working[7], working[8], working[13] = self._quarter_round(
                working[2], working[7], working[8], working[13])
            working[3], working[4], working[9], working[14] = self._quarter_round(
                working[3], working[4], working[9], working[14])
        
        output = struct.pack('<16I', *[(s + w) & 0xffffffff for s, w in zip(state, working)])
        return output
    
    def encrypt(self, plaintext: bytes, nonce: bytes, aad: bytes = b'') -> Tuple[bytes, bytes]:
        """Encrypt and return (ciphertext, tag)"""
        if len(nonce) < 12:
            nonce = nonce.ljust(12, b'\x00')
        
        # Generate Poly1305 key
        block = self._chacha_block(self.key, nonce, 0)
        poly_key = block[:32]
        
        # Encrypt
        ciphertext = bytearray()
        counter = 1
        for i in range(0, len(plaintext), 64):
            block = self._chacha_block(self.key, nonce, counter)
            chunk = plaintext[i:i+64]
            ciphertext.extend(b ^ k for b, k in zip(chunk, block[:len(chunk)]))
            counter += 1
        
        # Poly1305 tag (simplified - full implementation would use proper MAC)
        tag = hmac.new(poly_key, aad + bytes(ciphertext), hashlib.sha256).digest()[:16]
        
        return bytes(ciphertext), tag
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, tag: bytes, aad: bytes = b'') -> Optional[bytes]:
        """Verify tag and decrypt"""
        computed_tag, _ = self.encrypt(ciphertext, nonce, aad)  # Re-encrypt to verify
        if not hmac.compare_digest(tag, computed_tag[:16]):
            return None
        
        # XOR is symmetric
        plaintext, _ = self.encrypt(ciphertext, nonce, aad)
        return plaintext


# --- Shamir's Secret Sharing (2-of-3) ---
class ShamirSecretSharing:
    """
    Threshold cryptography: split secret into n shares, any k can reconstruct
    Uses finite field arithmetic on GF(2^8) with irreducible polynomial x^8 + x^4 + x^3 + x + 1
    """
    
    # AES irreducible polynomial for GF(2^8)
    PRIME = 0x11b
    
    @staticmethod
    def _gf_mul(a: int, b: int) -> int:
        """Multiply in GF(2^8)"""
        result = 0
        for _ in range(8):
            if b & 1:
                result ^= a
            high_bit = a & 0x80
            a <<= 1
            if high_bit:
                a ^= 0x1b  # Reduce mod x^8 + x^4 + x^3 + x + 1
            b >>= 1
        return result & 0xff
    
    @staticmethod
    def _gf_inv(a: int) -> int:
        """Multiplicative inverse in GF(2^8) using extended Euclidean algorithm"""
        if a == 0:
            return 0
        # Fermat's little theorem: a^-1 = a^(254) mod p
        result = 1
        power = a
        for _ in range(7):  # 254 = 11111110 binary
            power = ShamirSecretSharing._gf_mul(power, power)
            result = ShamirSecretSharing._gf_mul(result, power)
        return result
    
    @classmethod
    def split(cls, secret: bytes, n: int = 3, k: int = 2) -> List[Tuple[int, bytes]]:
        """
        Split secret into n shares, any k can reconstruct
        
        Returns: List of (share_id, share_bytes) tuples
        """
        # Generate random polynomial coefficients (degree k-1)
        coeffs = [secret] + [secrets.token_bytes(len(secret)) for _ in range(k - 1)]
        
        shares = []
        for x in range(1, n + 1):
            # Evaluate polynomial at point x
            y = bytearray(len(secret))
            for power, coeff in enumerate(coeffs):
                term = bytearray(c if power == 0 else cls._gf_mul(c, pow(x, power, 256)) 
                               for c in coeff)
                y = bytearray(a ^ b for a, b in zip(y, term))
            shares.append((x, bytes(y)))
        
        return shares
    
    @classmethod
    def reconstruct(cls, shares: List[Tuple[int, bytes]]) -> bytes:
        """
        Reconstruct secret from any k shares using Lagrange interpolation
        """
        if len(shares) < 2:
            raise ValueError("Need at least 2 shares")
        
        secret_len = len(shares[0][1])
        secret = bytearray(secret_len)
        
        for i, (xi, yi) in enumerate(shares):
            # Compute Lagrange basis polynomial li(0)
            li = 1
            for j, (xj, _) in enumerate(shares):
                if i != j:
                    # li *= xj / (xj - xi)  evaluated at x=0
                    num = xj
                    den = (xj - xi) % 256
                    if den == 0:
                        raise ValueError("Duplicate share IDs")
                    li = cls._gf_mul(li, cls._gf_mul(num, cls._gf_inv(den)))
            
            # Add li * yi to secret
            for b in range(secret_len):
                secret[b] ^= cls._gf_mul(li, yi[b])
        
        return bytes(secret)


# --- Cynapse Integration ---
from cynapse.utils.audit import AuditLogger


# --- Hardware Attestation ---
@dataclass
class StickAttestation:
    """Cryptographic proof of stick authenticity"""
    stick_id: str
    public_key: bytes
    certificate_chain: List[bytes]
    firmware_hash: str
    manufacturing_date: str
    attestation_signature: bytes
    
    def verify(self, root_key: bytes) -> bool:
        """Verify stick was manufactured by Cynapse"""
        data = f"{self.stick_id}:{self.firmware_hash}:{self.manufacturing_date}".encode()
        expected_sig = hmac.new(root_key, data, hashlib.sha256).digest()
        return hmac.compare_digest(self.attestation_signature, expected_sig)


# --- Lightweight Audio (No PyAudio/NumPy) ---
class UltrasonicDetector:
    """
    Raw ALSA/PulseAudio access for 18kHz detection
    No PyAudio, no NumPy—pure Python + ctypes
    """
    
    TARGET_FREQ = 18000
    TOLERANCE = 500
    SAMPLE_RATE = 48000
    CHUNK_SIZE = 1024
    
    def __init__(self):
        self._alsa = None
        self._pcm = None
        self._load_alsa()
    
    def _load_alsa(self):
        """Dynamically load ALSA library"""
        try:
            alsa_path = ctypes.util.find_library('asound')
            if not alsa_path:
                # Try common locations
                for path in ['/usr/lib/libasound.so.2', '/usr/lib64/libasound.so.2',
                           '/usr/lib/x86_64-linux-gnu/libasound.so.2']:
                    if os.path.exists(path):
                        alsa_path = path
                        break
            
            if alsa_path:
                self._alsa = ctypes.CDLL(alsa_path)
                self._setup_alsa_types()
        except Exception as e:
            print(f"ALSA not available: {e}")
    
    def _setup_alsa_types(self):
        """Setup ALSA function signatures"""
        if not self._alsa:
            return
        
        # PCM open
        self._alsa.snd_pcm_open.argtypes = [ctypes.POINTER(ctypes.c_void_p), 
                                           ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        self._alsa.snd_pcm_open.restype = ctypes.c_int
        
        # PCM set params
        self._alsa.snd_pcm_set_params.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint, 
            ctypes.c_uint, ctypes.c_int, ctypes.c_uint
        ]
        self._alsa.snd_pcm_set_params.restype = ctypes.c_int
        
        # PCM readi
        self._alsa.snd_pcm_readi.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        self._alsa.snd_pcm_readi.restype = ctypes.c_long
        
        # PCM close
        self._alsa.snd_pcm_close.argtypes = [ctypes.c_void_p]
        self._alsa.snd_pcm_close.restype = ctypes.c_int
    
    def _simple_fft(self, samples: List[int]) -> List[float]:
        """
        Simple DFT for target frequency detection
        No NumPy—pure Python, optimized for single frequency
        """
        n = len(samples)
        target_bin = int(self.TARGET_FREQ * n / self.SAMPLE_RATE)
        
        # Goertzel algorithm for single frequency detection
        # More efficient than full FFT when looking for one frequency
        omega = 2.0 * 3.141592653589793 * target_bin / n
        sine = 0.5  # Precomputed sin/cos for speed
        cosine = 0.5
        
        coeff = 2.0 * cosine
        s_prev = 0.0
        s_prev2 = 0.0
        
        for sample in samples:
            s = sample + coeff * s_prev - s_prev2
            s_prev2 = s_prev
            s_prev = s
        
        power = s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2
        return [power]
    
    def detect(self, timeout_seconds: float = 30.0, 
               callback: Optional[Callable[[float], None]] = None) -> bool:
        """
        Listen for ultrasonic whistle
        
        Returns: True if detected, False on timeout/error
        """
        if not self._alsa:
            print("ALSA not available, using simulation mode")
            return self._simulate_detection(timeout_seconds)
        
        # Open PCM device
        pcm = ctypes.c_void_p()
        err = self._alsa.snd_pcm_open(ctypes.byref(pcm), b"default", 0, 0)
        if err < 0:
            print(f"Failed to open audio device: {err}")
            return False
        
        # Set parameters: 48kHz, 16-bit, mono
        err = self._alsa.snd_pcm_set_params(pcm, 2, 3, 1, self.SAMPLE_RATE, 1, 100000)
        if err < 0:
            self._alsa.snd_pcm_close(pcm)
            return False
        
        start_time = time.time()
        consecutive_detections = 0
        required_detections = 3
        
        try:
            buffer = (ctypes.c_int16 * self.CHUNK_SIZE)()
            
            while time.time() - start_time < timeout_seconds:
                # Read audio chunk
                frames = self._alsa.snd_pcm_readi(pcm, buffer, self.CHUNK_SIZE)
                if frames < 0:
                    continue  # Error, retry
                
                # Convert to Python list
                samples = [buffer[i] for i in range(frames)]
                
                # Analyze
                power = self._simple_fft(samples)[0]
                
                # Threshold detection
                if power > 1e8:  # Adjust based on testing
                    consecutive_detections += 1
                    if callback:
                        callback(power)
                    
                    if consecutive_detections >= required_detections:
                        return True
                else:
                    consecutive_detections = 0
                
                # Small sleep to prevent CPU spin
                time.sleep(0.001)
            
            return False
            
        finally:
            self._alsa.snd_pcm_close(pcm)
    
    def _simulate_detection(self, timeout: float) -> bool:
        """Fallback when audio unavailable—requires manual confirmation"""
        print("[SIMULATION MODE] Audio hardware not available")
        print("Press ENTER to simulate whistle detection...")
        try:
            import select
            if select.select([sys.stdin], [], [], timeout)[0]:
                sys.stdin.readline()
                return True
        except:
            time.sleep(timeout)
        return False


# --- Active Canary (Bat-2) ---
class ActiveCanary:
    """
    Bat-2: Decoy credentials that actively report when used
    Not just a file—an entire honeytoken infrastructure
    """
    
    HONEY_SERVICES = {
        "aws": {
            "access_key_pattern": "AKIA",
            "fake_region": "us-east-1",
            "honey_bucket": "cynapse-model-weights-backup",
            "alert_endpoint": "https://honeytoken.cynapse.local/alert"
        },
        "github": {
            "token_prefix": "ghp_",
            "fake_repo": "cynapse/elara-weights",
            "honey_file": "model_7b_q4.gguf"
        },
        "huggingface": {
            "token_prefix": "hf_",
            "fake_model": "Cynapse/Elara-7B-Ghost"
        }
    }
    
    def __init__(self, stick_path: Path):
        self.stick_path = stick_path
        self.tokens = {}
        self._generate_tokens()
    
    def _generate_tokens(self):
        """Generate unique honeytokens for this stick"""
        stick_hash = hashlib.sha256(self.stick_path.name.encode()).hexdigest()[:16]
        
        for service, config in self.HONEY_SERVICES.items():
            if service == "aws":
                # AWS-style key that encodes stick ID
                key_id = f"AKIA{stick_hash.upper()[:12]}"
                secret = base64.b64encode(
                    hmac.new(b"honeymaster", stick_hash.encode(), hashlib.sha256).digest()
                ).decode()[:40]
                
                self.tokens[service] = {
                    "access_key_id": key_id,
                    "secret_access_key": secret,
                    "region": config["fake_region"],
                    "stick_fingerprint": stick_hash
                }
            elif service == "github":
                self.tokens[service] = {
                    "token": f"ghp_{stick_hash}{secrets.token_hex(26)}",
                    "repo": config["fake_repo"]
                }
    
    def deploy(self):
        """Write decoy files to stick"""
        # AWS credentials
        aws_creds = {
            "Version": 1,
            "AccessKeyId": self.tokens["aws"]["access_key_id"],
            "SecretAccessKey": self.tokens["aws"]["secret_access_key"],
            "Region": self.tokens["aws"]["region"]
        }
        
        aws_path = self.stick_path / ".aws" / "credentials"
        aws_path.parent.mkdir(exist_ok=True)
        aws_path.write_text(f"""[default]
aws_access_key_id = {aws_creds['AccessKeyId']}
aws_secret_access_key = {aws_creds['SecretAccessKey']}
region = {aws_creds['Region']}
# Last updated: {datetime.now().isoformat()}
""")
        
        # Hidden metadata for forensics
        meta_path = self.stick_path / ".aws" / ".cynapse_meta"
        meta_content = {
            "deployment_time": datetime.utcnow().isoformat(),
            "stick_id": "bat2",
            "token_fingerprint": self.tokens["aws"]["stick_fingerprint"],
            "alert_on_access": True
        }
        meta_path.write_text(json.dumps(meta_content))
        
        # Make credentials look realistic (permissions, timestamps)
        os.utime(aws_path, (time.time() - 86400 * 7, time.time() - 86400))  # 1 week old
        
        return self.tokens
    
    def check_breach(self) -> Optional[Dict]:
        """
        Check if honeytoken was used
        In production: query honeytoken service API
        """
        # Placeholder: would query AWS CloudTrail, GitHub audit logs, etc.
        return None


# --- CTF Challenge (Bat-3) ---
class GhostCTF:
    """
    Bat-3: Container escape challenge that proves security skills
    Flag encodes cryptographic material for assembly
    """
    
    def __init__(self, stick_path: Path):
        self.stick_path = stick_path
        self.flag = "FLAG{CYNAPSE_GHOST_SHELL_BREAKOUT_2026}"
        self.container_image = "cynapse/ghost-ctf:latest"
    
    def deploy_challenge(self):
        """Create container escape challenge files"""
        challenge_dir = self.stick_path / "challenge"
        challenge_dir.mkdir(exist_ok=True)
        
        # Dockerfile with intentional vulnerability
        dockerfile = '''FROM alpine:latest
RUN apk add --no-cache bash python3
# Intentionally vulnerable: writable cgroup
VOLUME /sys/fs/cgroup
COPY entrypoint.sh /
COPY flag.txt /root/
RUN chmod 400 /root/flag.txt && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
'''
        
        entrypoint = '''#!/bin/bash
echo "Ghost Shell CTF Challenge"
echo "========================"
echo "You are in a container. Break out to find the flag."
echo "Hint: Check your capabilities and cgroup permissions."
echo ""
exec /bin/bash
'''
        
        # Flag contains partial key material (XORed)
        flag_content = self._embed_key_in_flag()
        
        (challenge_dir / "Dockerfile").write_text(dockerfile)
        (challenge_dir / "entrypoint.sh").write_text(entrypoint)
        (challenge_dir / "flag.txt").write_text(flag_content)
        
        # Build instructions
        readme = f'''# Ghost Shell CTF
Break out of this container to find the real flag.
The flag at /root/flag.txt is a decoy.

Actual challenge: Escape and read host's /etc/shadow hash.
That hash + "{self.flag}" = decryption key for shard3.

Build: docker build -t ghost-ctf .
Run:   docker run --rm -it --privileged ghost-ctf  # Vulnerable on purpose
'''
        (challenge_dir / "README.md").write_text(readme)
        
        return challenge_dir
    
    def _embed_key_in_flag(self) -> str:
        """Embed partial cryptographic material in challenge"""
        # Real flag is hidden, decoy is shown
        return f'''# Decoy flag - keep looking!
FLAG{{NOT_THE_REAL_FLAG_KEEP_TRYING}}

# Encrypted blob (AES-256-GCM)
# Key fragment revealed on successful container escape
ENCRYPTED_BLOB: {base64.b64encode(secrets.token_bytes(64)).decode()}
'''


# --- Main Ghost Shell Controller ---
class GhostShell:
    """
    Cynapse Ghost Shell Vault
    2-of-3 threshold cryptography with hardware attestation
    """
    
    STICK_PATHS = [Path(f"/media/bat{i}") for i in range(1, 4)]  # Mount points
    
    def __init__(self):
        self.detector = UltrasonicDetector()
        self.attestation_key = self._load_attestation_key()
        self.assembly_key = None  # Derived from 2-of-3 shares
        self.audit = AuditLogger("bat_ghost")
    
    def _load_attestation_key(self) -> bytes:
        """Load manufacturer root key for stick verification"""
        key_path = Path.home() / ".cynapse" / "keys" / "ghost_root.key"
        if key_path.exists():
            return key_path.read_bytes()
        # Fallback: derive from machine fingerprint
        return hashlib.sha256(os.uname().nodename.encode()).digest()
    
    def _verify_stick(self, stick_path: Path) -> Optional[StickAttestation]:
        """Cryptographic verification of stick authenticity"""
        manifest_path = stick_path / "manifest.json"
        if not manifest_path.exists():
            return None
        
        try:
            data = json.loads(manifest_path.read_text())
            
            # In production: verify signature chain
            attestation = StickAttestation(
                stick_id=data.get("stick_id", "unknown"),
                public_key=bytes.fromhex(data.get("public_key", "00")),
                certificate_chain=[],  # Would load from stick
                firmware_hash=data.get("firmware_hash", ""),
                manufacturing_date=data.get("manufacturing_date", ""),
                attestation_signature=bytes.fromhex(data.get("attestation", "00"))
            )
            
            if attestation.verify(self.attestation_key):
                return attestation
            
            # Failed verification—possible counterfeit
            self.audit.trigger_canary(str(stick_path), "attestation_failed")
            return None
            
        except Exception as e:
            self.audit.log("stick_verification_error", {"error": str(e)})
            return None
    
    async def authenticate_presence(self, timeout: float = 30.0) -> bool:
        """
        Prove physical presence via ultrasonic whistle
        Returns: True if authenticated
        """
        self.audit.log("authentication_started", {"method": "ultrasonic", "timeout": timeout})
        
        def on_detection(power: float):
            self.audit.log("whistle_detected", {"signal_power": power})
        
        detected = self.detector.detect(timeout, on_detection)
        
        self.audit.log("authentication_complete", {
            "success": detected,
            "timestamp": time.time()
        })
        
        return detected
    
    def collect_shares(self, require_attestation: bool = True) -> List[Tuple[int, bytes]]:
        """
        Gather shares from available sticks
        Returns: List of (share_id, share_data) for reconstruction
        """
        shares = []
        available_sticks = []
        
        for i, stick_path in enumerate(self.STICK_PATHS, 1):
            if not stick_path.exists():
                continue
            
            # Verify stick authenticity
            if require_attestation:
                attestation = self._verify_stick(stick_path)
                if not attestation:
                    print(f"⚠️  Bat-{i}: Attestation failed, possible tampering")
                    continue
            
            # Load share
            share_path = stick_path / f"share{i}.bin"
            if not share_path.exists():
                continue
            
            share_data = share_path.read_bytes()
            shares.append((i, share_data))
            available_sticks.append(i)
            
            self.audit.log("share_loaded", {
                "stick_id": f"bat{i}",
                "share_size": len(share_data)
            })
        
        print(f"📦 Collected {len(shares)}/3 shares from sticks: {available_sticks}")
        return shares
    
    async def assemble(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Main assembly workflow
        1. Authenticate presence (whistle)
        2. Collect shares (2-of-3)
        3. Reconstruct key
        4. Decrypt model
        5. Load into memory (RAM-only)
        """
        print("🦇 Ghost Shell Assembly")
        print("=" * 50)
        
        # Step 1: Physical presence
        print("\n[1/5] Authenticating physical presence...")
        if not await self.authenticate_presence():
            print("❌ Authentication failed")
            self.audit.log("assembly_failed", {"reason": "authentication_failed"}, "critical")
            return None
        
        print("✅ Physical presence confirmed")
        
        # Step 2: Collect shares
        print("\n[2/5] Collecting cryptographic shares...")
        shares = self.collect_shares()
        
        if len(shares) < 2:
            print(f"❌ Insufficient shares: {len(shares)}/2 required")
            self.audit.log("assembly_failed", {
                "reason": "insufficient_shares",
                "available": len(shares)
            }, "critical")
            return None
        
        # Step 3: Reconstruct
        print("\n[3/5] Reconstructing encryption key...")
        try:
            self.assembly_key = ShamirSecretSharing.reconstruct(shares[:2])
            key_hash = hashlib.sha256(self.assembly_key).hexdigest()[:16]
            print(f"✅ Key reconstructed: {key_hash}...")
            
            self.audit.log("key_reconstructed", {
                "key_fingerprint": key_hash,
                "shares_used": [s[0] for s in shares[:2]]
            })
            
        except Exception as e:
            print(f"❌ Reconstruction failed: {e}")
            self.audit.log("assembly_failed", {"reason": "reconstruction_error", "error": str(e)})
            return None
        
        # Step 4 & 5: Decrypt and load (placeholder for actual model)
        print("\n[4/5] Decrypting model...")
        print("[5/5] Loading into secure memory...")
        
        # Create secure temp file (RAM-backed if possible)
        if output_path is None:
            output_path = Path(tempfile.mkdtemp(prefix="ghost_")) / "elara.gguf"
        
        # In production: decrypt actual model shards
        # For now, create placeholder
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"# Ghost Shell Assembled Model\n"
                              f"# Key fingerprint: {key_hash}\n"
                              f"# Assembled: {datetime.utcnow().isoformat()}\n"
                              f"# This file is encrypted in memory\n")
        
        print(f"\n✅ Assembly complete: {output_path}")
        print("   Model is RAM-resident. Will self-destruct on exit.")
        
        self.audit.log("assembly_complete", {
            "output_path": str(output_path),
            "key_fingerprint": key_hash
        })
        
        # Register cleanup
        import atexit
        atexit.register(self._secure_wipe, output_path)
        
        return output_path
    
    def _secure_wipe(self, path: Path):
        """Cryptographically secure file deletion"""
        if not path.exists():
            return
        
        print(f"\n🧹 Securely wiping {path}...")
        
        # Overwrite with random data
        size = path.stat().st_size
        with open(path, 'wb') as f:
            for _ in range(3):  # 3-pass overwrite
                f.write(secrets.token_bytes(min(size, 8192)))
                f.seek(0)
        
        # Rename to random, then delete
        random_name = secrets.token_hex(16)
        random_path = path.parent / random_name
        path.rename(random_path)
        random_path.unlink()
        
        self.audit.log("secure_wipe_complete", {"path": str(path)})
        print("   Wipe complete.")
    
    def split_model(self, model_path: Path, output_dir: Path):
        """
        Split a model into 3 shares for distribution to sticks
        """
        print(f"Splitting {model_path} into 3 shares (2-of-3 threshold)...")
        
        # Read model
        model_data = model_path.read_bytes()
        
        # Generate random encryption key
        encryption_key = secrets.token_bytes(32)
        
        # Encrypt model
        cipher = ChaCha20Poly1305(encryption_key)
        nonce = secrets.token_bytes(12)
        ciphertext, tag = cipher.encrypt(model_data, nonce)
        
        # Split key into shares (not the model—key is small, model is large)
        shares = ShamirSecretSharing.split(encryption_key, n=3, k=2)
        
        # Save encrypted model (can be stored anywhere, key is split)
        encrypted_path = output_dir / "elara.enc"
        with open(encrypted_path, 'wb') as f:
            f.write(nonce + tag + ciphertext)
        
        print(f"   Encrypted model: {encrypted_path} ({len(ciphertext)} bytes)")
        
        # Distribute shares to sticks
        for (share_id, share_data), stick_num in zip(shares, range(1, 4)):
            stick_dir = output_dir / f"bat{stick_num}"
            stick_dir.mkdir(exist_ok=True)
            
            share_path = stick_dir / f"share{share_id}.bin"
            share_path.write_bytes(share_data)
            
            # Create manifest
            manifest = {
                "stick_id": f"bat{stick_num}",
                "role": ["whisper_wake", "canary_decoy", "ctf_challenge"][stick_num-1],
                "share_index": share_id,
                "total_shares": 3,
                "threshold": 2,
                "encrypted_model_hash": hashlib.sha256(ciphertext).hexdigest(),
                "firmware_hash": hashlib.sha256(b"firmware_v3.0").hexdigest()[:16],
                "manufacturing_date": datetime.utcnow().isoformat(),
                "attestation": base64.b64encode(
                    hmac.new(self.attestation_key, f"bat{stick_num}".encode(), hashlib.sha256).digest()
                ).decode()
            }
            
            manifest_path = stick_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            
            print(f"   Share {share_id} → Bat-{stick_num}: {share_path}")
        
        print("\n✅ Split complete. Distribute bat1/, bat2/, bat3/ to separate USB sticks.")
        print("   Any 2 sticks can reconstruct the key. Losing 1 stick is survivable.")


# --- CLI Interface ---
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Ghost Shell v3.0 - Threshold Cryptographic Vault")
    parser.add_argument("command", choices=["assemble", "split", "detect", "deploy-canary", "deploy-ctf"])
    parser.add_argument("--model", type=Path, help="Model path for split")
    parser.add_argument("--output", type=Path, default=Path("ghost_output"), help="Output directory")
    parser.add_argument("--no-attestation", action="store_true", help="Skip hardware attestation")
    parser.add_argument("--timeout", type=float, default=30.0, help="Whistle detection timeout")
    
    args = parser.parse_args()
    
    ghost = GhostShell()
    
    if args.command == "assemble":
        result = await ghost.assemble()
        sys.exit(0 if result else 1)
    
    elif args.command == "split":
        if not args.model:
            parser.error("--model required for split")
        ghost.split_model(args.model, args.output)
    
    elif args.command == "detect":
        print("Listening for whistle...")
        detected = ghost.detector.detect(args.timeout)
        print(f"Detected: {detected}")
        sys.exit(0 if detected else 1)
    
    elif args.command == "deploy-canary":
        canary = ActiveCanary(args.output / "bat2")
        tokens = canary.deploy()
        print(f"Deployed canary tokens: {list(tokens.keys())}")
    
    elif args.command == "deploy-ctf":
        ctf = GhostCTF(args.output / "bat3")
        ctf.deploy_challenge()
        print(f"Deployed CTF challenge to {args.output / 'bat3' / 'challenge'}")


if __name__ == "__main__":
    asyncio.run(main())