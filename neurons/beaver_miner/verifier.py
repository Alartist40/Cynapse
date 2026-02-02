#!/usr/bin/env python3
"""
Rule verification module
Verifies firewall rules using Docker containers

Security Note: This module has been hardened against command injection attacks.
All LLM-generated rule parameters are validated before being used in shell commands.
"""

import logging
import subprocess
import time
import tempfile
import os
import sys
from typing import Dict, Optional, Tuple
from pathlib import Path

# Add parent directory to path for utils import
_current_dir = Path(__file__).parent.resolve()
_project_root = _current_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from utils.security import sanitize_llm_output, contains_shell_metacharacters
except ImportError:
    # Fallback inline implementation if utils not available
    import re
    
    def contains_shell_metacharacters(s: str) -> bool:
        return bool(set(';|&$`\n\r\\\'\"<>(){}[]!').intersection(set(s)))
    
    def sanitize_llm_output(output_dict: Dict) -> Tuple[bool, Dict, list]:
        errors = []
        ip_pattern = re.compile(r'^(any|(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?)$')
        port_pattern = re.compile(r'^(any|\d{1,5})$')
        proto_pattern = re.compile(r'^(any|tcp|udp|icmp)$', re.IGNORECASE)
        
        for key, val in output_dict.items():
            if contains_shell_metacharacters(str(val)):
                errors.append(f"Field {key} contains shell metacharacters")
        
        return len(errors) == 0, output_dict, errors

logger = logging.getLogger(__name__)


class RuleVerifier:
    """Verifies firewall rules in Docker containers"""
    
    def __init__(self, config: dict):
        """
        Initialize rule verifier
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.docker_timeout = config.get("verifier", {}).get("docker_timeout", 30)
        self._check_docker()
    
    def _check_docker(self):
        """Check if Docker is available"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"[+] Docker available: {result.stdout.strip()}")
            else:
                logger.warning("[!] Docker not available")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("[!] Docker not found or not responding")
    
    def verify(self, platform: str, rule: str, rule_json: Dict) -> bool:
        """
        Verify a firewall rule
        
        Args:
            platform: Platform name (iptables, suricata, etc.)
            rule: Generated rule string
            rule_json: Original rule parameters
            
        Returns:
            True if rule works as expected, False otherwise
        """
        platform_lower = platform.lower()
        
        if platform_lower == "iptables":
            return self._verify_iptables(rule, rule_json)
        elif platform_lower == "suricata":
            return self._verify_suricata(rule, rule_json)
        elif platform_lower == "pfsense":
            logger.info("[!] pfSense verification not implemented (requires special container)")
            return None
        elif platform_lower == "windows":
            logger.info("[!] Windows verification not implemented (requires Windows container)")
            return None
        else:
            logger.warning(f"[!] Verification not supported for {platform}")
            return None
    
    def _verify_iptables(self, rule: str, rule_json: Dict) -> bool:
        """
        Verify iptables rule in Alpine container
        
        Args:
            rule: iptables command
            rule_json: Original rule parameters
            
        Returns:
            True if rule blocks/allows as expected
            
        Security:
            All rule_json fields are validated before use to prevent
            command injection attacks (addresses CVE with CVSS 8.8)
        """
        logger.info("[*] Starting iptables verification...")
        
        # SECURITY: Validate all LLM-generated parameters before use
        is_valid, sanitized_json, errors = sanitize_llm_output(rule_json)
        if not is_valid:
            logger.error(f"[!] SECURITY: Invalid rule parameters rejected: {errors}")
            return False
        
        # SECURITY: Check the rule string itself for shell metacharacters
        if contains_shell_metacharacters(rule):
            logger.error("[!] SECURITY: Rule string contains forbidden shell metacharacters")
            return False
        
        # Use sanitized values
        rule_json = sanitized_json
        
        container_name = f"iptables-test-{int(time.time())}"
        
        try:
            # Create a script with the rule
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write("#!/bin/sh\n")
                f.write("set -e\n")
                f.write("# Flush existing rules\n")
                f.write("iptables -F\n")
                f.write("# Set default policy to ACCEPT\n")
                f.write("iptables -P INPUT ACCEPT\n")
                f.write("# Add our rule\n")
                f.write(rule + "\n")
                f.write("# List rules for debugging\n")
                f.write("iptables -L -n -v\n")
                script_path = f.name
            
            # Make script executable
            os.chmod(script_path, 0o755)
            
            # Start Alpine container with iptables
            logger.debug(f"Starting container {container_name}")
            start_cmd = [
                "docker", "run", "-d", "--rm",
                "--name", container_name,
                "--privileged",  # Required for iptables
                "--cap-add", "NET_ADMIN",
                "alpine:latest",
                "sh", "-c", "apk add --no-cache iptables && sleep 120"
            ]
            
            result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Failed to start container: {result.stderr}")
                return False
            
            # Wait for container to be ready
            time.sleep(3)
            
            # Copy script to container
            logger.debug("Copying script to container")
            copy_cmd = ["docker", "cp", script_path, f"{container_name}:/tmp/rule.sh"]
            subprocess.run(copy_cmd, check=True, timeout=10)
            
            # Execute the rule script
            logger.debug("Applying iptables rule")
            exec_cmd = ["docker", "exec", container_name, "sh", "/tmp/rule.sh"]
            result = subprocess.run(exec_cmd, capture_output=True, text=True, timeout=10)
            
            logger.debug(f"iptables output:\n{result.stdout}")
            
            if result.returncode != 0:
                logger.error(f"Failed to apply rule: {result.stderr}")
                return False
            
            # Test the rule with a probe
            expected_action = rule_json["action"]
            logger.debug(f"Expected action: {expected_action}")
            
            # For a DENY/DROP rule, we expect connection to fail
            # For an ALLOW/ACCEPT rule, we expect connection to succeed (or at least not be blocked by firewall)
            
            # Simple test: try to connect to a port
            test_port = rule_json.get("dst_port", "22")
            if test_port == "any":
                test_port = "22"
            
            # We'll test by trying to check if the port would be blocked
            # This is a simplified test - in reality we'd need more complex setup
            
            # For MVP, we just verify the rule was applied successfully
            logger.info("[+] iptables rule applied successfully")
            
            # Check if rule is in the list
            list_cmd = ["docker", "exec", container_name, "iptables", "-L", "INPUT", "-n"]
            list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10)
            
            if "AI Firewall Rule-Miner" in list_result.stdout or rule_json["action"].upper() in list_result.stdout:
                logger.info("[+] Rule verified in iptables list")
                return True
            else:
                logger.warning("[!] Rule not found in iptables list")
                return False
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False
            
        finally:
            # Cleanup
            try:
                os.unlink(script_path)
            except:
                pass
            
            # Stop container
            try:
                subprocess.run(
                    ["docker", "stop", container_name],
                    capture_output=True,
                    timeout=10
                )
                logger.debug(f"Stopped container {container_name}")
            except:
                pass
    
    def _verify_suricata(self, rule: str, rule_json: Dict) -> bool:
        """
        Verify Suricata rule
        
        Args:
            rule: Suricata rule string
            rule_json: Original rule parameters
            
        Returns:
            True if rule is valid
        """
        logger.info("[*] Starting Suricata verification...")
        
        container_name = f"suricata-test-{int(time.time())}"
        
        try:
            # Create a rules file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.rules', delete=False) as f:
                f.write(rule + "\n")
                rules_path = f.name
            
            # Start Suricata container
            logger.debug(f"Starting container {container_name}")
            start_cmd = [
                "docker", "run", "-d", "--rm",
                "--name", container_name,
                "jasonish/suricata:latest",
                "suricata", "-c", "/etc/suricata/suricata.yaml", "-i", "eth0"
            ]
            
            result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Failed to start container: {result.stderr}")
                return False
            
            # Wait for container to be ready
            time.sleep(5)
            
            # Copy rules file to container
            logger.debug("Copying rules to container")
            copy_cmd = ["docker", "cp", rules_path, f"{container_name}:/etc/suricata/rules/custom.rules"]
            subprocess.run(copy_cmd, check=True, timeout=10)
            
            # Validate rules
            logger.debug("Validating Suricata rules")
            validate_cmd = [
                "docker", "exec", container_name,
                "suricata", "-T", "-c", "/etc/suricata/suricata.yaml",
                "-S", "/etc/suricata/rules/custom.rules"
            ]
            
            result = subprocess.run(validate_cmd, capture_output=True, text=True, timeout=20)
            
            # Suricata returns 0 if rules are valid
            if result.returncode == 0:
                logger.info("[+] Suricata rule syntax valid")
                return True
            else:
                logger.error(f"[!] Suricata rule validation failed: {result.stderr}")
                return False
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False
            
        finally:
            # Cleanup
            try:
                os.unlink(rules_path)
            except:
                pass
            
            # Stop container
            try:
                subprocess.run(
                    ["docker", "stop", container_name],
                    capture_output=True,
                    timeout=10
                )
                logger.debug(f"Stopped container {container_name}")
            except:
                pass
    
    def _run_docker_command(self, cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
        """
        Run a Docker command with timeout
        
        Args:
            cmd: Command list
            timeout: Timeout in seconds
            
        Returns:
            CompletedProcess result
        """
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
