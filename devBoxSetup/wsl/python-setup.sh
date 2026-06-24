#!/usr/bin/env bash
# Install pyenv, uv, and Poetry as equal peers. Idempotent.
set -euo pipefail

log() { printf '==> [python] %s\n' "$*"; }

PYENV_VERSIONS=("3.12.8" "3.11.11")
DEFAULT_PYTHON="3.12.8"

# --- pyenv ---
if [[ ! -d "$HOME/.pyenv" ]]; then
  log "Installing pyenv..."
  curl -fsSL https://pyenv.run | bash
else
  log "pyenv already installed"
fi

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"

if [[ ! -d "$PYENV_ROOT/plugins/pyenv-virtualenv" ]]; then
  log "Installing pyenv-virtualenv..."
  git clone https://github.com/pyenv/pyenv-virtualenv.git \
    "$PYENV_ROOT/plugins/pyenv-virtualenv" 2>/dev/null || true
fi

for ver in "${PYENV_VERSIONS[@]}"; do
  if pyenv versions --bare | grep -qxF "$ver"; then
    log "Python $ver already installed"
  else
    log "Installing Python $ver (this may take a few minutes)..."
    pyenv install -s "$ver"
  fi
done

pyenv global "$DEFAULT_PYTHON"
log "Global Python: $(pyenv global)"

# --- uv ---
if command -v uv &>/dev/null; then
  log "uv already installed: $(uv --version)"
else
  log "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

mkdir -p "$HOME/.config/uv"
UV_TOML="$HOME/.config/uv/uv.toml"
if [[ ! -f "$UV_TOML" ]]; then
  cat > "$UV_TOML" <<'EOF'
# Prefer pyenv-managed interpreters over uv-downloaded Pythons
python-preference = "system"
EOF
  log "Created ~/.config/uv/uv.toml"
fi

# --- Poetry ---
if command -v poetry &>/dev/null; then
  log "Poetry already installed: $(poetry --version)"
else
  log "Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3 -
fi

poetry config virtualenvs.in-project true
poetry config virtualenvs.prefer-active-python true

# --- Shared dev tools via uv ---
export PATH="$HOME/.local/bin:$PATH"
for tool in ruff pytest pre-commit; do
  if command -v "$tool" &>/dev/null; then
    log "$tool already installed"
  else
    log "Installing $tool via uv tool..."
    uv tool install "$tool"
  fi
done

log "Python trinity setup complete."