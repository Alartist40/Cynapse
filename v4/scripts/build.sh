#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
GO_BIN="$PROJECT_DIR/.local/go/bin/go"

# Fallback to system go if local not found
if [ ! -f "$GO_BIN" ]; then
    GO_BIN="$(which go 2>/dev/null || true)"
fi

if [ -z "$GO_BIN" ]; then
    echo "❌ Go not found. Install Go first."
    exit 1
fi

VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "4.0.0-dev")
LDFLAGS="-X main.Version=$VERSION -s -w"

echo "🔨 Building Cynapse v$VERSION..."
cd "$PROJECT_DIR"

mkdir -p dist

"$GO_BIN" build -ldflags "$LDFLAGS" -o dist/cynapse ./cmd/cynapse

SIZE=$(du -h dist/cynapse | cut -f1)
echo "✅ Built: dist/cynapse ($SIZE)"
echo ""
echo "Run with:"
echo "  ./dist/cynapse           # Launch TUI"
echo "  ./dist/cynapse --health  # Health check"
echo "  ./dist/cynapse --help    # Usage"
