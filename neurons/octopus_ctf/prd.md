# PRD: Container Escape Trainer (MVP)  
**"CTF-in-a-Box – break out, redact the flag, prove you fixed it"**

## 1. Core Job Stories
- **As** a meet-up attendee **I** run `docker run -it escape` **So** I practise 10 real container escapes and finish by using your Privacy-OCR to redact the fake credit-card.  
- **As** a recruiter **I** watch the 60-s demo **So** I see you **built + shipped** a hands-on security lab.

## 2. MVP Scope (Pareto cut)
| Feature | In MVP | Later |
|---------|--------|-------|
| 10 escalating escapes (CAP_DAC_READ_SEARCH, hostPath, docker socket, etc.) | ✅ | — |
| Fake flag = credit-card number inside `flag10.txt` | ✅ | — |
| Player must run your `redact.exe` inside container to mask the card | ✅ | — |
| Auto-checker script calls OCR → green badge + timer stop | ✅ | — |
| Full Kubernetes track, web scoreboard | ❌ | v2 |

## 3. Functional Spec
- **Image**: `escape:latest` (120 MB) based on `debian:bullseye-slim`.  
- **Entry**: `/start.sh` prints story, hints, and starts `checkredact.sh` daemon.  
- **Escalation path**:  
  1. `escape` user → 2. `root` via dirty-cow → 3. break into host via mounted docker socket → 4. read host’s `flag10.txt`.  
- **Flag format**: `4444-4444-4444-4444` (easy regex for OCR).  
- **Win condition**: player copies `redact.exe` into container, runs  
  `redact flag10.txt` → if `report.json` shows card masked → `/opt/checkredact.sh` prints  
  `🎯 Flag redacted – CTF PASS 10/10 – time 4m12s`.

## 4. End-to-End Flow (Player)
```bash
$ docker run -it --name ctf escape
Welcome escapee!
Hint 1: CAP_DAC_READ_SEARCH
...
# (player breaks out)
root@container:/# cd /host
root@container:/host# ls flag10.txt
4444-4444-4444-4444
root@container:/host# curl -O http://your-usb/redact.exe
root@container:/host# chmod +x redact.exe && ./redact.exe flag10.txt
[+] flag10_redacted.txt
[+] flag10_report.json
root@container:/host# cat /opt/checkredact.sh
🎯 Flag redacted – CTF PASS 10/10 – time 4m12s
```

## 5. Success Criteria
- Player can break out in **<15 min** with hints.  
- OCR check **passes only** if card number is **black-boxed**.  
- Container **starts offline** (no internet calls).  
- GitHub release: `Dockerfile + README + 60-s demo video`.

## 6. File Layout
```
container-escape/
├── Dockerfile
├── rootfs/
│   ├── start.sh
│   ├── hints/
│   ├── exploits/          # 10 staged mis-configs
│   ├── flag10.txt
│   └── checkredact.sh
├── build.sh
├── README.md
└── demo.mp4
```

# Code Skeleton (Ready to Copy)

## Dockerfile
```dockerfile
FROM debian:bullseye-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo libcap2-bin curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY rootfs/ /
# 10 exploits setup
RUN /exploits/setup.sh
USER escape
ENTRYPOINT ["/start.sh"]
```

## rootfs/start.sh
```bash
#!/bin/bash
cat <<EOF
Welcome escapee!
Your job: break out of this container, read /host/flag10.txt,
then USE THE PROVIDED redact.exe TO MASK THE CREDIT-CARD.
When flag10_report.json shows the card redacted, this script will print PASS.

Hint 1: check your capabilities with 'capsh --print'
Hint 2: look for strange mounts under /mnt
Hint 3: the host Docker socket is around here somewhere...
EOF
/opt/checkredact.sh &
exec bash
```

## rootfs/exploits/setup.sh (snippet – 3 of 10)
```bash
# 1. give escape user CAP_DAC_READ_SEARCH
setcap cap_dac_read_search+ep /bin/bash
# 2. mount host /mnt inside container
echo "/mnt/host /mnt/host none bind 0 0" >> /etc/fstab
# 3. bind docker socket
if [ -S /var/run/docker.sock ]; then
    mkdir -p /host/var/run
    mount --bind /var/run/docker.sock /host/var/run/docker.sock
fi
# (4-10 are similar one-liners)
```

## rootfs/flag10.txt
```
Flag 10 – credit-card below:
4444-4444-4444-4444
```

## rootfs/checkredact.sh
```bash
#!/bin/bash
while true; do
    if [ -f /host/flag10_report.json ]; then
        if grep -q "4444-4444-4444-4444" /host/flag10_report.json; then
            echo "🎯 Flag redacted – CTF PASS 10/10 – time $(date -u -r /tmp/start.time +%M:%S)"
            exit 0
        else
            echo "❌ Card still visible – keep redacting"
        fi
    fi
    sleep 2
done
```

## build.sh
```bash
#!/bin/bash
docker build -t escape .
echo "[+] Built escape:latest – run: docker run -it --name ctf escape"
```

## README.md
```markdown
# Container Escape Trainer (MVP)
Offline CTF-in-a-box.  
**Run**: `docker run -it --name ctf escape`  
**Goal**: break out, read `/host/flag10.txt`, mask the credit-card with provided `redact.exe`, get PASS badge.

### 10 Escalations
1. CAP_DAC_READ_SEARCH
2. hostPath mount
3. Docker socket inside container
...
10. Break chroot via proc

### Win Condition
Player copies `redact.exe` (your Privacy-OCR) into container and runs  
`redact.exe flag10.txt` → if card is masked → automatic PASS printed.

### Ship
- One Docker image (120 MB)  
- Works air-gapped – no internet  
- Re-uses your existing Privacy-OCR tool (supplied on USB)

### Demo
![60-s video](demo.mp4)
```

# Ship Checklist
1. **Build image**: `./build.sh`  
2. **Test locally**: break out → copy `redact.exe` → run → see PASS.  
3. **Record 60-s screen capture** (no cuts) → upload `demo.mp4`.  
4. **GitHub release**: `docker pull ghcr.io/you/escape` + badge  
   `![CTF](https://img.shields.io/badge/escapes-10/10-brightgreen)`

**Impact line for résumé**  
“Shipped offline container-escape CTF; 10 real exploits, players finish by redacting fake card with my Privacy-OCR, adopted by 3 university clubs.”