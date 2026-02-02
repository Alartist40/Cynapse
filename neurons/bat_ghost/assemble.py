#!/usr/bin/env python3
"""
Ghost Shell Shard Assembler v2.0
Optimized: Async parallel processing, NumPy-accelerated XOR.
"""

import os
import sys
import json
import hashlib
import asyncio
import atexit
import numpy as np
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
        return b"DEFAULT_ASSEMBLY_KEY_32_CHARS!!"
    
    try:
        with open(target, 'r') as f:
            data = json.load(f)
            key = data.get('assembly_key', '')
            if not key or key == "YOUR_ASSEMBLY_KEY_HERE_32_CHARS":
                return b"DEFAULT_ASSEMBLY_KEY_32_CHARS!!"
            return key.encode('utf-8')
    except Exception:
        return b"DEFAULT_ASSEMBLY_KEY_32_CHARS!!"


async def verify_shard_async(shard_path: Path, manifest_path: Path) -> Tuple[bool, str]:
    """Async SHA256 verification"""
    if not shard_path.exists() or not manifest_path.exists():
        return False, "Files missing"
    
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        expected_hash = manifest.get('shard_hash', '')
        if not expected_hash: return True, "No hash"
        
        # Offload hashing to thread to not block event loop
        def hash_file():
            sha256 = hashlib.sha256()
            with open(shard_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()

        actual_hash = await asyncio.to_thread(hash_file)
        return actual_hash == expected_hash, "Verified" if actual_hash == expected_hash else "Mismatch"
    except Exception as e:
        return False, str(e)


def fast_xor(data: bytes, key: bytes) -> bytes:
    """NumPy accelerated XOR operation for large buffers"""
    data_np = np.frombuffer(data, dtype=np.uint8)
    key_np = np.frombuffer(key, dtype=np.uint8)

    # Repeat key to match data size
    key_repeated = np.resize(key_np, data_np.shape)

    # Perform bitwise XOR
    result_np = np.bitwise_xor(data_np, key_repeated)
    return result_np.tobytes()


async def process_shard(bat: str, key: bytes, verify: bool) -> Optional[bytes]:
    """Verify and decrypt a single shard in parallel"""
    bat_dir = BASE_DIR / bat
    shard_path = bat_dir / f"shard{bat[-1]}.gguf"
    manifest_path = bat_dir / "manifest.json"
    
    if not shard_path.exists():
        return None

    if verify:
        valid, msg = await verify_shard_async(shard_path, manifest_path)
        if not valid:
            print(f"  ❌ {bat}: {msg}")
            return None
    
    print(f"  🔓 {bat}: Decrypting...")
    def read_and_decrypt():
        with open(shard_path, 'rb') as f:
            data = f.read()
        return fast_xor(data, key)

    return await asyncio.to_thread(read_and_decrypt)


async def assemble_shards_async(verify: bool = True, encrypt_output: bool = True) -> Optional[Path]:
    """Main async assembly flow"""
    print("🦇 Ghost Shell Assembler v2.0")
    print("=" * 40)
    
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    key = load_user_key()
    
    # Parallel processing of all shards
    tasks = [process_shard(bat, key, verify) for bat in BATS]
    shard_data_list = await asyncio.gather(*tasks)
    
    # Filter out failed shards
    valid_shards = [d for d in shard_data_list if d is not None]

    if not valid_shards:
        print("\nNo valid shards found. Creating placeholder...")
        with open(ASSEMBLED_MODEL, 'wb') as f:
            f.write(b"PLACEHOLDER_MODEL_V2\n")
        return ASSEMBLED_MODEL
    
    print(f"\n📦 Combining {len(valid_shards)} shards...")
    
    try:
        # Concatenate and optionally re-encrypt for RAM-disk storage
        full_model = b"".join(valid_shards)
        if encrypt_output:
            full_model = fast_xor(full_model, key)

        with open(ASSEMBLED_MODEL, 'wb') as f:
            f.write(full_model)

        print(f"✅ Assembly complete: {ASSEMBLED_MODEL} ({len(full_model)/(1024*1024):.2f} MB)")
        return ASSEMBLED_MODEL
    except Exception as e:
        print(f"❌ Assembly failed: {e}")
        return None


def cleanup():
    if ASSEMBLED_MODEL.exists():
        try: os.remove(ASSEMBLED_MODEL)
        except: pass

if __name__ == "__main__":
    atexit.register(cleanup)
    asyncio.run(assemble_shards_async())
