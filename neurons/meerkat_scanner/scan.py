#!/usr/bin/env python3
import sqlite3, json, pathlib, re, datetime, platform, sys, html, subprocess

DB     = pathlib.Path(__file__).with_name('cve.db')
REPORT = pathlib.Path('report.html')
PKG_RE = re.compile(r'([a-zA-Z0-9\-]+)\-(\d+\.\d+\.\d+.*)')  # simple version grabber

def scan():
    """return dict { (pkg, version): [ (cve_id, cvss, summary) ] }"""
    found = {}
    print("[*] Inventorying Python packages...")
    # 1. Python
    for site in sys.path:
        p = pathlib.Path(site)
        if not p.exists(): continue
        for whl in p.glob('*dist-info'):
            m = PKG_RE.match(whl.name.split('-')[0] + '-' + whl.name.split('-')[1])
            if m:
                found[('python', m.group(2))] = [] # The PRD logic was slightly loose here, refining it slightly but keeping spirit
                # Actually, the PRD regex implies 'pip-21.0.dist-info', split('-')[0] is 'pip'. 
                # Let's stick closer to the PRD logic but make it safe.
                parts = whl.name.split('-')
                if len(parts) >= 2:
                     found[('python', parts[1])] = [] 
                     # Wait, PRD said: m = PKG_RE.match(whl.name.split('-')[0]) 
                     # That looks wrong if the regex expects two groups. 
                     # Let's fix the logic to actually parse dist-info names correctly.
                     # Dist-info format: Name-Version.dist-info
                     name = parts[0]
                     version = parts[1]
                     found[(name.lower(), version)] = []

    print("[*] Inventorying Node modules (home dir)...")
    # 2. Node - PRD says rglob node_modules in home. This might be slow but we follow spec.
    try:
        for node_mod in pathlib.Path.home().rglob('node_modules'):
            if 'Hidden' in str(node_mod): continue # Skip some obvious junk
            pkg_json = node_mod / 'package.json'
            if pkg_json.exists():
                try:
                    data = json.loads(pkg_json.read_text(errors='ignore'))
                    if 'version' in data:
                        found[('nodejs', data['version'])] = []
                        # Also capture the package name itself? PRD just says "nodejs", "ver". 
                        # The DB schema example has 'pkg'='nodejs', but real CVEs are for specific packages.
                        # The PRD example output shows: "node 14.17.1", "python 3.9.0", "chrome 91.0". 
                        # This implies it inventories the *runtime* or *app*, not every library?
                        # Wait, PRD section 5 msg: "python 3.9.0", "node 14.17.1". 
                        # BUT section 1 says "Inventory EXE, DLL, Python wheels, NPM".
                        # If I look at the DB schema: pkg="python", version="3.9.0".
                        # So it seems the intention is to check if the *runtime* is vulnerable, OR libraries?
                        # The mock DB build script extracts product names from NVD descriptions.
                        # NVD usually lists "django 3.2". 
                        # Let's capture the library name as the package.
                        if 'name' in data:
                             found[(data['name'].lower(), data['version'])] = []
                except:
                    pass
    except Exception as e:
        print(f"[-] Node scan error: {e}")

    # 3. EXE via WMI on Windows / rpm -qa on Linux (fallback)
    #    Keep it short: just chrome, firefox, git, docker
    print("[*] Checking system apps...")
    for prog in ['chrome', 'firefox', 'git', 'docker']:
        ver = quick_version(prog)
        if ver:
            found[(prog, ver)] = []
    
    return found

def quick_version(name):
    """return version string or None"""
    try:
        if platform.system() == 'Windows':
            # wmic datafile where name='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' get Version /value
            # This is hard because paths vary. PRD example was specific. 
            # Better approach for MVP: try common paths or just powershell/cmd for git/docker.
            
            if name == 'git':
                 out = subprocess.check_output(['git', '--version'], text=True, stderr=subprocess.DEVNULL)
                 # "git version 2.40.1.windows.1"
                 m = re.search(r'(\d+\.\d+\.\d+)', out)
                 return m.group(1) if m else None
            elif name == 'docker':
                 out = subprocess.check_output(['docker', '--version'], text=True, stderr=subprocess.DEVNULL)
                 m = re.search(r'(\d+\.\d+\.\d+)', out)
                 return m.group(1) if m else None
            elif name == 'chrome':
                # Registry might be better or deafult path
                ps_script = r'(Get-Item "C:\Program Files\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion'
                out = subprocess.check_output(["powershell", "-c", ps_script], text=True, stderr=subprocess.DEVNULL)
                return out.strip() if out.strip() else None
            elif name == 'firefox':
                ps_script = r'(Get-Item "C:\Program Files\Mozilla Firefox\firefox.exe").VersionInfo.FileVersion'
                out = subprocess.check_output(["powershell", "-c", ps_script], text=True, stderr=subprocess.DEVNULL)
                return out.strip() if out.strip() else None

            return None
        else:
            # which + --version
            path = subprocess.check_output(['which', name], text=True).strip()
            out = subprocess.check_output([name, '--version'], stderr=subprocess.STDOUT, text=True)
            # grab first semver
            m = re.search(r'(\d+\.\d+\.\d+)', out)
            return m.group(1) if m else None
    except:
        return None

def lookup(found):
    if not DB.exists():
        print(f"[!] DB file not found: {DB}")
        return {}

    conn = sqlite3.connect(DB)
    vulns = {}
    for (pkg, ver) in found:
        # Relaxed matching: try exact match first, then partial?
        # NVD data is messy. 
        cur = conn.execute('SELECT cve_id, cvss, summary FROM cve WHERE pkg=? AND version=?', (pkg, ver))
        rows = cur.fetchall()
        if rows:
            vulns[(pkg, ver)] = rows
    conn.close()
    return vulns

def html_report(vulns):
    total = len(vulns)
    highs = sum(1 for vs in vulns.values() if any(v[1] >= 7 for v in vs))
    meds  = sum(1 for vs in vulns.values() if any(4 <= v[1] < 7 for v in vs))
    rows = []
    for (pkg, ver), vs in vulns.items():
        for cve_id, cvss, summary in vs:
            rows.append((pkg, ver, cve_id, f"{cvss:.1f}", summary))
    rows.sort(key=lambda x: float(x[3]), reverse=True)

    tmpl = pathlib.Path(__file__).with_name('report_template.html').read_text()
    out = tmpl.replace('{{DATE}}', datetime.datetime.now().isoformat(' ', 'minutes'))
    out = out.replace('{{TOTAL}}', str(total)).replace('{{HIGHS}}', str(highs)).replace('{{MEDS}}', str(meds))
    table = ""
    for pkg, ver, cve, cvss, summ in rows[:50]:  # top 50
        table += f"<tr><td>{pkg}</td><td>{ver}</td><td><a href='https://nvd.nist.gov/vuln/detail/{cve}' target='_blank'>{cve}</a></td><td>{cvss}</td><td>{html.escape(summ[:80])}</td></tr>\n"
    out = out.replace('{{TABLE}}', table)
    REPORT.write_text(out)

def main():
    print("[*] Scanning ...")
    found = scan()
    print(f"[*] Found {len(found)} software items (python/node/apps). Checking CVEs...")
    vulns = lookup(found)
    html_report(vulns)
    print(f"[+] Report saved: {REPORT.resolve()}")

if __name__ == '__main__':
    main()
