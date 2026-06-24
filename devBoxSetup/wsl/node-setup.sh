#!/usr/bin/env bash
# Install fnm and Node.js LTS. Idempotent.
set -euo pipefail

log() { printf '==> [node] %s\n' "$*"; }

NODE_VERSION="${NODE_VERSION:-20}"

if command -v fnm &>/dev/null; then
  log "fnm already installed"
else
  log "Installing fnm..."
  curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir "$HOME/.local/share/fnm" --skip-shell
  mkdir -p "$HOME/.local/bin"
  ln -sf "$HOME/.local/share/fnm/fnm" "$HOME/.local/bin/fnm" 2>/dev/null || true
fi

export PATH="$HOME/.local/bin:$PATH"
eval "$(fnm env)" 2>/dev/null || true

if fnm list 2>/dev/null | grep -q "$NODE_VERSION"; then
  log "Node $NODE_VERSION already installed"
else
  log "Installing Node $NODE_VERSION..."
  fnm install "$NODE_VERSION"
fi

fnm default "$NODE_VERSION"
fnm use "$NODE_VERSION"

log "Node: $(node --version), npm: $(npm --version)"
log "Node.js setup complete."