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

# ─── try prebuilt download ─────────────────────────────────────────────────

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

command -v git   >/dev/null 2>&1 || err "git is required"
command -v cargo >/dev/null 2>&1 || err "cargo and Rust are required (https://rustup.rs)"

# ─── build from development source ────────────────────────────────────────────

BRANCH="${CYNAPSE_BRANCH:-main}"

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

info "Cloning $REPO_URL ($BRANCH) ..."
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$tmpdir/cynapse-src"

info "Building cynapse (release profile) ..."
cargo build --release --manifest-path "$tmpdir/cynapse-src/Cargo.toml" || err "cargo build failed"

info "Determining version hash ..."
VERSION_HASH=$(git -C "$tmpdir/cynapse-src" rev-parse --short HEAD)
VERSION_DIR="$VERSIONS_DIR/$VERSION_HASH"
mkdir -p "$INSTALL_DIR" "$VERSION_DIR" "$STABLE_DIR"

# Copy the binary to the versioned directory
cp "$tmpdir/cynapse-src/target/release/cynapse" "$VERSION_DIR/cynapse"
chmod +x "$VERSION_DIR/cynapse"
echo "$VERSION_HASH" > "$VERSION_DIR/VERSION"

# Symlink: stable → versioned binary
ln -sfn "$VERSION_DIR/cynapse" "$STABLE_DIR/cynapse"
# Launcher: ~/.local/bin/cynapse → stable
ln -sfn "$STABLE_DIR/cynapse" "$INSTALL_DIR/cynapse"

# Record metadata
echo "$VERSION_HASH" > "$BUILDS_DIR/stable-version"

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