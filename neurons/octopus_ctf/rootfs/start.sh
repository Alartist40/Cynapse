#!/bin/bash

# Record start time for timer
date +%s > /tmp/start.time

# Display welcome banner
cat <<'EOF'
╔══════════════════════════════════════════════════════════════════╗
║           CONTAINER ESCAPE TRAINER - CTF Challenge               ║
║                    "Break Out or Break Down"                     ║
╚══════════════════════════════════════════════════════════════════╝

Welcome, escapee! 🔓

Your mission, should you choose to accept it:
  1. Break out of this container using ANY of the 10 escape paths
  2. Navigate to the host filesystem and locate /host/flag10.txt
  3. Read the credit card number inside (this is fake data for training)
  4. Use the provided redact.exe tool to MASK the credit card
  5. When flag10_report.json shows the card is redacted, you WIN!

═══════════════════════════════════════════════════════════════════

🎯 ESCAPE PATHS - 10 Ways Out:

  1. CAP_DAC_READ_SEARCH - Bypass file read permissions
  2. CAP_SYS_ADMIN - Mount/unmount operations enabled
  3. Privileged Container - Full root capabilities
  4. Host Path Mount - Host filesystem accessible at /host
  5. Docker Socket - Control Docker from inside container
  6. PID Namespace Sharing - See host processes
  7. Writable Cgroup - Control group manipulation
  8. Procfs Escape - Break out via /proc filesystem
  9. Weak Seccomp - Reduced syscall filtering
 10. No AppArmor - Mandatory access control disabled

═══════════════════════════════════════════════════════════════════

💡 HINTS:

  → Check your capabilities: capsh --print
  → Look for mounted filesystems: mount | grep host
  → Check for Docker socket: ls -la /var/run/docker.sock
  → Explore /host directory if it exists
  → Review hints in /hints/ directory
  → Check running processes: ps aux
  → Examine cgroup paths: cat /proc/1/cgroup

═══════════════════════════════════════════════════════════════════

📍 WIN CONDITION:

  The flag is at: /host/flag10.txt (after you escape)
  
  Once you find it, run:
    redact.exe /host/flag10.txt
  
  This creates flag10_report.json - when the credit card is masked,
  the auto-checker will print: 🎯 CTF PASS 10/10
  
═══════════════════════════════════════════════════════════════════

⏱️  Timer started! The checkredact.sh daemon is monitoring...
    Good luck, hacker! 🚀

EOF

# Start the redaction checker daemon in background
/opt/checkredact.sh &

# Drop into interactive bash shell
exec bash
