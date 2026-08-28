#!/usr/bin/env bash
# Build cynapse from the local source tree and install it as the active
# "current" channel. Sets up the immutable version store + launcher.
#
# Paths after install:
# - ~/.cynapse/builds/versions/<hash>/cynapse (immutable binary)
# - ~/.cynapse/builds/stable/cynapse    -> .../versions/<hash>/cynapse
# - ~/.cynapse/builds/current/cynapse   -> .../versions/<hash>/cynapse
# - ~/.local/bin/cynapse                -> ~/.cynapse/builds/current/cynapse
#
# Usage:
#   scripts/install_release.sh [--fast]
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
CYNAPSE_HOME="${CYNAPSE_HOME:-$HOME/.cynapse}"
BUILDS_DIR="$CYNAPSE_HOME/builds"
STABLE_DIR="$BUILDS_DIR/stable"
CURRENT_DIR="$BUILDS_DIR/current"
VERSIONS_DIR="$BUILDS_DIR/versions"
INSTALL_DIR="${CYNAPSE_INSTALL_DIR:-$HOME/.local/bin}"

profile="release-lto"
if [[ "${1:-}" == "--fast" ]]; then
  profile="release"
  shift
fi
if [[ "$#" -gt 0 ]]; then
  echo "Usage: $0 [--fast]" >&2
  exit 1
fi

case "$profile" in
  release-lto) echo "Building with LTO (this takes a few minutes)..." ;;
  release)     echo "Building fast release profile (no LTO)..." ;;
  *)           echo "Unsupported profile: $profile" >&2; exit 1 ;;
esac

RUSTFLAGS="-C target-cpu=native" cargo build --profile "$profile" --manifest-path "$repo_root/Cargo.toml" -j 2
bin="$repo_root/target/$profile/cynapse"
[[ -x "$bin" ]] || { echo "Release binary not found: $bin" >&2; exit 1; }

hash="$(git -C "$repo_root" rev-parse --short HEAD 2>/dev/null || echo "local")"
if [[ -n "$hash" ]] && [[ -n "$(git -C "$repo_root" status --porcelain 2>/dev/null || true)" ]]; then
  hash="${hash}-dirty"
fi

version_dir="$VERSIONS_DIR/$hash"
CARGO_BIN="$HOME/.cargo/bin"
mkdir -p "$INSTALL_DIR" "$CARGO_BIN" "$version_dir" "$STABLE_DIR" "$CURRENT_DIR"
install -m 755 "$bin" "$version_dir/cynapse"
install -m 755 "$bin" "$CARGO_BIN/cynapse" 2>/dev/null || true
echo "$hash" > "$version_dir/VERSION"

ln -sfn "$version_dir/cynapse" "$STABLE_DIR/cynapse"
ln -sfn "$version_dir/cynapse" "$CURRENT_DIR/cynapse"
ln -sfn "$CURRENT_DIR/cynapse" "$INSTALL_DIR/cynapse"

echo "$hash" > "$BUILDS_DIR/stable-version"
echo "$hash" > "$BUILDS_DIR/current-version"

echo ""
echo "Installed cynapse ($hash) → $INSTALL_DIR/cynapse"
echo ""
if command -v cynapse >/dev/null 2>&1; then
  echo "Run 'cynapse' to start a chat session."
else
  echo "Add $INSTALL_DIR to your PATH (or restart the shell), then run 'cynapse'."
fi