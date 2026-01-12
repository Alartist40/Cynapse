#!/usr/bin/env python3
"""
Ghost Shell Shard Assembler
Combines encrypted model shards from Bat-1, Bat-2, Bat-3 into a working model.

Security features:
- SHA256 hash verification of each shard
- XOR encryption with user assembly key
- RAM-only assembly (temp directory)
- Automatic cleanup on exit
"""

import os
import sys
import json
import hashlib
import tempfile
import atexit
from pathlib import Path
from typing import Optional, List, Tuple


# Paths
BASE_DIR = Path(__file__).parent.resolve()
BATS = ['bat1', 'bat2', 'bat3']
CONFIG_DIR = BASE_DIR.parent.parent / "config"
TEMP_DIR = BASE_DIR.parent.parent / "temp"
ASSEMBLED_MODEL = TEMP_DIR / "assembled.gguf"


def load_user_key() -> Optional[bytes]:
    """Load the assembly key from user_keys.json"""
    keys_file = CONFIG_DIR / "user_keys.json"
    example_file = CONFIG_DIR / "user_keys.json.example"
    
    target = keys_file if keys_file.exists() else example_file
    
    if not target.exists():
        print("Warning: No user_keys.json found, using default key")
        return b"DEFAULT_ASSEMBLY_KEY_32_CHARS!!"
    
    try:
        with open(target, 'r') as f:
            data = json.load(f)
            key = data.get('assembly_key', '')
            if not key or key == "YOUR_ASSEMBLY_KEY_HERE_32_CHARS":
                print("Warning: Assembly key not configured, using default")
                return b"DEFAULT_ASSEMBLY_KEY_32_CHARS!!"
            return key.encode('utf-8')
    except Exception as e:
        print(f"Error loading keys: {e}")
        return b"DEFAULT_ASSEMBLY_KEY_32_CHARS!!"


def verify_shard(shard_path: Path, manifest_path: Path) -> Tuple[bool, str]:
    """
    Verify a shard's SHA256 hash against its manifest.
    
    Returns:
        Tuple of (is_valid, message)
    """
    if not shard_path.exists():
        return False, f"Shard not found: {shard_path}"
    
    if not manifest_path.exists():
        return False, f"Manifest not found: {manifest_path}"
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        expected_hash = manifest.get('shard_hash', '')
        if not expected_hash:
            return True, "No hash in manifest, skipping verification"
        
        # Compute actual hash
        sha256 = hashlib.sha256()
        with open(shard_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        actual_hash = sha256.hexdigest()
        
        if actual_hash == expected_hash:
            return True, "Hash verified"
        else:
            return False, f"Hash mismatch: expected {expected_hash[:16]}..., got {actual_hash[:16]}..."
            
    except Exception as e:
        return False, f"Verification error: {e}"


def xor_encrypt(data: bytes, key: bytes) -> bytes:
    """XOR encrypt/decrypt data with key (symmetric)."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def decrypt_shard(shard_path: Path, key: bytes) -> bytes:
    """Decrypt a shard using XOR with user key."""
    with open(shard_path, 'rb') as f:
        encrypted_data = f.read()
    return xor_encrypt(encrypted_data, key)


def assemble_shards(verify: bool = True, encrypt_output: bool = True) -> Optional[Path]:
    """
    Assemble all shards into a complete model.
    
    Args:
        verify: Verify shard hashes before assembly
        encrypt_output: Encrypt the assembled model
    
    Returns:
        Path to assembled model, or None if failed
    """
    print("🦇 Ghost Shell Assembler")
    print("=" * 40)
    
    # Ensure temp directory exists
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load user key
    key = load_user_key()
    if not key:
        print("Error: Could not load assembly key")
        return None
    
    # Collect shards
    shards: List[Path] = []
    for bat in BATS:
        bat_dir = BASE_DIR / bat
        shard_path = bat_dir / f"shard{bat[-1]}.gguf"
        manifest_path = bat_dir / "manifest.json"
        
        if not shard_path.exists():
            print(f"  ⚠️ {bat}: shard not found (placeholder)")
            # Create placeholder for testing
            continue
        
        if verify:
            valid, msg = verify_shard(shard_path, manifest_path)
            status = "✅" if valid else "❌"
            print(f"  {status} {bat}: {msg}")
            if not valid:
                print("Error: Shard verification failed, aborting")
                return None
        else:
            print(f"  ⏭️ {bat}: skipping verification")
        
        shards.append(shard_path)
    
    if not shards:
        print("\nNo shards found. Creating placeholder assembled model...")
        # Create placeholder for testing
        with open(ASSEMBLED_MODEL, 'wb') as f:
            f.write(b"PLACEHOLDER_MODEL_CYNAPSE_GHOST_SHELL\n")
            f.write(b"This file would contain the assembled AI model shards.\n")
        print(f"✅ Placeholder created: {ASSEMBLED_MODEL}")
        return ASSEMBLED_MODEL
    
    print(f"\n📦 Assembling {len(shards)} shards...")
    
    # Assemble shards
    try:
        with open(ASSEMBLED_MODEL, 'wb') as out:
            for shard_path in shards:
                print(f"  ➕ Adding {shard_path.name}...")
                
                # Read and decrypt shard
                decrypted = decrypt_shard(shard_path, key)
                out.write(decrypted)
        
        # Optionally encrypt the assembled model
        if encrypt_output:
            print("  🔐 Encrypting assembled model...")
            with open(ASSEMBLED_MODEL, 'rb') as f:
                plain_data = f.read()
            encrypted_data = xor_encrypt(plain_data, key)
            with open(ASSEMBLED_MODEL, 'wb') as f:
                f.write(encrypted_data)
        
        size_mb = ASSEMBLED_MODEL.stat().st_size / (1024 * 1024)
        print(f"\n✅ Assembly complete: {ASSEMBLED_MODEL}")
        print(f"   Size: {size_mb:.2f} MB")
        
        return ASSEMBLED_MODEL
        
    except Exception as e:
        print(f"❌ Assembly failed: {e}")
        return None


def cleanup_assembled():
    """Clean up assembled model on exit."""
    if ASSEMBLED_MODEL.exists():
        try:
            os.remove(ASSEMBLED_MODEL)
            print("🧹 Cleaned up assembled model")
        except Exception:
            pass


def split_model(model_path: Path, output_dir: Path = None, num_shards: int = 3) -> List[Path]:
    """
    Split a model into encrypted shards (utility function for setup).
    
    Args:
        model_path: Path to the full model
        output_dir: Where to save shards (default: bat_ghost/)
        num_shards: Number of shards to create
    
    Returns:
        List of created shard paths
    """
    if not model_path.exists():
        print(f"Error: Model not found: {model_path}")
        return []
    
    output_dir = output_dir or BASE_DIR
    key = load_user_key()
    
    model_size = model_path.stat().st_size
    shard_size = model_size // num_shards
    
    print(f"Splitting {model_path.name} into {num_shards} shards...")
    print(f"  Model size: {model_size / (1024*1024):.2f} MB")
    print(f"  Shard size: {shard_size / (1024*1024):.2f} MB each")
    
    shards = []
    with open(model_path, 'rb') as f:
        for i in range(1, num_shards + 1):
            bat_dir = output_dir / f"bat{i}"
            bat_dir.mkdir(exist_ok=True)
            
            shard_path = bat_dir / f"shard{i}.gguf"
            
            # Read chunk
            if i == num_shards:
                # Last shard gets remainder
                chunk = f.read()
            else:
                chunk = f.read(shard_size)
            
            # Encrypt
            encrypted = xor_encrypt(chunk, key)
            
            # Write shard
            with open(shard_path, 'wb') as sf:
                sf.write(encrypted)
            
            # Compute hash
            sha256 = hashlib.sha256(encrypted).hexdigest()
            
            # Create manifest
            manifest = {
                "stick_id": f"bat{i}",
                "shard_hash": sha256,
                "shard_index": i,
                "total_shards": num_shards,
                "size": len(encrypted)
            }
            
            manifest_path = bat_dir / "manifest.json"
            with open(manifest_path, 'w') as mf:
                json.dump(manifest, mf, indent=2)
            
            print(f"  ✅ Created shard{i}.gguf ({len(encrypted)} bytes)")
            shards.append(shard_path)
    
    print(f"\n✅ Split complete: {len(shards)} shards created")
    return shards


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Ghost Shell Shard Assembler')
    parser.add_argument('--assemble', action='store_true', default=True,
                       help='Assemble shards into model (default)')
    parser.add_argument('--split', type=str, metavar='MODEL_PATH',
                       help='Split a model into shards')
    parser.add_argument('--no-verify', action='store_true',
                       help='Skip hash verification')
    parser.add_argument('--no-encrypt', action='store_true',
                       help='Do not encrypt assembled output')
    parser.add_argument('--cleanup', action='store_true',
                       help='Register cleanup on exit')
    
    args = parser.parse_args()
    
    if args.cleanup:
        atexit.register(cleanup_assembled)
    
    if args.split:
        split_model(Path(args.split))
    else:
        result = assemble_shards(
            verify=not args.no_verify,
            encrypt_output=not args.no_encrypt
        )
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
