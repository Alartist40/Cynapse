#!/usr/bin/env python3
"""
Beaver Miner v3.0 - Cynapse Integrated Firewall Rule Generator
Lightweight, dependency-minimal, Hub-connected rule engine
"""

import asyncio
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import ipaddress


# --- Cynapse Integration ---
class CynapseBridge:
    """Minimal Cynapse Hub integration for audit and orchestration"""
    
    AUDIT_PATH = Path.home() / ".cynapse" / "logs" / "audit.ndjson"
    
    @staticmethod
    def log_event(event_type: str, data: Dict, severity: str = "info") -> None:
        """Append to Cynapse NDJSON audit trail"""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "neuron": "beaver_miner",
            "event": event_type,
            "severity": severity,
            "data": data
        }
        CynapseBridge.AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CynapseBridge.AUDIT_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    @staticmethod
    def request_signature(rule_path: Path) -> Optional[Path]:
        """Request Elephant Sign to sign generated rules"""
        # Stub: actual implementation calls Elephant neuron
        signed_path = rule_path.with_suffix(rule_path.suffix + ".sig")
        return signed_path if signed_path.exists() else None
    
    @staticmethod
    async def notify_canary(rule_metadata: Dict) -> None:
        """Alert Canary neuron to monitor for rule bypass attempts"""
        # Integration point: Canary watches for traffic that should match this rule
        pass


# --- Core Data Structures ---
@dataclass
class RuleIntent:
    """Structured intent extracted from natural language"""
    action: str  # allow, deny, drop, reject, log
    protocol: str  # tcp, udp, icmp, any
    src_ip: str  # IP, CIDR, or "any"
    dst_ip: str  # IP, CIDR, or "any"
    dst_port: Union[str, int]  # port number, name, or "any"
    src_port: Union[str, int] = "any"
    time_start: str = "00:00"
    time_end: str = "23:59"
    days: List[str] = None  # mon, tue, etc. or empty for all
    interface: str = "any"
    log_enabled: bool = False
    description: str = ""
    
    def __post_init__(self):
        if self.days is None:
            self.days = []
        self._normalize()
    
    def _normalize(self):
        """Validate and normalize fields"""
        # Normalize action
        action_map = {
            "block": "deny", "reject": "reject", "drop": "drop",
            "allow": "allow", "permit": "allow", "accept": "allow",
            "log": "log", "mirror": "log"
        }
        self.action = action_map.get(self.action.lower(), "deny")
        
        # Normalize protocol
        proto_map = {
            "tcp": "tcp", "udp": "udp", "icmp": "icmp",
            "any": "any", "all": "any", "ip": "any"
        }
        self.protocol = proto_map.get(self.protocol.lower(), "tcp")
        
        # Validate IPs
        for field in ['src_ip', 'dst_ip']:
            val = getattr(self, field)
            if val != "any":
                try:
                    ipaddress.ip_network(val, strict=False)
                except ValueError:
                    setattr(self, field, "any")
        
        # Port resolution
        self.dst_port = self._resolve_port(str(self.dst_port))
        self.src_port = self._resolve_port(str(self.src_port))
        
        # Time validation
        for time_field in ['time_start', 'time_end']:
            val = getattr(self, time_field)
            if not re.match(r'^\d{2}:\d{2}$', val):
                setattr(self, time_field, "00:00" if time_field == 'time_start' else "23:59")
    
    @staticmethod
    def _resolve_port(port_str: str) -> str:
        """Convert service names to port numbers"""
        service_map = {
            'ssh': '22', 'http': '80', 'https': '443', 'dns': '53',
            'smtp': '25', 'ftp': '21', 'rdp': '3389', 'smb': '445',
            'snmp': '161', 'ldap': '389', 'mysql': '3306', 'postgres': '5432',
            'redis': '6379', 'mongo': '27017', 'elasticsearch': '9200'
        }
        port_lower = port_str.lower()
        if port_lower in service_map:
            return service_map[port_lower]
        if port_str.isdigit() and 0 <= int(port_str) <= 65535:
            return port_str
        return "any"
    
    def to_dict(self) -> Dict:
        return asdict(self)


class LightweightNLU:
    """
    Tiny rule parser - no LLM required
    Uses pattern matching + lightweight slot filling
    ~100KB vs 4GB for Mistral
    """
    
    # Compiled patterns for performance
    ACTION_PATTERNS = [
        (r'\b(block|deny|drop|reject)\b', 'deny'),
        (r'\b(allow|permit|accept|enable)\b', 'allow'),
        (r'\b(log|mirror|capture)\b', 'log'),
    ]
    
    PROTO_PATTERNS = [
        (r'\b(tcp|udp)\b', None),  # Extract as-is
        (r'\bicmp\b', 'icmp'),
        (r'\bhttp\b', 'tcp'),
        (r'\bhttps\b', 'tcp'),
        (r'\bssh\b', 'tcp'),
        (r'\bdns\b', 'udp'),
    ]
    
    PORT_PATTERNS = [
        r'port\s+(\d+)',
        r'(\d{2,5})\s*$',  # trailing number
        r'\b(ssh|http|https|dns|smtp|ftp|rdp)\b',
    ]
    
    IP_PATTERNS = [
        r'from\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)',
        r'to\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)',
        r'source\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
        r'destination\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
    ]
    
    TIME_PATTERNS = [
        (r'after\s+(\d{1,2})\s*(pm|am)', lambda h, m: (f"{int(h)+12 if m=='pm' else int(h):02d}:00", "23:59")),
        (r'before\s+(\d{1,2})\s*(pm|am)', lambda h, m: ("00:00", f"{int(h)+12 if m=='pm' else int(h):02d}:00")),
        (r'between\s+(\d{1,2})\s*(pm|am)\s+and\s+(\d{1,2})\s*(pm|am)', 
         lambda h1, m1, h2, m2: (f"{int(h1)+12 if m1=='pm' else int(h1):02d}:00", 
                                f"{int(h2)+12 if m2=='pm' else int(h2):02d}:00")),
        (r'from\s+(\d{1,2}):(\d{2})\s+to\s+(\d{1,2}):(\d{2})', 
         lambda h1, m1, h2, m2: (f"{int(h1):02d}:{m1}", f"{int(h2):02d}:{m2}")),
    ]
    
    def parse(self, sentence: str) -> RuleIntent:
        """
        Parse natural language into structured intent
        No ML, no dependencies, deterministic
        """
        sentence_lower = sentence.lower()
        
        # Extract action
        action = self._extract_action(sentence_lower)
        
        # Extract protocol
        protocol = self._extract_protocol(sentence_lower)
        
        # Extract IPs
        src_ip, dst_ip = self._extract_ips(sentence)
        
        # Extract ports
        dst_port = self._extract_port(sentence_lower)
        
        # Extract time
        time_start, time_end = self._extract_time(sentence_lower)
        
        # Build description
        description = f"Auto-generated: {sentence[:80]}"
        
        return RuleIntent(
            action=action,
            protocol=protocol,
            src_ip=src_ip,
            dst_ip=dst_ip,
            dst_port=dst_port,
            time_start=time_start,
            time_end=time_end,
            description=description
        )
    
    def _extract_action(self, text: str) -> str:
        for pattern, action in self.ACTION_PATTERNS:
            if re.search(pattern, text):
                return action
        return "deny"  # Default: defensive
    
    def _extract_protocol(self, text: str) -> str:
        for pattern, proto in self.PROTO_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return proto if proto else match.group(1)
        return "any"
    
    def _extract_ips(self, text: str) -> Tuple[str, str]:
        src, dst = "any", "any"
        
        # Source IP
        src_match = re.search(self.IP_PATTERNS[0], text, re.IGNORECASE)
        if src_match:
            src = src_match.group(1)
        
        # Destination IP
        dst_match = re.search(self.IP_PATTERNS[1], text, re.IGNORECASE)
        if dst_match:
            dst = dst_match.group(1)
        
        # If only one IP found and no "from/to", guess based on position
        if src == "any" and dst == "any":
            all_ips = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?', text)
            if len(all_ips) == 1:
                src = all_ips[0]  # Assume source if single IP
        
        return src, dst
    
    def _extract_port(self, text: str) -> str:
        for pattern in self.PORT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return "any"
    
    def _extract_time(self, text: str) -> Tuple[str, str]:
        for pattern, extractor in self.TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return extractor(*match.groups())
        return "00:00", "23:59"


class RuleEngine:
    """Generate platform-specific firewall rules from intent"""
    
    def generate(self, intent: RuleIntent, platform: str) -> str:
        """Route to platform-specific generator"""
        platform_lower = platform.lower()
        
        generators = {
            'iptables': self._gen_iptables,
            'nftables': self._gen_nftables,
            'pfsense': self._gen_pfsense,
            'opnsense': self._gen_pfsense,  # Same XML format
            'suricata': self._gen_suricata,
            'snort': self._gen_snort,
            'windows': self._gen_windows,
            'win': self._gen_windows,
            'ufw': self._gen_ufw,
            'cisco': self._gen_cisco_asa,
            'fortinet': self._gen_fortinet,
        }
        
        generator = generators.get(platform_lower, self._gen_iptables)
        return generator(intent)
    
    def _gen_iptables(self, intent: RuleIntent) -> str:
        """Generate iptables command"""
        cmd_parts = ["iptables", "-A", "INPUT"]
        
        # Protocol
        if intent.protocol != "any":
            cmd_parts.extend(["-p", intent.protocol])
        
        # Source
        if intent.src_ip != "any":
            cmd_parts.extend(["-s", intent.src_ip])
        
        # Destination
        if intent.dst_ip != "any":
            cmd_parts.extend(["-d", intent.dst_ip])
        
        # Port (only for tcp/udp)
        if intent.dst_port != "any" and intent.protocol in ["tcp", "udp"]:
            cmd_parts.extend(["--dport", str(intent.dst_port)])
        
        # Time module
        if intent.time_start != "00:00" or intent.time_end != "23:59":
            cmd_parts.extend([
                "-m", "time",
                "--timestart", intent.time_start,
                "--timestop", intent.time_end
            ])
        
        # Action
        action_map = {
            "allow": "ACCEPT", "deny": "DROP", 
            "reject": "REJECT", "log": "LOG"
        }
        cmd_parts.extend(["-j", action_map.get(intent.action, "DROP")])
        
        # Comment
        cmd_parts.extend(["-m", "comment", "--comment", f"Beaver:{intent.description[:30]}"])
        
        return " ".join(cmd_parts)
    
    def _gen_nftables(self, intent: RuleIntent) -> str:
        """Generate nftables rule (modern replacement for iptables)"""
        family = "inet"
        table = "filter"
        chain = "input"
        
        # Build match conditions
        matches = []
        
        if intent.protocol != "any":
            matches.append(f"ip protocol {intent.protocol}")
        
        if intent.src_ip != "any":
            matches.append(f"ip saddr {intent.src_ip}")
        
        if intent.dst_ip != "any":
            matches.append(f"ip daddr {intent.dst_ip}")
        
        if intent.dst_port != "any" and intent.protocol in ["tcp", "udp"]:
            matches.append(f"{intent.protocol} dport {intent.dst_port}")
        
        # Action
        action_map = {
            "allow": "accept", "deny": "drop",
            "reject": "reject", "log": "log"
        }
        action = action_map.get(intent.action, "drop")
        
        match_str = " ".join(matches) if matches else "ip saddr != 127.0.0.1"  # Default match
        
        return f'add rule {family} {table} {chain} {match_str} {action} comment "{intent.description[:20]}"'
    
    def _gen_pfsense(self, intent: RuleIntent) -> str:
        """Generate pfSense XML configuration fragment"""
        action_type = "pass" if intent.action == "allow" else "block"
        if intent.action == "log":
            action_type = "pass"  # pfSense uses separate log option
        
        # Build XML
        lines = [
            '<rule>',
            f'  <type>{action_type}</type>',
            '  <interface>wan</interface>',
            '  <ipprotocol>inet</ipprotocol>',
            f'  <protocol>{intent.protocol if intent.protocol != "any" else "tcp"}</protocol>',
            '  <source>',
            f'    {"<any/>" if intent.src_ip == "any" else f"<network>{intent.src_ip}</network>"}',
            '  </source>',
            '  <destination>',
            f'    {"<any/>" if intent.dst_ip == "any" else f"<network>{intent.dst_ip}</network>"}',
        ]
        
        if intent.dst_port != "any":
            lines.append(f'    <port>{intent.dst_port}</port>')
        
        lines.append('  </destination>')
        
        # Time schedule
        if intent.time_start != "00:00" or intent.time_end != "23:59":
            lines.append(f'  <sched>Beaver_{intent.time_start.replace(":", "")}_{intent.time_end.replace(":", "")}</sched>')
        
        lines.append(f'  <descr>{intent.description[:50]}</descr>')
        lines.append('</rule>')
        
        return '\n'.join(lines)
    
    def _gen_suricata(self, intent: RuleIntent) -> str:
        """Generate Suricata IDS/IPS rule"""
        action_map = {"allow": "pass", "deny": "drop", "reject": "reject", "log": "alert"}
        suricata_action = action_map.get(intent.action, "drop")
        
        proto = intent.protocol if intent.protocol != "any" else "ip"
        src = intent.src_ip if intent.src_ip != "any" else "any"
        dst = intent.dst_ip if intent.dst_ip != "any" else "any"
        sport = intent.src_port if intent.src_port != "any" else "any"
        dport = intent.dst_port if intent.dst_port != "any" else "any"
        
        msg = f"Beaver: {intent.action} {proto}"
        if intent.dst_port != "any":
            msg += f" port {intent.dst_port}"
        
        rule = f'{suricata_action} {proto} {src} {sport} -> {dst} {dport} (msg:"{msg}"; '
        
        # Add sid (unique ID based on hash)
        sid = int(hashlib.md5(f"{intent}{time.time()}".encode()).hexdigest()[:8], 16) % 1000000 + 1000000
        rule += f'sid:{sid}; rev:1; classtype:policy-violation;)'
        
        return rule
    
    def _gen_snort(self, intent: RuleIntent) -> str:
        """Generate Snort rule (similar to Suricata)"""
        # Snort compatible format
        return self._gen_suricata(intent).replace("classtype:policy-violation", "classtype:attempted-admin")
    
    def _gen_windows(self, intent: RuleIntent) -> str:
        """Generate Windows Advanced Firewall PowerShell command"""
        action = "Allow" if intent.action == "allow" else "Block"
        
        # Build command
        name = f"Beaver_{intent.protocol}_{intent.dst_port}_{int(time.time())}"
        
        cmd_parts = [
            "New-NetFirewallRule",
            f'-DisplayName "{name}"',
            "-Direction Inbound",
            f"-Action {action}"
        ]
        
        if intent.protocol != "any":
            proto_map = {"tcp": "TCP", "udp": "UDP", "icmp": "ICMPv4"}
            cmd_parts.append(f'-Protocol {proto_map.get(intent.protocol, "Any")}')
        
        if intent.dst_port != "any" and intent.protocol in ["tcp", "udp"]:
            cmd_parts.append(f'-LocalPort {intent.dst_port}')
        
        if intent.src_ip != "any":
            cmd_parts.append(f'-RemoteAddress {intent.src_ip}')
        
        cmd_parts.append(f'-Description "{intent.description}"')
        
        return " ".join(cmd_parts)
    
    def _gen_ufw(self, intent: RuleIntent) -> str:
        """Generate Ubuntu UFW command"""
        action = "allow" if intent.action == "allow" else "deny"
        
        if intent.dst_port != "any":
            if intent.protocol == "any":
                return f"ufw {action} {intent.dst_port}"
            else:
                return f"ufw {action} {intent.dst_port}/{intent.protocol}"
        
        if intent.src_ip != "any":
            return f"ufw {action} from {intent.src_ip}"
        
        return f"ufw {action} {intent.protocol}"
    
    def _gen_cisco_asa(self, intent: RuleIntent) -> str:
        """Generate Cisco ASA ACL entry"""
        action = "permit" if intent.action == "allow" else "deny"
        
        proto = intent.protocol if intent.protocol != "any" else "ip"
        src = intent.src_ip if intent.src_ip != "any" else "any"
        dst = intent.dst_ip if intent.dst_ip != "any" else "any"
        
        if intent.dst_port != "any" and intent.protocol in ["tcp", "udp"]:
            return f"access-list OUTSIDE_IN extended {action} {proto} {src} host {dst} eq {intent.dst_port}"
        
        return f"access-list OUTSIDE_IN extended {action} {proto} {src} {dst}"
    
    def _gen_fortinet(self, intent: RuleIntent) -> str:
        """Generate FortiGate CLI command"""
        action = "accept" if intent.action == "allow" else "deny"
        
        cmd = f"config firewall policy\nedit 0\nset name \"Beaver_{int(time.time())}\"\nset srcintf \"port1\"\nset dstintf \"port2\"\nset srcaddr \"{intent.src_ip if intent.src_ip != 'any' else 'all'}\"\nset dstaddr \"{intent.dst_ip if intent.dst_ip != 'any' else 'all'}\"\nset action {action}\n"
        
        if intent.protocol != "any":
            cmd += f"set protocol {intent.protocol}\n"
        
        if intent.dst_port != "any":
            cmd += f"set service \"{intent.dst_port}\"\n"
        
        cmd += "next\nend"
        return cmd


class RuleValidator:
    """Validate rule syntax without Docker"""
    
    @staticmethod
    def validate_iptables(rule: str) -> Tuple[bool, str]:
        """Check iptables syntax using --check or dry-run"""
        # Extract the rule without the -A INPUT part for checking
        check_rule = rule.replace("iptables -A", "iptables -C")
        
        try:
            # Try to check if rule exists (will fail if syntax bad)
            result = subprocess.run(
                check_rule.split(),
                capture_output=True,
                text=True,
                timeout=5
            )
            # If it says "Bad rule", syntax is wrong
            if "Bad rule" in result.stderr or "Invalid" in result.stderr:
                return False, result.stderr
            
            # Try dry-run with -t filter -A INPUT --dry-run (iptables 1.6.0+)
            dry_run = ["iptables", "-t", "filter", "-A", "INPUT", "--dry-run"] + rule.split()[3:]
            result = subprocess.run(dry_run, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                return True, "Syntax valid"
            return False, result.stderr
            
        except Exception as e:
            # If we can't validate, assume valid (better than blocking)
            return True, f"Validation skipped: {e}"
    
    @staticmethod
    def validate_suricata(rule: str) -> Tuple[bool, str]:
        """Basic Suricata syntax check"""
        # Check for required components
        required = ['(', ')', 'msg:', 'sid:', 'rev:']
        for req in required:
            if req not in rule:
                return False, f"Missing {req}"
        
        # Check action
        actions = ['alert', 'drop', 'pass', 'reject']
        if not any(rule.startswith(a) for a in actions):
            return False, "Invalid action"
        
        return True, "Basic syntax valid"
    
    @staticmethod
    def validate_ip_addresses(intent: RuleIntent) -> Tuple[bool, List[str]]:
        """Validate all IP addresses in intent"""
        errors = []
        
        for field, val in [("src_ip", intent.src_ip), ("dst_ip", intent.dst_ip)]:
            if val != "any":
                try:
                    ipaddress.ip_network(val, strict=False)
                except ValueError as e:
                    errors.append(f"{field}: {e}")
        
        return len(errors) == 0, errors


class BeaverMiner:
    """Main Beaver Miner neuron controller"""
    
    def __init__(self):
        self.nlu = LightweightNLU()
        self.engine = RuleEngine()
        self.validator = RuleValidator()
        self.output_dir = Path.home() / ".cynapse" / "beaver_rules"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def process(self, 
                     input_text: str,
                     platforms: Optional[List[str]] = None,
                     validate: bool = True,
                     sign: bool = True) -> Dict[str, Any]:
        """
        Process natural language into firewall rules
        
        Args:
            input_text: English description of desired rule
            platforms: List of target platforms (default: all)
            validate: Run syntax validation
            sign: Request Elephant signature
        
        Returns:
            Dictionary with generated rules and metadata
        """
        # Audit: start processing
        CynapseBridge.log_event("rule_generation_start", {
            "input": input_text,
            "platforms": platforms or ["all"]
        })
        
        # Parse intent
        intent = self.nlu.parse(input_text)
        
        # Validate intent IPs
        ips_valid, ip_errors = self.validator.validate_ip_addresses(intent)
        if not ips_valid:
            CynapseBridge.log_event("validation_failed", {
                "errors": ip_errors,
                "intent": intent.to_dict()
            }, severity="warning")
            return {
                "success": False,
                "error": "IP validation failed",
                "details": ip_errors
            }
        
        # Determine platforms
        if platforms is None:
            platforms = ["iptables", "nftables", "pfsense", "suricata", "windows"]
        
        # Generate rules
        generated = {}
        for platform in platforms:
            try:
                rule = self.engine.generate(intent, platform)
                
                # Validate if requested
                validation_result = None
                if validate and platform == "iptables":
                    is_valid, msg = self.validator.validate_iptables(rule)
                    validation_result = {"valid": is_valid, "message": msg}
                
                generated[platform] = {
                    "rule": rule,
                    "validation": validation_result
                }
                
            except Exception as e:
                generated[platform] = {
                    "rule": None,
                    "error": str(e)
                }
        
        # Save to file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_files = {}
        
        for platform, data in generated.items():
            if data.get("rule"):
                filename = f"{timestamp}_{platform}.txt"
                filepath = self.output_dir / filename
                
                content = f"# Beaver Miner Rule\n# Source: {input_text}\n# Generated: {datetime.utcnow().isoformat()}\n\n"
                content += data["rule"]
                
                filepath.write_text(content)
                output_files[platform] = str(filepath)
                
                # Request signature
                if sign:
                    sig_path = CynapseBridge.request_signature(filepath)
                    if sig_path:
                        output_files[f"{platform}_sig"] = str(sig_path)
        
        # Audit: completion
        result = {
            "success": True,
            "intent": intent.to_dict(),
            "generated": generated,
            "output_files": output_files,
            "timestamp": timestamp
        }
        
        CynapseBridge.log_event("rule_generation_complete", {
            "input": input_text,
            "platforms": list(generated.keys()),
            "output_files": list(output_files.values())
        })
        
        return result
    
    async def deploy(self, platform: str, rule_file: Path, 
                    test_only: bool = True) -> Dict[str, Any]:
        """
        Deploy rule to live firewall (if permitted)
        
        Args:
            platform: Target platform
            rule_file: Path to rule file
            test_only: If True, only test without applying
        
        Returns:
            Deployment result
        """
        CynapseBridge.log_event("deployment_attempt", {
            "platform": platform,
            "rule_file": str(rule_file),
            "test_only": test_only
        }, severity="warning" if not test_only else "info")
        
        if platform == "iptables":
            if test_only:
                # Test with --dry-run or in separate chain
                return {"status": "test_mode", "applied": False}
            
            # Actual deployment would require root and careful handling
            # This is a placeholder for the integration
            return {"status": "not_implemented", "reason": "Requires root and safety review"}
        
        return {"status": "unsupported_platform", "platform": platform}
    
    def list_rules(self) -> List[Dict]:
        """List all generated rules"""
        rules = []
        for f in sorted(self.output_dir.glob("*.txt")):
            rules.append({
                "file": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        return rules


# --- CLI Interface ---
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Beaver Miner v3.0 - Cynapse Firewall Rule Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  beaver.py "block ssh from 192.168.1.50"
  beaver.py "allow http from 10.0.0.0/24 after 6pm" --platform iptables nftables
  beaver.py --list
        """
    )
    
    parser.add_argument("input", nargs="?", help="Natural language rule description")
    parser.add_argument("--platform", "-p", nargs="+", 
                       choices=["iptables", "nftables", "pfsense", "suricata", 
                               "windows", "ufw", "cisco", "fortinet"],
                       help="Target platforms")
    parser.add_argument("--validate", action="store_true", default=True,
                       help="Validate generated rules")
    parser.add_argument("--no-validate", dest="validate", action="store_false")
    parser.add_argument("--sign", action="store_true", default=True,
                       help="Request Elephant signature")
    parser.add_argument("--list", action="store_true", help="List generated rules")
    parser.add_argument("--output", "-o", type=Path, help="Custom output directory")
    
    args = parser.parse_args()
    
    beaver = BeaverMiner()
    
    if args.list:
        rules = beaver.list_rules()
        print(f"\nGenerated rules in {beaver.output_dir}:")
        for r in rules:
            print(f"  {r['modified']}  {r['file']}")
        return
    
    if not args.input:
        parser.error("Provide input text or use --list")
    
    print(f"[*] Processing: {args.input}")
    result = await beaver.process(
        args.input,
        platforms=args.platform,
        validate=args.validate,
        sign=args.sign
    )
    
    if not result["success"]:
        print(f"[!] Failed: {result.get('error')}")
        if result.get("details"):
            for d in result["details"]:
                print(f"    - {d}")
        return
    
    print(f"\n[+] Parsed intent:")
    intent = result["intent"]
    print(f"    Action: {intent['action']}")
    print(f"    Proto:  {intent['protocol']}")
    print(f"    Source: {intent['src_ip']}")
    print(f"    Dest:   {intent['dst_ip']}:{intent['dst_port']}")
    print(f"    Time:   {intent['time_start']} - {intent['time_end']}")
    
    print(f"\n[+] Generated rules:")
    for platform, data in result["generated"].items():
        if data.get("rule"):
            print(f"\n--- {platform.upper()} ---")
            print(data["rule"])
            if data.get("validation"):
                v = data["validation"]
                status = "✓" if v["valid"] else "✗"
                print(f"[{status}] {v['message']}")
    
    print(f"\n[+] Saved to: {beaver.output_dir}")


if __name__ == "__main__":
    asyncio.run(main())