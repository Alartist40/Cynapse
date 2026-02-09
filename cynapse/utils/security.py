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

def redact_sensitive(text: str) -> str:
    """Redact sensitive information like keys and tokens"""
    # Simple regex for things that look like keys
    if not text:
        return text
    # Redact obvious long hex strings or base64
    text = re.sub(r'(sk-[a-zA-Z0-9]{32,})', r'****', text)
    text = re.sub(r'(ghp_[a-zA-Z0-9]{30,})', r'****', text)
    return text
