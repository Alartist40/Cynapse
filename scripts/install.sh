#!/usr/bin/env bash
set -euo pipefail

# cynapse one-command bootstrap installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/xander/cynapse-rs/main/scripts/install.sh | bash
#
# This script builds cynapse from source (Rust/Cargo required) and installs it
# to ~/.cynapse/builds/versions/<git-hash>/cynapse with ~/.local/bin/cynapse as
# the launcher symlink. A `git` and `cargo` build chain is required for source
# installs; binary downloads are handled by install_release.sh instead.

CYNAPSE_HOME="${CYNAPSE_HOME:-$HOME/.cynapse}"
BUILDS_DIR="$CYNAPSE_HOME/builds"
STABLE_DIR="$BUILDS_DIR/stable"
CURRENT_DIR="$BUILDS_DIR/current"
VERSIONS_DIR="$BUILDS_DIR/versions"
INSTALL_DIR="${CYNAPSE_INSTALL_DIR:-$HOME/.local/bin}"

info()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
err()   { printf '\033[1;31merror: %s\033[0m\n' "$*" >&2; exit 1; }

# ─── prerequisites ─────────────────────────────────────────────────────────

command -v git   >/dev/null 2>&1 || err "git is required"
command -v cargo >/dev/null 2>&1 || err "cargo and Rust are required (https://rustup.rs)"

# ─── build from development source ────────────────────────────────────────────

REPO_URL="${CYNAPSE_REPO:-https://github.com/nex/cynapse-rs.git}"
BRANCH="${CYNAPSE_BRANCH:-master}"

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

# ─── PATH setup ──────────────────────────────────────────────────────────────

PATH_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""
ensure_rc() {
  local rc="$1"; local create="$2"
  if [ ! -f "$rc" ]; then
    [ "$create" = "yes" ] || return 0; mkdir -p "$(dirname "$rc")"
  fi
  if ! grep -qF "$INSTALL_DIR" "$rc" 2>/dev/null; then
    printf '\n# Added by cynapse installer\n%s\n' "$PATH_LINE" >> "$rc"
  fi
}
ensure_fish_rc() {
  local create="$1"
  local rc="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
  if [ ! -f "$rc" ]; then
    [ "$create" = "yes" ] || return 0; mkdir -p "$(dirname "$rc")"
  fi
  if ! grep -qF "$INSTALL_DIR" "$rc" 2>/dev/null; then
    printf '\n# Added by cynapse installer\nif not contains "%s" $PATH\n    set -gx PATH "%s" $PATH\nend\n' "$INSTALL_DIR" "$INSTALL_DIR" >> "$rc"
  fi
}

for rc in "$HOME/.zshenv" "$HOME/.bashrc" "$HOME/.profile"; do
  ensure_rc "$rc" yes
done
if command -v fish >/dev/null 2>&1; then
  ensure_fish_rc yes
fi

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