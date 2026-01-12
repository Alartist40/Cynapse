#!/bin/bash
# Container Escape Trainer - Run Script
# Starts the CTF challenge with appropriate Docker flags

set -e

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Starting Container Escape Trainer CTF                   ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "[*] Launching CTF container with escape configurations..."
echo ""

# Run the container with necessary flags for escapes to work
docker run -it --rm \
    --privileged \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /:/host \
    --name ctf \
    escape:latest

echo ""
echo "[*] CTF container exited."
