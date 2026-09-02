#!/bin/sh
# Cynapse installer — builds from source and installs to PATH.
# Usage: curl -fsSL https://raw.githubusercontent.com/.../install.sh | sh
# Or:    ./install.sh
set -eu

red="$( (/usr/bin/tput bold || :; /usr/bin/tput setaf 1 || :) 2>&-)"
plain="$( (/usr/bin/tput sgr0 || :) 2>&-)"
status() { echo ">>> $*" >&2; }
error()  { echo "${red}ERROR:${plain} $*"; exit 1; }

require() {
    local MISSING=''
    for TOOL in $*; do
        if ! command -v "$TOOL" >/dev/null 2>&1; then
            MISSING="$MISSING $TOOL"
        fi
    done
    echo "$MISSING"
}

OS="$(uname -s)"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64) ARCH="x86_64" ;;
    aarch64|arm64) ARCH="aarch64" ;;
    *) error "Unsupported architecture: $ARCH" ;;
esac

status "Detected: $OS $ARCH"

# ── Dependency check ──────────────────────────────────────────────
NEEDS=$(require curl git cmake gcc g++ make)
if [ -n "$NEEDS" ]; then
    status "Installing build dependencies..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq curl git cmake gcc g++ make pkg-config
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y curl git cmake gcc-c++ make pkg-config
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm curl git cmake gcc make pkg-config
    elif command -v brew >/dev/null 2>&1; then
        brew install curl git cmake
    else
        error "Cannot auto-install dependencies. Please install: curl git cmake gcc g++ make"
    fi
fi

# ── Rust toolchain ────────────────────────────────────────────────
if ! command -v cargo >/dev/null 2>&1; then
    status "Installing Rust toolchain..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    . "$HOME/.cargo/env"
fi

status "Rust: $(rustc --version)"

# ── Clone or find source ──────────────────────────────────────────
CYNAPSE_DIR="${CYNAPSE_DIR:-}"
if [ -z "$CYNAPSE_DIR" ] || [ ! -d "$CYNAPSE_DIR" ]; then
    # Check if we're already inside the repo
    if [ -f "./Cargo.toml" ] && grep -q "cynapse" ./Cargo.toml 2>/dev/null; then
        CYNAPSE_DIR="$(pwd)"
    else
        CYNAPSE_DIR="$HOME/.local/src/cynapse"
        if [ ! -d "$CYNAPSE_DIR" ]; then
            status "Cloning cynapse source..."
            git clone --depth 1 https://github.com/AstralCraf/cynapse.git "$CYNAPSE_DIR"
        fi
    fi
fi

status "Source: $CYNAPSE_DIR"

# ── Build llama.cpp (static) ─────────────────────────────────────
LLAMA_DIR="$CYNAPSE_DIR/leafcutter/llama.cpp"
if [ ! -f "$LLAMA_DIR/build/src/libllama.a" ]; then
    status "Building llama.cpp (static)..."
    mkdir -p "$LLAMA_DIR/build"
    cd "$LLAMA_DIR/build"
    cmake .. \
        -DBUILD_SHARED_LIBS=OFF \
        -DGGML_NATIVE=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_VULKAN=OFF \
        -DLLAMA_CURL=OFF \
        2>&1 | tail -3
    make -j"$(nproc)" 2>&1 | tail -3
    cd "$CYNAPSE_DIR"
else
    status "llama.cpp already built"
fi

# ── Build cynapse ─────────────────────────────────────────────────
status "Building cynapse (release)..."
cd "$CYNAPSE_DIR"
cargo build --release 2>&1 | tail -3

# ── Install binary ────────────────────────────────────────────────
BINDIR="${BINDIR:-/usr/local/bin}"
if [ -w "$BINDIR" ] 2>/dev/null; then
    cp "$CYNAPSE_DIR/target/release/cynapse" "$BINDIR/cynapse"
    chmod +x "$BINDIR/cynapse"
else
    status "Installing to $BINDIR (may require password)..."
    sudo cp "$CYNAPSE_DIR/target/release/cynapse" "$BINDIR/cynapse"
    sudo chmod +x "$BINDIR/cynapse"
fi

# ── Create directories ────────────────────────────────────────────
mkdir -p "$HOME/.cynapse/data"
mkdir -p "$HOME/.cynapse/models"
mkdir -p "$HOME/.cynapse/persona/defaults"
mkdir -p "$HOME/.cynapse/workspace"

# ── Install default config if missing ─────────────────────────────
if [ ! -f "$HOME/.cynapse/config.yaml" ]; then
    if [ -f "$CYNAPSE_DIR/config.yaml" ]; then
        cp "$CYNAPSE_DIR/config.yaml" "$HOME/.cynapse/config.yaml"
        chmod 600 "$HOME/.cynapse/config.yaml"
        status "Installed default config to ~/.cynapse/config.yaml"
    fi
else
    # Fix permissions on existing config
    chmod 600 "$HOME/.cynapse/config.yaml" 2>/dev/null || true
fi

# ── Copy persona defaults if missing ──────────────────────────────
if [ -d "$CYNAPSE_DIR/persona/defaults" ]; then
    cp -rn "$CYNAPSE_DIR/persona/defaults/"* "$HOME/.cynapse/persona/defaults/" 2>/dev/null || true
fi

# ── Verify installation ──────────────────────────────────────────
if command -v cynapse >/dev/null 2>&1; then
    STATUS_OUTPUT=$(cynapse doctor 2>&1 | head -20)
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           ⚡ CYNAPSE INSTALLED SUCCESSFULLY                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Quick start:"
    echo "    cynapse          # Open the TUI"
    echo "    cynapse cli      # Open the CLI (lightweight)"
    echo "    cynapse doctor   # Run system diagnostics"
    echo ""
    echo "  Put your .gguf models in: ~/Downloads/models/"
    echo "  Then edit ~/.cynapse/config.yaml to point models_dir there."
    echo ""
else
    echo ""
    echo "Installed to $BINDIR/cynapse"
    echo "You may need to restart your shell or run: export PATH=\"$BINDIR:\$PATH\""
    echo ""
fi
