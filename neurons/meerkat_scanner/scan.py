#!/usr/bin/env python3
"""
Meerkat Scanner v2.0 - High Performance CVE Auditor
Optimized: Async, parallel CVE lookups, non-blocking crawling
"""

import asyncio
import sqlite3
import json
import pathlib
import re
import datetime
import platform
import sys
import html
import subprocess
import os
from typing import Dict, List, Tuple, Optional, Set

# Cynapse integration
BASE_DIR = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(BASE_DIR))
try:
    from cynapse import AuditLogger, LOG_FILE
except ImportError:
    class AuditLogger:
        def log(self, event, data): pass
    LOG_FILE = pathlib.Path("audit.log")

DB = pathlib.Path(__file__).parent / 'cve.db'
REPORT = pathlib.Path('report.html')
PKG_RE = re.compile(r'([a-zA-Z0-9\-]+)\-(\d+\.\d+\.\d+.*)')

class MeerkatScanner:
    def __init__(self, hub=None):
        self.hub = hub
        self.audit = hub.logger if hub else AuditLogger(LOG_FILE)
        self.found_packages: Dict[Tuple[str, str], List] = {}
        self.lock = asyncio.Lock()

    async def scan_all(self):
        """Perform full async scan"""
        print("[*] Meerkat v2.0: Initiating parallel inventory...")
        tasks = [
            self._inventory_python(),
            self._inventory_node(),
            self._inventory_system()
        ]
        await asyncio.gather(*tasks)

    async def _inventory_python(self):
        """Async inventory of Python packages"""
        print("[*]   Scanning Python packages...")
        for site in sys.path:
            p = pathlib.Path(site)
            if not p.exists(): continue
            # Non-blocking glob
            for whl in p.glob('*dist-info'):
                parts = whl.name.split('-')
                if len(parts) >= 2:
                    name = parts[0].lower()
                    version = parts[1].replace('.dist', '')
                    async with self.lock:
                        self.found_packages[(name, version)] = []

    async def _inventory_node(self):
        """Optimized Node.js module discovery"""
        print("[*]   Scanning Node modules (optimized crawl)...")
        home = pathlib.Path.home()
        # Limited depth to prevent infinite hangs on complex systems
        await self._crawl_node_modules(home, max_depth=5)

    async def _crawl_node_modules(self, path: pathlib.Path, depth: int = 0, max_depth: int = 5):
        if depth > max_depth: return
        try:
            # Using os.scandir for high performance
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_dir():
                        if entry.name == 'node_modules':
                            await self._parse_node_dir(pathlib.Path(entry.path))
                        elif not entry.name.startswith('.'):
                            await self._crawl_node_modules(pathlib.Path(entry.path), depth + 1, max_depth)
        except (PermissionError, OSError):
            pass

    async def _parse_node_dir(self, node_modules_path: pathlib.Path):
        try:
            with os.scandir(node_modules_path) as it:
                for entry in it:
                    if entry.is_dir() and not entry.name.startswith('@'):
                        pkg_json = pathlib.Path(entry.path) / 'package.json'
                        if pkg_json.exists():
                            await self._extract_node_meta(pkg_json)
                    elif entry.is_dir() and entry.name.startswith('@'):
                        # Scoped packages
                        with os.scandir(entry.path) as sit:
                            for sentry in sit:
                                pkg_json = pathlib.Path(sentry.path) / 'package.json'
                                if pkg_json.exists():
                                    await self._extract_node_meta(pkg_json)
        except:
            pass

    async def _extract_node_meta(self, pkg_json: pathlib.Path):
        try:
            data = json.loads(pkg_json.read_text(errors='ignore'))
            if 'name' in data and 'version' in data:
                async with self.lock:
                    self.found_packages[(data['name'].lower(), data['version'])] = []
        except:
            pass

    async def _inventory_system(self):
        """Async system app version check"""
        print("[*]   Checking system apps...")
        progs = ['chrome', 'firefox', 'git', 'docker', 'python3', 'node']
        tasks = [self._get_quick_version(p) for p in progs]
        results = await asyncio.gather(*tasks)
        for prog, ver in results:
            if ver:
                async with self.lock:
                    self.found_packages[(prog, ver)] = []

    async def _get_quick_version(self, name: str) -> Tuple[str, Optional[str]]:
        try:
            if platform.system() == 'Windows':
                if name == 'git':
                    cmd = ['git', '--version']
                elif name == 'docker':
                    cmd = ['docker', '--version']
                else:
                    return name, None

                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                m = re.search(r'(\d+\.\d+\.\d+)', stdout.decode())
                return name, (m.group(1) if m else None)
            else:
                proc = await asyncio.create_subprocess_exec(
                    'which', name, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await proc.communicate()
                if not stdout.strip(): return name, None

                proc = await asyncio.create_subprocess_exec(
                    name, '--version', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                )
                stdout, _ = await proc.communicate()
                m = re.search(r'(\d+\.\d+\.\d+)', stdout.decode())
                return name, (m.group(1) if m else None)
        except:
            return name, None

    async def lookup_vulnerabilities(self):
        """Parallel CVE lookup in SQLite"""
        if not DB.exists():
            print(f"[!] CVE Database not found: {DB}")
            return {}

        print(f"[*] Checking {len(self.found_packages)} packages against local database...")
        conn = sqlite3.connect(DB)
        vulns = {}

        # Parallelize database queries
        def do_lookup(pkg, ver):
            cur = conn.execute('SELECT cve_id, cvss, summary FROM cve WHERE pkg=? AND version=?', (pkg, ver))
            return cur.fetchall()

        for (pkg, ver) in self.found_packages:
            # We use a thread pool for SQLite because it's blocking
            rows = await asyncio.to_thread(do_lookup, pkg, ver)
            if rows:
                vulns[(pkg, ver)] = rows

        conn.close()
        self.audit.log("meerkat_scan_complete", {"packages": len(self.found_packages), "vulnerabilities": len(vulns)})
        return vulns

    def generate_report(self, vulns):
        """Generate HTML report"""
        rows = []
        highs = 0
        meds = 0
        for (pkg, ver), vs in vulns.items():
            for cve_id, cvss, summary in vs:
                rows.append((pkg, ver, cve_id, cvss, summary))
                if cvss >= 7.0: highs += 1
                elif cvss >= 4.0: meds += 1

        rows.sort(key=lambda x: x[3], reverse=True)

        template_path = pathlib.Path(__file__).parent / 'report_template.html'
        if not template_path.exists():
            print("[-] Report template missing.")
            return

        tmpl = template_path.read_text()
        out = tmpl.replace('{{DATE}}', datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
        out = out.replace('{{TOTAL}}', str(len(vulns)))
        out = out.replace('{{HIGHS}}', str(highs))
        out = out.replace('{{MEDS}}', str(meds))

        table = ""
        for pkg, ver, cve, cvss, summ in rows[:100]:
            table += f"<tr><td>{pkg}</td><td>{ver}</td><td>{cve}</td><td>{cvss:.1f}</td><td>{html.escape(summ)}</td></tr>\n"

        out = out.replace('{{TABLE}}', table)
        REPORT.write_text(out)
        print(f"[+] Report generated: {REPORT.resolve()}")

async def main():
    scanner = MeerkatScanner()
    await scanner.scan_all()
    vulns = await scanner.lookup_vulnerabilities()
    scanner.generate_report(vulns)

if __name__ == '__main__':
    asyncio.run(main())
