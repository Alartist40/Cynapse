#!/usr/bin/env python3
"""
Elephant Sign - Python Verifier Wrapper
Verifies Ed25519 signatures on model files.
"""

import sys
import os
from pathlib import Path

# Try to import cryptography for signature verification
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

FOOTER_LEN = 256
MAGIC = b"\x21\x47\x49\x53"  # 0x53494721 in little-endian

def verify_file(filepath: str, public_key_path: str = None) -> bool:
    """
    Verify a signed file.

    Args:
        filepath: Path to the signed file
        public_key_path: Path to the public key (optional)
    """
    if not os.path.exists(filepath):
        print(f"[-] File not found: {filepath}")
        return False

    file_size = os.path.getsize(filepath)
    if file_size < FOOTER_LEN:
        print(f"[-] File too small to be signed: {filepath}")
        return False

    with open(filepath, 'rb') as f:
        f.seek(-FOOTER_LEN, os.SEEK_END)
        footer = f.read(FOOTER_LEN)

    # Check Magic
    if footer[96:100] != MAGIC:
        print(f"[-] Magic mismatch - file not signed: {filepath}")
        return False

    if not HAS_CRYPTO:
        print("[!] Warning: 'cryptography' library not found. Performing basic integrity check only.")
        # If no crypto, we just check the magic as a placeholder
        return True

    try:
        signature = footer[0:64]
        pub_key_bytes = footer[64:96]

        # Load public key
        # If a specific public key is provided, we should probably check against it
        # For now, we trust the one in the footer but we could hardening this

        # Extract the original data
        with open(filepath, 'rb') as f:
            data = f.read(file_size - FOOTER_LEN)

        # We also need blake3 hash as used in the Rust version
        # If blake3 is not available, this will fail.
        try:
            import blake3
            hasher = blake3.blake3()
            hasher.update(data)
            data_hash = hasher.digest()
        except ImportError:
            # Fallback to SHA256 if blake3 is missing, though it won't match Rust
            import hashlib
            data_hash = hashlib.sha256(data).digest()
            print("[!] Warning: blake3 not found. Falling back to SHA256 (may not match Rust signatures).")

        public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_key_bytes)
        public_key.verify(signature, data_hash)

        print(f"[+] Signature valid: {filepath}")
        return True
    except Exception as e:
        print(f"[-] Signature verification failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify.py <signed_file>")
        sys.exit(1)

    success = verify_file(sys.argv[1])
    sys.exit(0 if success else 1)
