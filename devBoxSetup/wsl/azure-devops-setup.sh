#!/usr/bin/env bash
# Install Azure CLI + DevOps extension. Idempotent.
set -euo pipefail

log() { printf '==> [azure] %s\n' "$*"; }

if command -v az &>/dev/null; then
  log "Azure CLI already installed: $(az version --query '\"azure-cli\"' -o tsv 2>/dev/null || az --version | head -1)"
else
  log "Installing Azure CLI..."
  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
fi

if az extension list --query "[?name=='azure-devops'].name" -o tsv 2>/dev/null | grep -q azure-devops; then
  log "Azure DevOps extension already installed"
else
  log "Installing Azure DevOps extension..."
  az extension add --name azure-devops --yes 2>/dev/null || az extension add --name azure-devops
fi

if ! az account show &>/dev/null; then
  log "Not logged in to Azure. Run: az login"
  log "Then configure defaults: az devops configure --defaults organization=https://dev.azure.com/<ORG> project=<PROJECT>"
else
  log "Azure account: $(az account show --query name -o tsv)"
fi

SSH_KEY="$HOME/.ssh/id_ed25519"
if [[ ! -f "$SSH_KEY" ]]; then
  log "No SSH key found. Generate one if your org allows SSH to Azure Repos:"
  log "  ssh-keygen -t ed25519 -C \"your.email@corp.com\""
  log "  Add public key: Azure DevOps → User Settings → SSH Public Keys"
else
  log "SSH key exists: $SSH_KEY.pub"
fi

log "Azure DevOps setup complete."