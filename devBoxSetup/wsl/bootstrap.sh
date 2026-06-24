#!/usr/bin/env bash
# WSL foundation bootstrap. Idempotent — safe to re-run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { printf '==> %s\n' "$*"; }

log "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
  build-essential curl git jq unzip zip ca-certificates \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev libffi-dev liblzma-dev tk-dev \
  direnv

log "Creating directory layout..."
mkdir -p "$HOME/src" "$HOME/tools" "$HOME/.local/bin" "$HOME/.config/direnv"

log "Installing shell snippet..."
BASHRC="$HOME/.bashrc"
MARKER_BEGIN="# BEGIN devBoxSetup"
MARKER_END="# END devBoxSetup"
SNIPPET="$SCRIPT_DIR/shell/bashrc.snippet"

if ! grep -qF "$MARKER_BEGIN" "$BASHRC" 2>/dev/null; then
  echo "" >> "$BASHRC"
  cat "$SNIPPET" >> "$BASHRC"
  log "Appended devBoxSetup snippet to ~/.bashrc"
else
  log "devBoxSetup snippet already in ~/.bashrc"
fi

log "Installing direnv global config..."
DIRENVRC="$HOME/.config/direnv/direnvrc"
if [[ ! -f "$DIRENVRC" ]]; then
  cp "$SCRIPT_DIR/shell/direnvrc.example" "$DIRENVRC"
  log "Created ~/.config/direnv/direnvrc"
fi

log "Configuring Git..."
if [[ -z "$(git config --global user.name 2>/dev/null || true)" ]]; then
  if [[ -n "${GIT_USER_NAME:-}" ]]; then
    git config --global user.name "$GIT_USER_NAME"
  elif [[ -t 0 ]]; then
    read -rp "Git user.name: " git_name
    git config --global user.name "$git_name"
  else
    log "Set GIT_USER_NAME or run: git config --global user.name 'Your Name'"
  fi
fi
if [[ -z "$(git config --global user.email 2>/dev/null || true)" ]]; then
  if [[ -n "${GIT_USER_EMAIL:-}" ]]; then
    git config --global user.email "$GIT_USER_EMAIL"
  elif [[ -t 0 ]]; then
    read -rp "Git user.email: " git_email
    git config --global user.email "$git_email"
  else
    log "Set GIT_USER_EMAIL or run: git config --global user.email 'you@corp.com'"
  fi
fi
git config --global init.defaultBranch main

GCM="/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe"
if [[ -f "$GCM" ]]; then
  git config --global credential.helper "$GCM"
  git config --global credential.https://dev.azure.com.useHttpPath true
  log "Git Credential Manager configured (Windows SSO bridge)"
else
  log "Git Credential Manager not found at $GCM — configure manually if needed"
fi

log "Linking devBoxSetup to ~/tools..."
ln -sfn "$SETUP_ROOT" "$HOME/tools/devBoxSetup"
export DEVBOX_SETUP_HOME="$HOME/tools/devBoxSetup"

log "Running Python setup..."
bash "$SCRIPT_DIR/python-setup.sh"

log "Running Node.js setup..."
bash "$SCRIPT_DIR/node-setup.sh"

log "Running Azure DevOps setup..."
bash "$SCRIPT_DIR/azure-devops-setup.sh"

log "Running Databricks setup..."
bash "$SCRIPT_DIR/databricks-setup.sh"

log "Bootstrap complete. Run: source ~/.bashrc && bash $SETUP_ROOT/scripts/doctor.sh"