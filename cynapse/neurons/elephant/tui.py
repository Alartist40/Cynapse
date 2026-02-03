#!/usr/bin/env python3
"""
Elephant Sign v2.0 - Python TUI Integration
Thin wrapper around Rust core, async, TUI-native output
"""

import asyncio
from pathlib import Path
from typing import Optional, Callable, Tuple
import struct

# Try to import Rust extension, fall back to pure Python
try:
    import elephant_core as _core
    HAS_RUST = True
except ImportError:
    HAS_RUST = False
    # Pure Python fallback using cryptography
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey
        )
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        HAS_CRYPTO = True
    except ImportError:
        HAS_CRYPTO = False


class ElephantSigner:
    """
    Cryptographic signing for Cynapse Zone 3 (Activation).
    Verifies model integrity before HiveMind loading.
    """
    
    # TUI colors
    COLORS = {
        'valid': '\033[38;5;118m',    # Green
        'invalid': '\033[38;5;196m',  # Red
        'info': '\033[38;5;141m',     # Purple
        'dim': '\033[38;5;245m',      # Gray
        'reset': '\033[0m',
    }
    
    SYMBOLS = {
        'valid': '✓',
        'invalid': '✗',
        'signing': '🔏',
        'verify': '🔍',
    }
    
    def __init__(self, key_dir: Path = None):
        self.key_dir = key_dir or Path.home() / ".cynapse" / "keys"
        self.key_dir.mkdir(parents=True, exist_ok=True)
        
        self._private_key: Optional[bytes] = None
        self._public_key: Optional[bytes] = None
        
        # Load or generate keys
        self._load_keys()
    
    def _load_keys(self):
        """Load existing keys or generate new pair"""
        priv_path = self.key_dir / "elephant_private.key"
        pub_path = self.key_dir / "elephant_public.key"
        
        if priv_path.exists() and pub_path.exists():
            self._private_key = priv_path.read_bytes()
            self._public_key = pub_path.read_bytes()
        else:
            self._generate_keys()
    
    def _generate_keys(self):
        """Generate new Ed25519 keypair"""
        if HAS_RUST:
            priv, pub = _core.generate_keypair()
            self._private_key = Path(priv).read_bytes()
            self._public_key = Path(pub).read_bytes()
            Path(priv).unlink()
            Path(pub).rename(self.key_dir / "elephant_public.key")
        elif HAS_CRYPTO:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            private_key = Ed25519PrivateKey.generate()
            self._private_key = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            self._public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            (self.key_dir / "elephant_private.key").write_bytes(self._private_key)
            (self.key_dir / "elephant_public.key").write_bytes(self._public_key)
        else:
            raise RuntimeError("No crypto backend available")
    
    async def sign(
        self,
        file_path: Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Path:
        """
        Sign a file, return path to signed file.
        Streams progress to TUI.
        """
        if progress_callback:
            progress_callback(f"{self.SYMBOLS['signing']} Signing {file_path.name}...")
        
        # Run in thread pool (Rust/crypto is CPU-bound)
        output_path = await asyncio.to_thread(self._sync_sign, file_path)
        
        if progress_callback:
            size = output_path.stat().st_size
            progress_callback(
                f"{self.COLORS['valid']}{self.SYMBOLS['valid']}{self.COLORS['reset']} "
                f"Signed: {output_path.name} ({size} bytes)"
            )
        
        return output_path
    
    def _sync_sign(self, file_path: Path) -> Path:
        """Synchronous signing (called in thread)"""
        if HAS_RUST:
            output = _core.sign_file(str(file_path), str(self.key_dir / "elephant_private.key"))
            return Path(output)
        
        # Pure Python fallback
        content = file_path.read_bytes()
        
        # Hash with SHA256 (or Blake3 if available)
        try:
            import blake3
            file_hash = blake3.blake3(content).digest()
        except ImportError:
            import hashlib
            file_hash = hashlib.sha256(content).digest()
        
        # Sign
        private_key = Ed25519PrivateKey.from_private_bytes(self._private_key)
        signature = private_key.sign(file_hash)
        
        # Build footer: [64 sig][32 key][4 magic][156 padding]
        footer = (
            signature + 
            self._public_key + 
            b"SIG!" + 
            bytes(156)
        )
        
        output_path = file_path.with_suffix(file_path.suffix + ".signed")
        output_path.write_bytes(content + footer)
        
        return output_path
    
    async def verify(
        self,
        file_path: Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Verify a signed file.
        Returns (is_valid, message) for TUI display.
        """
        if progress_callback:
            progress_callback(f"{self.SYMBOLS['verify']} Verifying {file_path.name}...")
        
        result = await asyncio.to_thread(self._sync_verify, file_path)
        
        is_valid, msg = result
        
        if progress_callback:
            symbol = self.SYMBOLS['valid'] if is_valid else self.SYMBOLS['invalid']
            color = self.COLORS['valid'] if is_valid else self.COLORS['invalid']
            status = "VALID" if is_valid else "TAMPERED"
            progress_callback(f"{color}{symbol}{self.COLORS['reset']} {file_path.name}: {status} - {msg}")
        
        return result
    
    def _sync_verify(self, file_path: Path) -> Tuple[bool, str]:
        """Synchronous verification"""
        if HAS_RUST:
            try:
                valid = _core.verify_file(str(file_path))
                return (valid, "Signature verified" if valid else "Invalid signature")
            except Exception as e:
                return (False, str(e))
        
        # Pure Python
        data = file_path.read_bytes()
        
        if len(data) < 256:
            return (False, "File too small to be signed")
        
        # Check magic
        footer = data[-256:]
        if footer[96:100] != b"SIG!":
            return (False, "Not a signed file (no magic)")
        
        content = data[:-256]
        signature = footer[0:64]
        public_key_bytes = footer[64:96]
        
        # Recompute hash
        try:
            import blake3
            file_hash = blake3.blake3(content).digest()
        except ImportError:
            import hashlib
            file_hash = hashlib.sha256(content).digest()
        
        # Verify
        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, file_hash)
            return (True, "Ed25519 signature valid")
        except InvalidSignature:
            return (False, "Signature mismatch - file tampered")
        except Exception as e:
            return (False, f"Verification error: {e}")
    
    def is_signed(self, file_path: Path) -> bool:
        """Quick check if file has signature footer"""
        if HAS_RUST:
            return _core.is_signed_file(str(file_path))
        
        try:
            data = file_path.read_bytes()
            if len(data) < 256:
                return False
            return data[-160:-156] == b"SIG!"
        except:
            return False
    
    def get_public_key_fingerprint(self) -> str:
        """Return short fingerprint of public key for TUI display"""
        if not self._public_key:
            return "no key"
        return hashlib.sha256(self._public_key).hexdigest()[:16]


# --- TUI Integration ---
async def verify_for_tui(
    file_path: Path,
    log_callback: Callable[[str], None]
) -> bool:
    """
    Entry point for Cynapse TUI.
    Verifies file and streams status to RichLog.
    """
    signer = ElephantSigner()
    
    # Quick check
    if not signer.is_signed(file_path):
        log_callback(f"{signer.COLORS['invalid']}✗{signer.COLORS['reset']} {file_path.name}: Not signed")
        return False
    
    # Full verify
    is_valid, msg = await signer.verify(file_path, log_callback)
    return is_valid


# --- CLI ---
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Elephant Sign - Model signing for Cynapse")
    parser.add_argument("command", choices=["sign", "verify", "keygen"])
    parser.add_argument("file", nargs="?", help="File to sign/verify")
    parser.add_argument("--key-dir", help="Directory for keys")
    
    args = parser.parse_args()
    
    signer = ElephantSigner(Path(args.key_dir) if args.key_dir else None)
    
    if args.command == "keygen":
        print(f"🔑 Keys generated in: {signer.key_dir}")
        print(f"   Public fingerprint: {signer.get_public_key_fingerprint()}")
        
    elif args.command == "sign" and args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File not found: {path}")
            return 1
        
        output = await signer.sign(path, print)
        print(f"\nSigned file: {output}")
        
    elif args.command == "verify" and args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File not found: {path}")
            return 1
        
        valid, msg = await signer.verify(path, print)
        return 0 if valid else 1


if __name__ == "__main__":
    asyncio.run(main())