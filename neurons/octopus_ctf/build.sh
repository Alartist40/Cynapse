#!/bin/bash
# Container Escape Trainer - Build Script

set -e

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║        Building Container Escape Trainer Docker Image            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Build the Docker image
echo "[*] Building Docker image 'escape:latest'..."
docker build -t escape:latest .

if [ $? -eq 0 ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║                     BUILD SUCCESSFUL! ✅                          ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Image: escape:latest"
    echo "Size: $(docker images escape:latest --format '{{.Size}}')"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    echo "🚀 Quick Start:"
    echo ""
    echo "  To run the CTF challenge:"
    echo "    ./run.sh"
    echo ""
    echo "  Or manually:"
    echo "    docker run -it --rm --privileged \\"
    echo "      -v /var/run/docker.sock:/var/run/docker.sock \\"
    echo "      -v /:/host \\"
    echo "      --name ctf escape:latest"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
else
    echo ""
    echo "❌ Build failed! Please check the error messages above."
    exit 1
fi
