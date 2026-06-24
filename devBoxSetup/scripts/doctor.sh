#!/usr/bin/env bash
# Verify developer environment setup. Run from WSL after bootstrap.
set -uo pipefail

PASS=0
FAIL=0
WARN=0

green()  { printf '\033[0;32m✓\033[0m %s\n' "$1"; ((PASS++)) || true; }
red()    { printf '\033[0;31m✗\033[0m %s\n' "$1"; ((FAIL++)) || true; }
yellow() { printf '\033[0;33m!\033[0m %s\n' "$1"; ((WARN++)) || true; }

check_cmd() {
  local name="$1" cmd="$2"
  if command -v "$cmd" &>/dev/null; then
    green "$name: $($cmd --version 2>/dev/null | head -1 || echo 'installed')"
  else
    red "$name: not found ($cmd)"
  fi
}

echo "=== DevBox Setup Doctor ==="
echo ""

# --- WSL environment ---
if grep -qi microsoft /proc/version 2>/dev/null; then
  green "WSL: running under WSL"
else
  yellow "WSL: not detected (run from WSL for full checks)"
fi

if [[ -f /proc/sys/fs/binfmt_misc/WSLInterop ]] || grep -qi wsl /proc/version 2>/dev/null; then
  wsl_ver=$(wsl.exe --version 2>/dev/null | head -1 || echo "unknown")
  if echo "$wsl_ver" | grep -qi "2"; then
    green "WSL version: 2"
  else
    yellow "WSL version: could not confirm version 2 ($wsl_ver)"
  fi
fi

cwd=$(pwd)
if [[ "$cwd" == /mnt/* ]]; then
  yellow "Working directory is on Windows mount ($cwd) — prefer ~/src for repos"
else
  green "Working directory is on Linux filesystem ($cwd)"
fi

if [[ -d "$HOME/src" ]]; then
  green "Directory layout: ~/src exists"
else
  yellow "Directory layout: ~/src missing (run wsl/bootstrap.sh)"
fi

echo ""
echo "--- Core tools ---"
check_cmd "Git" git
check_cmd "curl" curl
check_cmd "jq" jq
check_cmd "direnv" direnv

echo ""
echo "--- Python trinity ---"
check_cmd "pyenv" pyenv
if command -v pyenv &>/dev/null; then
  versions=$(pyenv versions --bare 2>/dev/null | tr '\n' ' ')
  if [[ -n "$versions" ]]; then
    green "pyenv versions: $versions"
  else
    red "pyenv versions: none installed"
  fi
fi
check_cmd "uv" uv
check_cmd "poetry" poetry
check_cmd "ruff" ruff
check_cmd "pytest" pytest

echo ""
echo "--- Node.js ---"
check_cmd "fnm" fnm
if command -v fnm &>/dev/null; then
  eval "$(fnm env)" 2>/dev/null || true
fi
check_cmd "node" node
check_cmd "npm" npm

echo ""
echo "--- Azure & Databricks ---"
check_cmd "Azure CLI" az
if az extension list --query "[?name=='azure-devops'].name" -o tsv 2>/dev/null | grep -q azure-devops; then
  green "Azure DevOps extension: installed"
else
  red "Azure DevOps extension: not installed (az extension add --name azure-devops)"
fi

if az account show --query name -o tsv &>/dev/null; then
  account=$(az account show --query name -o tsv 2>/dev/null)
  green "Azure login: $account"
else
  yellow "Azure login: not logged in (run: az login)"
fi

check_cmd "Databricks CLI" databricks
if command -v databricks &>/dev/null; then
  if databricks auth profiles 2>/dev/null | grep -q .; then
    green "Databricks auth: profile(s) configured"
  else
    yellow "Databricks auth: no profiles (run: databricks auth login)"
  fi
fi

echo ""
echo "--- Java (Spark) ---"
if command -v java &>/dev/null; then
  green "Java: $(java -version 2>&1 | head -1)"
  if [[ -n "${JAVA_HOME:-}" ]]; then
    green "JAVA_HOME: $JAVA_HOME"
  else
    yellow "JAVA_HOME: not set"
  fi
else
  red "Java: not found (required for Databricks Connect / Spark)"
fi

echo ""
echo "--- Git credentials ---"
helper=$(git config --global credential.helper 2>/dev/null || echo "")
if [[ -n "$helper" ]]; then
  green "Git credential helper: $helper"
else
  yellow "Git credential helper: not configured"
fi

git_name=$(git config --global user.name 2>/dev/null || echo "")
git_email=$(git config --global user.email 2>/dev/null || echo "")
if [[ -n "$git_name" && -n "$git_email" ]]; then
  green "Git identity: $git_name <$git_email>"
else
  yellow "Git identity: not fully configured (user.name / user.email)"
fi

echo ""
echo "--- Optional: Databricks Connect ---"
if command -v uv &>/dev/null; then
  if uv run python -c "import databricks.connect" &>/dev/null 2>&1; then
    green "databricks-connect: importable"
  else
    yellow "databricks-connect: not installed in current project (add per-project)"
  fi
elif command -v python3 &>/dev/null; then
  if python3 -c "import databricks.connect" &>/dev/null 2>&1; then
    green "databricks-connect: importable"
  else
    yellow "databricks-connect: not installed (add per-project)"
  fi
fi

echo ""
echo "=== Summary: $PASS passed, $FAIL failed, $WARN warnings ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0