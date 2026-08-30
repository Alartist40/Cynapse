#!/usr/bin/env bash
set -euo pipefail

# cynapse one-command bootstrap installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Alartist40/cynapse/main/scripts/install.sh | bash
#
# Downloads the prebuilt cynapse binary for your OS/CPU when one is published
# (github.com/Alartist40/cynapse/releases); otherwise it falls back to building
# from source (Rust/Cargo required). The launcher is symlinked at
# ~/.local/bin/cynapse (and ~/.cynapse/builds/stable/cynapse).

CYNAPSE_HOME="${CYNAPSE_HOME:-$HOME/.cynapse}"
BUILDS_DIR="$CYNAPSE_HOME/builds"
STABLE_DIR="$BUILDS_DIR/stable"
CURRENT_DIR="$BUILDS_DIR/current"
VERSIONS_DIR="$BUILDS_DIR/versions"
INSTALL_DIR="${CYNAPSE_INSTALL_DIR:-$HOME/.local/bin}"

info()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
err()   { printf '\033[1;31merror: %s\033[0m\n' "$*" >&2; exit 1; }

# ─── PATH setup ──────────────────────────────────────────────────────────────

# Append $INSTALL_DIR to the shell rc files so `cynapse` works from any dir.
ensure_path() {
  local dir="$1"
  local path_line="export PATH=\"$dir:\$PATH\""
  ensure_rc() {
    local rc="$1"; local create="$2"
    if [ ! -f "$rc" ]; then
      [ "$create" = "yes" ] || return 0; mkdir -p "$(dirname "$rc")"
    fi
    if ! grep -qF "$dir" "$rc" 2>/dev/null; then
      printf '\n# Added by cynapse installer\n%s\n' "$path_line" >> "$rc"
    fi
  }
  ensure_fish_rc() {
    local create="$1"
    local rc="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
    if [ ! -f "$rc" ]; then
      [ "$create" = "yes" ] || return 0; mkdir -p "$(dirname "$rc")"
    fi
    if ! grep -qF "$dir" "$rc" 2>/dev/null; then
      printf '\n# Added by cynapse installer\nif not contains "%s" $PATH\n    set -gx PATH "%s" $PATH\nend\n' "$dir" "$dir" >> "$rc"
    fi
  }
  for rc in "$HOME/.zshenv" "$HOME/.bashrc" "$HOME/.profile"; do
    ensure_rc "$rc" yes
  done
  if command -v fish >/dev/null 2>&1; then
    ensure_fish_rc yes
  fi
}

# ─── platform detection ────────────────────────────────────────────────────

uname_os() {
    os=$(uname -s)
    case "$os" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *) echo "linux" ;;
    esac
}

uname_arch() {
    arch=$(uname -m)
    case "$arch" in
        x86_64|amd64)  echo "x86_64" ;;
        aarch64|arm64) echo "aarch64" ;;
        *) echo "$arch" ;;
    esac
}

OS=$(uname_os)
ARCH=$(uname_arch)
echo "Detected: ${OS}/${ARCH}"

REPO_URL="${CYNAPSE_REPO:-https://github.com/Alartist40/cynapse.git}"
REPO="Alartist40/cynapse"

# ─── try prebuilt download (skip if running in local source tree) ─────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$REPO_DIR/Cargo.toml" ]; then
    CYNAPSE_SOURCE_BUILD=1
fi

if [ "${CYNAPSE_SOURCE_BUILD:-0}" != "1" ]; then
    if command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
        asset="cynapse-${OS}-${ARCH}"
        url="https://github.com/${REPO}/releases/latest/download/${asset}"
        tmp="${TMPDIR:-/tmp}/${asset}"
        echo "⬇️  Downloading ${asset} …"
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL -o "$tmp" "$url" 2>/dev/null || { rm -f "$tmp"; DOWNLOAD_FAILED=1; }
        else
            wget -q -O "$tmp" "$url" 2>/dev/null || { rm -f "$tmp"; DOWNLOAD_FAILED=1; }
        fi
        if [ "${DOWNLOAD_FAILED:-0}" != "1" ] && [ -s "$tmp" ]; then
            if head -c 4 "$tmp" | od -An -tx1 | grep -qE "7f 45 4c 46|4d 5a|fa ed fe|fe ed fa"; then
                chmod +x "$tmp"
                mkdir -p "$VERSIONS_DIR" "$STABLE_DIR" "$INSTALL_DIR"
                VERSION_HASH="$(echo "$url" | sha256sum | cut -c1-7)"
                VERSION_DIR="$VERSIONS_DIR/$VERSION_HASH"
                mkdir -p "$VERSION_DIR"
                cp "$tmp" "$VERSION_DIR/cynapse"
                chmod +x "$VERSION_DIR/cynapse"
                echo "$VERSION_HASH" > "$VERSION_DIR/VERSION"
                ln -sfn "$VERSION_DIR/cynapse" "$STABLE_DIR/cynapse"
                ln -sfn "$STABLE_DIR/cynapse" "$INSTALL_DIR/cynapse"
                echo "$VERSION_HASH" > "$BUILDS_DIR/stable-version"
                rm -f "$tmp"
                echo "✅ cynapse ($VERSION_HASH) installed successfully (prebuilt)!"
                echo ""
                info "Run 'cynapse' to start a chat session."
                echo ""
                ensure_path "$INSTALL_DIR"
                echo "  Config: $CYNAPSE_HOME/config.yaml (edit to set your LLM provider)"
                echo "  Persona: $CYNAPSE_HOME/persona/"
                echo "  Sessions: $CYNAPSE_HOME/data/sessions/"
                exit 0
            fi
            rm -f "$tmp"
        fi
        echo "No prebuilt binary for ${OS}/${ARCH} — building from source."
    fi
fi

# ─── prerequisites ─────────────────────────────────────────────────────────

command -v git    >/dev/null 2>&1 || err "git is required"
command -v cargo  >/dev/null 2>&1 || err "cargo and Rust are required (https://rustup.rs)"
command -v cmake  >/dev/null 2>&1 || err "cmake is required for building vendored llama.cpp"

# ─── build from development source ────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$REPO_DIR/Cargo.toml" ]; then
    info "Building cynapse from local source ($REPO_DIR) …"
    SRC_DIR="$REPO_DIR"
else
    BRANCH="${CYNAPSE_BRANCH:-main}"
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' EXIT
    info "Cloning $REPO_URL ($BRANCH) ..."
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$tmpdir/cynapse-src"
    SRC_DIR="$tmpdir/cynapse-src"
fi

info "Building cynapse (hardware-safe release profile) ..."
RUSTFLAGS="-C target-cpu=native -C opt-level=3 -C target-feature=+neon,+dotprod,+i8mm,+sve2" cargo build --release --manifest-path "$SRC_DIR/Cargo.toml" || err "cargo build failed"

info "Determining version hash ..."
VERSION_HASH=$(git -C "$SRC_DIR" rev-parse --short HEAD 2>/dev/null || echo "local")
VERSION_DIR="$VERSIONS_DIR/$VERSION_HASH"
CARGO_BIN="$HOME/.cargo/bin"
mkdir -p "$INSTALL_DIR" "$CARGO_BIN" "$VERSION_DIR" "$STABLE_DIR" "$CURRENT_DIR" "$CYNAPSE_HOME"

# Seed default config, assets, docs, and persona templates into ~/.cynapse/ if not present
if [ -d "$SRC_DIR/assets" ]; then
    mkdir -p "$CYNAPSE_HOME/assets"
    cp -r "$SRC_DIR/assets/"* "$CYNAPSE_HOME/assets/" 2>/dev/null || true
fi
if [ -d "$SRC_DIR/persona" ]; then
    mkdir -p "$CYNAPSE_HOME/persona"
    cp -r "$SRC_DIR/persona/"* "$CYNAPSE_HOME/persona/" 2>/dev/null || true
fi
if [ -f "$SRC_DIR/config.yaml" ] && [ ! -f "$CYNAPSE_HOME/config.yaml" ]; then
    cp "$SRC_DIR/config.yaml" "$CYNAPSE_HOME/config.yaml"
fi
if [ -d "$SRC_DIR/docs" ]; then
    mkdir -p "$CYNAPSE_HOME/docs"
    cp -r "$SRC_DIR/docs/"* "$CYNAPSE_HOME/docs/" 2>/dev/null || true
fi

# Install binary atomically using install -m 755
install -m 755 "$SRC_DIR/target/release/cynapse" "$VERSION_DIR/cynapse"
install -m 755 "$SRC_DIR/target/release/cynapse" "$STABLE_DIR/cynapse"
install -m 755 "$SRC_DIR/target/release/cynapse" "$CURRENT_DIR/cynapse"
install -m 755 "$SRC_DIR/target/release/cynapse" "$INSTALL_DIR/cynapse"
install -m 755 "$SRC_DIR/target/release/cynapse" "$CARGO_BIN/cynapse" 2>/dev/null || true
echo "$VERSION_HASH" > "$VERSION_DIR/VERSION"

# Record metadata
echo "$VERSION_HASH" > "$BUILDS_DIR/stable-version"
echo "$VERSION_HASH" > "$BUILDS_DIR/current-version"

ensure_path "$CARGO_BIN"
ensure_path "$INSTALL_DIR"

echo ""
info "✅ cynapse ($VERSION_HASH) installed successfully!"
echo ""
info "Run 'cynapse' to start a chat session."
echo ""

if ! command -v cynapse >/dev/null 2>&1; then
  echo "  Refresh your shell or run:"
  echo ""
  printf '    \033[1;32mexport PATH="%s:\$PATH" && cynapse\033[0m\n' "$INSTALL_DIR"
  echo ""
fi

echo "  Config: $CYNAPSE_HOME/config.yaml (edit to set your LLM provider)"
echo "  Persona: $CYNAPSE_HOME/persona/"
echo "  Sessions: $CYNAPSE_HOME/data/sessions/"