#!/usr/bin/env python3
"""
Meerkat v2.1 - TUI-Native Vulnerability Scanner
Outputs directly to Cynapse Synaptic Fortress TUI, zero external files
"""

import asyncio
import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, AsyncIterator, Set, Tuple, Callable
import re
import platform
from datetime import datetime


@dataclass
class SoftwareItem:
    """Discovered software component"""
    name: str
    version: str
    source: str  # 'python', 'node', 'system', 'docker'
    path: Optional[str] = None


@dataclass
class Vulnerability:
    """CVE match result"""
    cve_id: str
    cvss_score: float
    severity: str  # 'critical', 'high', 'medium', 'low'
    summary: str


@dataclass
class ScanResult:
    """Complete result for one software item"""
    software: SoftwareItem
    vulnerabilities: List[Vulnerability]
    risk_score: float


class MeerkatScanner:
    """
    Async vulnerability scanner for Cynapse TUI integration.
    All output via callbacks - no files, no HTML, pure terminal.
    """
    
    # ANSI colors matching Cynapse TUI palette
    COLORS = {
        'reset': '\033[0m',
        'critical': '\033[38;5;196m',  # Red
        'high': '\033[38;5;208m',      # Orange/Amber
        'medium': '\033[38;5;178m',    # Yellow
        'low': '\033[38;5;67m',        # Muted blue
        'clean': '\033[38;5;118m',     # Green
        'header': '\033[38;5;141m',    # Purple
        'text': '\033[38;5;255m',      # White
        'dim': '\033[38;5;245m',       # Gray
    }
    
    SYMBOLS = {
        'critical': '✗',
        'high': '⚠',
        'medium': '▲',
        'low': '●',
        'clean': '✓',
        'scanning': '∿',
    }
    
    def __init__(self, db_path: Path = None, workers: int = 10):
        self.db_path = db_path or Path(__file__).parent / "cve.db"
        self.workers = workers
        self._db_conn = None
        self._version_cache: Dict[str, str] = {}
        
    async def _get_db(self) -> sqlite3.Connection:
        """Lazy async DB connection"""
        if self._db_conn is None:
            self._db_conn = await asyncio.to_thread(sqlite3.connect, str(self.db_path))
            await asyncio.to_thread(self._db_conn.execute, "PRAGMA journal_mode=WAL")
        return self._db_conn
    
    async def close(self):
        if self._db_conn:
            await asyncio.to_thread(self._db_conn.close)
    
    # --- Inventory Methods ---
    
    async def scan_python_packages(self) -> AsyncIterator[SoftwareItem]:
        """Yield Python packages from sys.path"""
        seen: Set[Tuple[str, str]] = set()
        
        for site in sys.path:
            site_path = Path(site)
            if not site_path.exists():
                continue
            
            dist_infos = await asyncio.to_thread(list, site_path.glob("*dist-info"))
            
            for dist in dist_infos:
                parts = dist.name.replace(".dist-info", "").split("-")
                if len(parts) >= 2:
                    name = parts[0].lower()
                    version = parts[1]
                    
                    if (name, version) not in seen:
                        seen.add((name, version))
                        yield SoftwareItem(name=name, version=version, source="python")
    
    async def scan_node_modules(self, max_depth: int = 4) -> AsyncIterator[SoftwareItem]:
        """Yield Node.js packages from home directory"""
        home = Path.home()
        seen: Set[Tuple[str, str]] = set()
        
        cmd = [
            "find", str(home), "-maxdepth", str(max_depth),
            "-name", "package.json", "-type", "f",
            "2>/dev/null"
        ]
        
        try:
            proc = await asyncio.create_subprocess_shell(
                " ".join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await proc.communicate()
            
            for line in stdout.decode().splitlines():
                if not line.strip():
                    continue
                
                pkg_path = Path(line)
                
                try:
                    content = await asyncio.to_thread(pkg_path.read_text)
                    data = json.loads(content)
                    name = data.get("name", "").lower()
                    version = data.get("version", "")
                    
                    if name and version and (name, version) not in seen:
                        seen.add((name, version))
                        yield SoftwareItem(name=name, version=version, source="node")
                except:
                    continue
        except Exception:
            pass
    
    async def scan_system_binaries(self) -> AsyncIterator[SoftwareItem]:
        """Yield system apps"""
        binaries = [
            ("git", ["git", "--version"], r"git version (\d+\.\d+\.\d+)"),
            ("docker", ["docker", "--version"], r"Docker version (\d+\.\d+\.\d+)"),
            ("python", [sys.executable, "--version"], r"Python (\d+\.\d+\.\d+)"),
        ]
        
        if platform.system() == "Windows":
            binaries.extend([
                ("chrome", ["powershell", "-c", 
                    '(Get-Item "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe").VersionInfo.FileVersion'],
                    r"(\d+\.\d+\.\d+\.\d+)"),
            ])
        else:
            binaries.extend([
                ("chrome", ["google-chrome", "--version"], r"Google Chrome (\d+\.\d+\.\d+)"),
            ])
        
        for name, cmd, pattern in binaries:
            cache_key = " ".join(cmd)
            if cache_key in self._version_cache:
                yield SoftwareItem(name=name, version=self._version_cache[cache_key], source="system")
                continue
            
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                match = re.search(pattern, stdout.decode())
                
                if match:
                    version = match.group(1)
                    self._version_cache[cache_key] = version
                    yield SoftwareItem(name=name, version=version, source="system")
            except:
                continue
    
    # --- Vulnerability Lookup ---
    
    async def lookup_vulnerabilities(self, item: SoftwareItem) -> List[Vulnerability]:
        """Query SQLite for CVEs"""
        conn = await self._get_db()
        
        version_patterns = [
            item.version,
            ".".join(item.version.split(".")[:2]),
            item.version.split(".")[0],
        ]
        
        vulnerabilities = []
        
        for pattern in version_patterns:
            rows = await asyncio.to_thread(
                lambda: conn.execute(
                    """SELECT cve_id, cvss, summary FROM cve 
                       WHERE pkg = ? AND (version = ? OR version LIKE ?)
                       ORDER BY cvss DESC""",
                    (item.name, pattern, f"{pattern}%")
                ).fetchall()
            )
            
            for row in rows:
                cve_id, cvss, summary = row
                severity = self._cvss_to_severity(cvss)
                
                if not any(v.cve_id == cve_id for v in vulnerabilities):
                    vulnerabilities.append(Vulnerability(
                        cve_id=cve_id, cvss_score=cvss, severity=severity, summary=summary
                    ))
        
        return vulnerabilities
    
    def _cvss_to_severity(self, score: float) -> str:
        if score >= 9.0: return "critical"
        if score >= 7.0: return "high"
        if score >= 4.0: return "medium"
        return "low"
    
    # --- TUI-Optimized Output ---
    
    def format_line(self, item: SoftwareItem, vuln_count: int, max_cvss: float) -> str:
        """Format single scan result line for TUI"""
        if vuln_count == 0:
            symbol = self.SYMBOLS['clean']
            color = self.COLORS['clean']
            status = "clean"
        else:
            severity = self._cvss_to_severity(max_cvss)
            symbol = self.SYMBOLS[severity]
            color = self.COLORS[severity]
            status = f"{vuln_count} CVEs"
        
        source_icon = {
            'python': '🐍',
            'node': '⬢',
            'system': '⚙',
            'docker': '🐳'
        }.get(item.source, '•')
        
        return f"{color}{symbol}{self.COLORS['reset']} {source_icon} {item.name:20} {item.version:15} {color}{status}{self.COLORS['reset']}"
    
    def format_detail(self, vuln: Vulnerability, indent: str = "    ") -> str:
        """Format vulnerability detail line"""
        color = self.COLORS[vuln.severity]
        return f"{indent}{color}{self.SYMBOLS[vuln.severity]}{self.COLORS['reset']} {vuln.cve_id} (CVSS: {color}{vuln.cvss_score:.1f}{self.COLORS['reset']}) {self.COLORS['dim']}{vuln.summary[:60]}...{self.COLORS['reset']}"
    
    # --- Main Scan ---
    
    async def scan(
        self,
        line_callback: Callable[[str], None],
        detail_callback: Optional[Callable[[str], None]] = None,
        summary_callback: Optional[Callable[[Dict], None]] = None
    ) -> List[ScanResult]:
        """
        Run scan with real-time TUI callbacks.
        
        Args:
            line_callback: Called for each item (main list)
            detail_callback: Called for vulnerability details (expanded view)
            summary_callback: Called with final stats
        """
        # Header
        line_callback(f"{self.COLORS['header']}╔══════════════════════════════════════════════════════════════╗{self.COLORS['reset']}")
        line_callback(f"{self.COLORS['header']}║{self.COLORS['reset']}           🦡 MEERKAT SECURITY AUDIT                           {self.COLORS['header']}║{self.COLORS['reset']}")
        line_callback(f"{self.COLORS['header']}╚══════════════════════════════════════════════════════════════╝{self.COLORS['reset']}")
        line_callback("")
        
        # Phase 1: Inventory
        line_callback(f"{self.COLORS['dim']}Scanning system...{self.COLORS['reset']}")
        
        all_items: List[SoftwareItem] = []
        
        inventory_tasks = [
            self._collect(self.scan_python_packages()),
            self._collect(self.scan_node_modules()),
            self._collect(self.scan_system_binaries()),
        ]
        
        results = await asyncio.gather(*inventory_tasks)
        for result_list in results:
            all_items.extend(result_list)
        
        line_callback(f"{self.COLORS['dim']}Found {len(all_items)} items. Checking CVE database...{self.COLORS['reset']}")
        line_callback("")
        
        # Phase 2: Vulnerability check with progress
        semaphore = asyncio.Semaphore(self.workers)
        scan_results = []
        
        async def check_item(item: SoftwareItem) -> ScanResult:
            async with semaphore:
                vulns = await self.lookup_vulnerabilities(item)
                risk = max((v.cvss_score for v in vulns), default=0.0)
                
                # Send formatted line to TUI
                line = self.format_line(item, len(vulns), risk)
                line_callback(line)
                
                # Send details if vulnerabilities found
                if vulns and detail_callback:
                    for vuln in vulns[:3]:  # Top 3 only
                        detail_callback(self.format_detail(vuln))
                
                return ScanResult(software=item, vulnerabilities=vulns, risk_score=risk)
        
        tasks = [check_item(item) for item in all_items]
        scan_results = await asyncio.gather(*tasks)
        
        # Sort by risk
        scan_results.sort(key=lambda x: x.risk_score, reverse=True)
        
        # Summary
        critical = sum(1 for r in scan_results if r.risk_score >= 9.0)
        high = sum(1 for r in scan_results if 7.0 <= r.risk_score < 9.0)
        medium = sum(1 for r in scan_results if 4.0 <= r.risk_score < 7.0)
        total_vulns = sum(len(r.vulnerabilities) for r in scan_results)
        
        summary = {
            'total_items': len(scan_results),
            'critical': critical,
            'high': high,
            'medium': medium,
            'total_vulns': total_vulns,
            'clean': len(scan_results) - sum(1 for r in scan_results if r.vulnerabilities)
        }
        
        line_callback("")
        line_callback(f"{self.COLORS['header']}═══════════════════════════════════════════════════════════════{self.COLORS['reset']}")
        
        if summary_callback:
            summary_callback(summary)
        else:
            # Default summary display
            status_color = self.COLORS['critical'] if critical > 0 else self.COLORS['high'] if high > 0 else self.COLORS['clean']
            status_symbol = '✗' if critical > 0 or high > 0 else '✓'
            
            line_callback(f"{status_color}{status_symbol}{self.COLORS['reset']} SCAN COMPLETE")
            line_callback(f"  Items scanned: {summary['total_items']}")
            line_callback(f"  {self.COLORS['critical']}Critical: {summary['critical']}{self.COLORS['reset']}  {self.COLORS['high']}High: {summary['high']}{self.COLORS['reset']}  {self.COLORS['medium']}Medium: {summary['medium']}{self.COLORS['reset']}")
            line_callback(f"  {self.COLORS['clean']}Clean: {summary['clean']}{self.COLORS['reset']}")
            
            if critical > 0:
                line_callback(f"\n{self.COLORS['critical']}🔴 IMMEDIATE ACTION REQUIRED{self.COLORS['reset']}")
        
        return scan_results
    
    async def _collect(self, async_gen) -> list:
        """Collect async generator to list"""
        return [item async for item in async_gen]


# --- Direct TUI Integration ---
async def run_in_tui(rich_log_callback: Callable[[str], None]):
    """
    Entry point for Cynapse TUI integration.
    Passes formatted lines directly to RichLog widget.
    """
    scanner = MeerkatScanner(workers=10)
    
    try:
        await scanner.scan(
            line_callback=rich_log_callback,
            detail_callback=lambda msg: rich_log_callback(f"  {msg}")
        )
    finally:
        await scanner.close()


# --- CLI Standalone ---
async def main():
    """Standalone CLI mode (no TUI)"""
    scanner = MeerkatScanner(workers=10)
    
    try:
        await scanner.scan(line_callback=print)
    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())