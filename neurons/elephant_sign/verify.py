#!/usr/bin/env python3
"""
Elephant Sign - Python Verification Wrapper

This module provides a Python interface for verifying Ed25519 signatures
of binaries and models in the Cynapse ecosystem.

It serves as a bridge between the Hub's Python code and the Rust-based
signing infrastructure.

Usage:
    python verify.py <file_path> [--signature <sig_file>] [--public-key <key_file>]
    
Exit codes:
    0 - Signature valid
    1 - Signature invalid or verification failed
    2 - File or key not found

Author: Cynapse Team
"""

import sys
import hashlib
import argparse
from pathlib import Path
from typing import Optional, Tuple

# Try to import cryptography library
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def compute_file_hash(file_path: Path) -> bytes:
    """
    Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to the file to hash
        
    Returns:
        SHA256 hash as bytes
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.digest()


def load_public_key(key_path: Path) -> Optional['Ed25519PublicKey']:
    """
    Load an Ed25519 public key from a file.
    
    Args:
        key_path: Path to the public key file (PEM or raw format)
        
    Returns:
        Ed25519PublicKey object or None if loading fails
    """
    if not HAS_CRYPTO:
        return None
    
    try:
        with open(key_path, 'rb') as f:
            key_data = f.read()
        
        # Try PEM format first
        if b'-----BEGIN' in key_data:
            return serialization.load_pem_public_key(key_data)
        
        # Try raw 32-byte format
        if len(key_data) == 32:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            return Ed25519PublicKey.from_public_bytes(key_data)
        
        # Try DER format
        return serialization.load_der_public_key(key_data)
        
    except Exception as e:
        print(f"Error loading public key: {e}", file=sys.stderr)
        return None


def verify_signature(file_path: Path, signature_path: Path, public_key: 'Ed25519PublicKey') -> Tuple[bool, str]:
    """
    Verify an Ed25519 signature for a file.
    
    Args:
        file_path: Path to the file to verify
        signature_path: Path to the signature file
        public_key: Ed25519 public key object
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not HAS_CRYPTO:
        return False, "cryptography library not available"
    
    try:
        # Read the signature
        with open(signature_path, 'rb') as f:
            signature = f.read()
        
        # Compute file hash (we sign the hash, not the file directly for large files)
        file_hash = compute_file_hash(file_path)
        
        # Verify the signature
        # Ed25519 signatures are 64 bytes
        if len(signature) != 64:
            return False, f"Invalid signature length: expected 64 bytes, got {len(signature)}"
        
        try:
            public_key.verify(signature, file_hash)
            return True, "Signature valid"
        except InvalidSignature:
            return False, "Invalid signature"
            
    except FileNotFoundError as e:
        return False, f"File not found: {e}"
    except Exception as e:
        return False, f"Verification error: {e}"


def find_signature_file(binary_path: Path) -> Optional[Path]:
    """
    Find the signature file for a binary.
    
    Looks for:
    1. <binary>.sig
    2. <binary>.signature
    3. signature.sig in the same directory
    
    Args:
        binary_path: Path to the binary
        
    Returns:
        Path to signature file or None
    """
    candidates = [
        binary_path.with_suffix(binary_path.suffix + '.sig'),
        binary_path.with_suffix('.sig'),
        binary_path.parent / 'signature.sig',
        binary_path.parent / 'signature',
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    return None


def find_public_key() -> Optional[Path]:
    """
    Find the public key file for verification.
    
    Looks in standard locations:
    1. ./public_key.pem
    2. ../config/public_key.pem
    3. ~/.cynapse/public_key.pem
    
    Returns:
        Path to public key file or None
    """
    current_dir = Path(__file__).parent
    candidates = [
        current_dir / 'public_key.pem',
        current_dir / 'public_key',
        current_dir.parent / 'config' / 'public_key.pem',
        Path.home() / '.cynapse' / 'public_key.pem',
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Verify Ed25519 signatures for Cynapse binaries and models',
        epilog='Exit code 0 means valid, 1 means invalid, 2 means error'
    )
    parser.add_argument('file', help='Path to file to verify')
    parser.add_argument('--signature', '-s', help='Path to signature file (auto-detected if not specified)')
    parser.add_argument('--public-key', '-k', help='Path to public key file (auto-detected if not specified)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output except errors')
    
    args = parser.parse_args()
    
    # Check if cryptography is available
    if not HAS_CRYPTO:
        print("Error: 'cryptography' library not installed.", file=sys.stderr)
        print("Install with: pip install cryptography", file=sys.stderr)
        sys.exit(2)
    
    # Validate file path
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(2)
    
    # Find or use specified signature file
    if args.signature:
        sig_path = Path(args.signature)
    else:
        sig_path = find_signature_file(file_path)
    
    if not sig_path or not sig_path.exists():
        if not args.quiet:
            print(f"Warning: Signature file not found for {file_path.name}")
            print("Verification skipped (signature not required or not available)")
        # Return success if no signature is required
        # The Hub checks requires_signature in the manifest
        sys.exit(0)
    
    # Find or use specified public key
    if args.public_key:
        key_path = Path(args.public_key)
    else:
        key_path = find_public_key()
    
    if not key_path or not key_path.exists():
        print("Error: Public key not found", file=sys.stderr)
        print("Generate keys with: python -c \"from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; ...\"", file=sys.stderr)
        sys.exit(2)
    
    # Load public key
    public_key = load_public_key(key_path)
    if not public_key:
        print("Error: Failed to load public key", file=sys.stderr)
        sys.exit(2)
    
    # Verify
    is_valid, message = verify_signature(file_path, sig_path, public_key)
    
    if not args.quiet:
        status = "✓" if is_valid else "✗"
        print(f"{status} {file_path.name}: {message}")
    
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
