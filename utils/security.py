#!/usr/bin/env python3
"""
Cynapse Security Utilities Module

Provides shared security functions for input validation and sanitization
across the Cynapse ecosystem. This module addresses several security
vulnerabilities identified in the security audit.

Author: Cynapse Team
"""

import re
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


# Regex patterns for validation
IP_PATTERN = re.compile(
    r'^(any|'
    r'(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?|'  # IPv4 with optional CIDR
    r'([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|'  # Full IPv6
    r'::1|'  # IPv6 localhost
    r'::)$'  # IPv6 any
)

PORT_PATTERN = re.compile(r'^(any|\d{1,5})$')

PROTOCOL_PATTERN = re.compile(r'^(any|tcp|udp|icmp|ip|sctp)$', re.IGNORECASE)

ACTION_PATTERN = re.compile(r'^(allow|deny|accept|drop|pass|block|reject)$', re.IGNORECASE)

# Shell metacharacters that should never appear in command arguments
SHELL_METACHARACTERS = set(';|&$`\n\r\\\'\"<>(){}[]!')


def validate_path(entry_path: Path, base_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate that a path does not escape its base directory (path traversal prevention).
    
    Args:
        entry_path: The path to validate (can be relative or absolute)
        base_path: The base directory that entry_path must be within
        
    Returns:
        Tuple of (is_valid, error_message)
        If valid, returns (True, None)
        If invalid, returns (False, "error description")
    """
    try:
        resolved_entry = entry_path.resolve()
        resolved_base = base_path.resolve()
        
        # This will raise ValueError if the path is outside the base directory
        resolved_entry.relative_to(resolved_base)
        return True, None
        
    except ValueError:
        return False, f"Path traversal attempt: '{entry_path}' is outside '{base_path}'"
    except Exception as e:
        return False, f"Path validation error: {e}"


def validate_ip(ip_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an IP address or CIDR notation.
    
    Args:
        ip_string: The IP address string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not ip_string:
        return False, "IP address cannot be empty"
    
    ip_string = ip_string.strip()
    
    if not IP_PATTERN.match(ip_string):
        return False, f"Invalid IP address format: '{ip_string}'"
    
    # Additional validation for IPv4 octets
    if ip_string != "any" and ":" not in ip_string:
        parts = ip_string.split("/")[0].split(".")
        for part in parts:
            if int(part) > 255:
                return False, f"Invalid IPv4 octet: {part}"
    
    # Check for shell metacharacters
    if contains_shell_metacharacters(ip_string):
        return False, f"IP contains forbidden characters: '{ip_string}'"
    
    return True, None


def validate_port(port_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a port number.
    
    Args:
        port_string: The port string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not port_string:
        return False, "Port cannot be empty"
    
    port_string = str(port_string).strip()
    
    if not PORT_PATTERN.match(port_string):
        return False, f"Invalid port format: '{port_string}'"
    
    if port_string != "any":
        port_num = int(port_string)
        if port_num < 0 or port_num > 65535:
            return False, f"Port out of range (0-65535): {port_num}"
    
    return True, None


def validate_protocol(protocol_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a network protocol.
    
    Args:
        protocol_string: The protocol string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not protocol_string:
        return False, "Protocol cannot be empty"
    
    protocol_string = protocol_string.strip()
    
    if not PROTOCOL_PATTERN.match(protocol_string):
        return False, f"Invalid protocol: '{protocol_string}'. Must be tcp, udp, icmp, ip, sctp, or any"
    
    return True, None


def validate_action(action_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a firewall action.
    
    Args:
        action_string: The action string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not action_string:
        return False, "Action cannot be empty"
    
    action_string = action_string.strip()
    
    if not ACTION_PATTERN.match(action_string):
        return False, f"Invalid action: '{action_string}'. Must be allow, deny, accept, drop, pass, block, or reject"
    
    return True, None


def contains_shell_metacharacters(input_string: str) -> bool:
    """
    Check if a string contains shell metacharacters.
    
    Args:
        input_string: The string to check
        
    Returns:
        True if the string contains shell metacharacters, False otherwise
    """
    return bool(SHELL_METACHARACTERS.intersection(set(input_string)))


def sanitize_llm_output(output_dict: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], list]:
    """
    Sanitize and validate LLM-generated firewall rule output.
    
    This function addresses the critical command injection vulnerability
    (CVE estimate 8.8) by validating all fields in LLM output before
    they are used to generate shell commands.
    
    Args:
        output_dict: Dictionary containing LLM-generated rule parameters
        
    Returns:
        Tuple of (is_valid, sanitized_dict, list_of_errors)
    """
    errors = []
    sanitized = {}
    
    # Required fields and their validators
    validators = {
        "src_ip": validate_ip,
        "dst_ip": validate_ip,
        "src_port": validate_port,
        "dst_port": validate_port,
        "proto": validate_protocol,
        "action": validate_action,
    }
    
    # Optional fields with default values
    defaults = {
        "src_ip": "any",
        "dst_ip": "any",
        "src_port": "any",
        "dst_port": "any",
        "proto": "any",
        "time_start": "00:00",
        "time_end": "23:59",
    }
    
    # Validate each field
    for field, validator in validators.items():
        value = output_dict.get(field, defaults.get(field, ""))
        
        # Convert to string if necessary
        value = str(value).strip() if value else defaults.get(field, "")
        
        # Check for shell metacharacters first
        if contains_shell_metacharacters(value):
            errors.append(f"Field '{field}' contains forbidden shell metacharacters")
            sanitized[field] = defaults.get(field, "any")
            continue
        
        # Run the specific validator
        is_valid, error = validator(value)
        if is_valid:
            sanitized[field] = value
        else:
            errors.append(f"{field}: {error}")
            sanitized[field] = defaults.get(field, "any")
    
    # Handle time fields (simple validation)
    time_pattern = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
    
    for time_field in ["time_start", "time_end"]:
        value = output_dict.get(time_field, defaults[time_field])
        value = str(value).strip()
        
        if time_pattern.match(value):
            sanitized[time_field] = value
        else:
            errors.append(f"Invalid time format for {time_field}: '{value}'")
            sanitized[time_field] = defaults[time_field]
    
    is_valid = len(errors) == 0
    return is_valid, sanitized, errors


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """
    Mask an API key for safe logging, showing only the first few characters.
    
    Args:
        api_key: The API key to mask
        visible_chars: Number of characters to show (default 4)
        
    Returns:
        Masked API key string
    """
    if not api_key:
        return "<empty>"
    
    if len(api_key) <= visible_chars:
        return "*" * len(api_key)
    
    return api_key[:visible_chars] + "*" * (len(api_key) - visible_chars)


def hash_api_key(api_key: str) -> str:
    """
    Create a SHA256 hash of an API key for logging correlation.
    
    Args:
        api_key: The API key to hash
        
    Returns:
        First 8 characters of the SHA256 hash
    """
    if not api_key:
        return "<empty>"
    
    return hashlib.sha256(api_key.encode()).hexdigest()[:8]
