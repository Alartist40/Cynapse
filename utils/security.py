from pathlib import Path
import sys

def validate_path_traversal(base_path: Path, user_path: Path, name: str = "item") -> bool:
    """
    Validate that a user-provided path is strictly within a base directory.

    Returns:
        True if safe, False if traversal attempt detected.
    """
    resolved_base = base_path.resolve()
    resolved_user = user_path.resolve()

    try:
        resolved_user.relative_to(resolved_base)
        return True
    except ValueError:
        print(f"CRITICAL: Path traversal attempt in '{name}'. Path '{user_path}' is outside its directory.", file=sys.stderr)
        return False
