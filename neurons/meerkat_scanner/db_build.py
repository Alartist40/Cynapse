#!/usr/bin/env python3
import json, gzip, sqlite3, pathlib, urllib.request, re, subprocess

DB_FILE = pathlib.Path(__file__).parent / 'cve.db'
NVD_FEED = 'https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-recent.json.gz'

def fetch():
    print(f"[*] Fetching {NVD_FEED} ...")
    try:
        req = urllib.request.Request(NVD_FEED, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            return json.loads(gzip.decompress(resp.read()))
    except Exception as e:
        print(f"[!] urllib failed: {e}. Trying curl...")
        try:
            # Try curl
            subprocess.check_call(['curl', '-L', '-o', 'nvd.json.gz', NVD_FEED])
            with gzip.open('nvd.json.gz', 'rb') as f:
                data = json.load(f)
            pathlib.Path('nvd.json.gz').unlink()
            return data
        except Exception as e2:
            print(f"[!] curl failed too: {e2}")
            raise e2

def build():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('CREATE TABLE IF NOT EXISTS cve(pkg TEXT, version TEXT, cve_id TEXT, cvss REAL, summary TEXT)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_pkg_ver ON cve(pkg, version)')
    
    data = None
    try:
        data = fetch()
    except Exception as e:
        print(f"[!] Fetch failed: {e}")
        print("[*] Switching to MOCK DATA mode for MVP demonstration.")
        # Insert mock data matching PRD examples and some common libs
        mock_cves = [
            ('python', '3.9.0', 'CVE-2021-1234', 9.8, 'Mock critical vulnerability in Python 3.9.0'),
            ('nodejs', '14.17.1', 'CVE-2021-3918', 8.2, 'Mock high vulnerability in Node.js'),
            ('chrome', '91.0', 'CVE-2021-3055', 7.9, 'Mock vulnerability in Chrome'),
            ('git', '2.40.1', 'CVE-2023-1234', 5.5, 'Mock medium vulnerability in Git'),
            ('urllib3', '1.26.4', 'CVE-2021-33503', 4.3, 'Mock Denial of Service in urllib3'),
        ]
        count = 0
        for pkg, ver, cve, cvss, desc in mock_cves:
             conn.execute('INSERT INTO cve VALUES (?,?,?,?,?)', (pkg, ver, cve, cvss, desc))
             count += 1
        conn.commit()
        conn.close()
        print(f'[+] cve.db rebuilt with {count} MOCK entries due to download failure.')
        return

    print("[*] Parsing and inserting data ...")
    count = 0
    if data:
        for item in data['CVE_Items']:
            cve_id = item['cve']['CVE_data_meta']['ID']
            desc_data = item['cve']['description']['description_data']
            desc = desc_data[0]['value'] if desc_data else "No description"
            
            if 'baseMetricV3' not in item['impact']:
                continue
                
            cvss = item['impact']['baseMetricV3']['cvssV3']['baseScore']
            
            # crude extraction of product/version from description
            for match in re.finditer(r'([a-zA-Z][a-zA-Z0-9\-]+)\s+versions?\s+([\d\.]+)', desc):
                pkg, ver = match.group(1).lower(), match.group(2)
                conn.execute('INSERT INTO cve VALUES (?,?,?,?,?)', (pkg, ver, cve_id, cvss, desc[:200]))
                count += 1
            
    conn.commit()
    conn.close()
    print(f'[+] cve.db rebuilt with {count} entries at {DB_FILE}')

if __name__ == '__main__':
    build()
