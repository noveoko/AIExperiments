#!/usr/bin/env bash
# Install Databricks CLI, Java 17, and dev tooling. Idempotent.
set -euo pipefail

log() { printf '==> [databricks] %s\n' "$*"; }

if command -v java &>/dev/null; then
  log "Java already installed: $(java -version 2>&1 | head -1)"
else
  log "Installing OpenJDK 17..."
  sudo apt-get install -y openjdk-17-jdk
fi

JAVA_HOME_PATH="/usr/lib/jvm/java-17-openjdk-amd64"
if [[ -d "$JAVA_HOME_PATH" ]]; then
  export JAVA_HOME="$JAVA_HOME_PATH"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

export PATH="$HOME/.local/bin:$PATH"

if command -v databricks &>/dev/null; then
  log "Databricks CLI already installed: $(databricks --version 2>/dev/null || echo installed)"
else
  if command -v uv &>/dev/null; then
    log "Installing Databricks CLI via uv tool..."
    uv tool install databricks-cli
  else
    log "Installing Databricks CLI via pip..."
    pip install --user databricks-cli
  fi
fi

if databricks auth profiles 2>/dev/null | grep -q .; then
  log "Databricks auth profile(s) configured"
else
  log "No Databricks auth profile. Run:"
  log "  databricks auth login --host https://adb-<workspace-id>.azuredatabricks.net"
fi

log "Databricks setup complete."
log "Install Databricks Connect per-project: uv add databricks-connect  (or poetry add)"