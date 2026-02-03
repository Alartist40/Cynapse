"""
Cynapse Security Utilities
"""
import re
import hashlib

def sanitize_path(path: str) -> str:
    """Sanitize file path to prevent traversal"""
    return path.replace("..", "")

def mask_key(key: str) -> str:
    """Mask API key for logging"""
    if not key or len(key) < 8:
        return "****"
    return f"{key[:4]}****"

def hash_key(key: str) -> str:
    """Hash key for correlation"""
    return hashlib.sha256(key.encode()).hexdigest()

def validate_input(text: str) -> bool:
    """Basic input validation against shell injection chars"""
    unsafe = [";", "&&", "|", "`", "$("]
    return not any(char in text for char in unsafe)
