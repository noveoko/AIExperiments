# DevBox Professional Developer Setup

Reproducible bootstrap for **Microsoft DevBox** + **WSL2** + **Python (pyenv/uv/Poetry)** + **Azure DevOps** + **Databricks**.

Designed for corporate DevBox environments where IT provisions the pool and you configure personal tooling.

## Architecture

```
DevBox (Windows 11)
├── Cursor / VS Code  ──Remote WSL──►  WSL2 Ubuntu (primary dev shell)
├── Git Credential Manager (Entra ID SSO)
└── Azure CLI (browser auth)

WSL2
├── ~/src/          ← clone all repos here (NOT /mnt/c/ or /mnt/d/)
├── pyenv           ← Python interpreter versions
├── uv              ← projects with uv.lock
├── Poetry          ← projects with poetry.lock
├── Azure CLI + azure-devops extension
└── Databricks CLI + Java 17
```

## Prerequisites (before running scripts)

Get these from your platform / project teams:

| Item | Who provides it |
|------|-----------------|
| DevBox pool access | IT / platform engineering |
| Azure DevOps org + **Basic** license | Project admin |
| Contributor access on target repos | Project admin |
| Databricks workspace URL + cluster policy | Data platform team |
| Approval for `devbox/team-customization.yaml` | IT |

## Configurator UI (recommended)

A **local-only web wizard** for corporate-specific settings (org names, workspace URLs, PATs) that should not be shared with chat tools.

```bash
cd devBoxSetup
uv sync
uv run devbox-configurator
# Open http://127.0.0.1:9477
```

The configurator:

- Walks you through identity, DevBox/WSL, Python, Databricks, and CI/CD settings
- Saves profiles to `~/.config/devbox-setup/profiles/` (mode `0600`)
- Stores secrets separately in `~/.config/devbox-setup/secrets.local.json` (never returned by API)
- Generates ready-to-use YAML, `.env`, `.wslconfig`, and pipeline files
- Writes artifacts to `~/.config/devbox-setup/generated/<profile>/`
- Runs `doctor.sh` and `bootstrap.sh` with live output

**Trust model:** binds to `127.0.0.1:9477` only. No telemetry. No outbound data from the app.

## Quick Start (manual)

### 1. Windows (first DevBox login)

```powershell
cd C:\src\devBoxSetup   # or wherever you cloned this repo
.\windows\bootstrap.ps1
```

This installs WSL2, host tools, IDE extensions, and kicks off the WSL bootstrap.

### 2. WSL (primary dev shell)

If you skipped the Windows script, run directly inside Ubuntu:

```bash
bash /path/to/devBoxSetup/wsl/bootstrap.sh
source ~/.bashrc
```

### 3. Authenticate to cloud services

```bash
az login
az devops configure --defaults organization=https://dev.azure.com/<ORG> project=<PROJECT>

databricks auth login --host https://adb-<workspace-id>.azuredatabricks.net
```

### 4. Verify everything

```bash
bash ~/tools/devBoxSetup/scripts/doctor.sh
```

## Directory Layout

After bootstrap:

```
~/src/                  # Git repositories (clone here)
~/tools/devBoxSetup/    # Symlink to this repo
~/.pyenv/               # Python versions
~/.local/bin/           # uv, Poetry, fnm, CLI tools
```

**Clone repos into WSL filesystem:**

```bash
cd ~/src
git clone https://dev.azure.com/<ORG>/<PROJECT>/_git/my-etl-repo
```

Avoid `/mnt/c/` and `/mnt/d/` — I/O is 10–20x slower and file permissions break tooling.

## Python: pyenv + uv + Poetry

All three are first-class. Pick per project based on what lockfile exists.

| Scenario | Tool | Commands |
|----------|------|----------|
| Pin interpreter | pyenv | `pyenv local 3.12.8` → writes `.python-version` |
| New project | uv | `uv init && uv add fastapi` |
| `uv.lock` project | uv | `uv sync && uv run pytest` |
| `poetry.lock` project | Poetry | `poetry install && poetry run pytest` |
| Build Databricks wheel | uv or Poetry | `uv build` / `poetry build` |
| Quick REPL | pyenv | `pyenv shell 3.11.11` |

Installed Python versions: **3.12.8** (default), **3.11.11** (Databricks runtime compatibility).

### Per-project direnv (optional)

Add to a project's `.envrc`:

```bash
use python_project
```

Copy `wsl/shell/direnvrc.example` helpers are loaded globally from `~/.config/direnv/direnvrc`.

## Azure DevOps

### Git authentication

HTTPS with Git Credential Manager (recommended on locked-down networks):

```bash
git clone https://dev.azure.com/<ORG>/<PROJECT>/_git/<REPO>
# Browser SSO prompt handled by GCM
```

SSH (if org policy allows):

```bash
ssh-keygen -t ed25519 -C "you@corp.com"
# Add ~/.ssh/id_ed25519.pub → Azure DevOps → User Settings → SSH Public Keys
```

### CI/CD template

Copy [`templates/azure-pipelines-python.yml`](templates/azure-pipelines-python.yml) into your repo as `azure-pipelines.yml`. Set `packageManager` to `uv` or `poetry`.

## Databricks

### CLI auth

```bash
databricks auth login --host https://adb-<workspace-id>.azuredatabricks.net
databricks auth profiles
```

### Local PySpark development

Add per-project (match your cluster runtime version):

```bash
uv add --dev databricks-connect
# or: poetry add --group dev databricks-connect
```

### Asset Bundles

Copy [`templates/databricks.yml`](templates/databricks.yml) as a starting point for job deployment.

## DevBox Customizations

Submit to IT for pool-level standardization:

- [`devbox/team-customization.yaml`](devbox/team-customization.yaml) — WSL, Git, Azure CLI, Cursor (system + user tasks)

Upload at dev box creation for personal setup:

- [`devbox/user-customization.yaml`](devbox/user-customization.yaml) — clone repo + run bootstrap

## IDE Setup

Extensions list: [`ide/extensions.txt`](ide/extensions.txt)

Recommended settings: [`ide/settings.json`](ide/settings.json) — copy into your user or workspace settings.

Open projects via **Remote WSL**:

```
Cursor → File → Open Folder in WSL → ~/src/<project>
```

## Project Templates

| Template | Purpose |
|----------|---------|
| [`templates/pyproject-etl.toml`](templates/pyproject-etl.toml) | ETL package with PySpark, Delta, pytest, ruff |
| [`templates/databricks.yml`](templates/databricks.yml) | Databricks Asset Bundle for job deployment |
| [`templates/azure-pipelines-python.yml`](templates/azure-pipelines-python.yml) | CI pipeline with lint + test + wheel build |
| [`templates/.env.example`](templates/.env.example) | Environment variable reference |
| [`templates/.gitignore`](templates/.gitignore) | Standard ignores for Python/Databricks projects |

## Troubleshooting

### Git Credential Manager auth loop

```bash
git config --global credential.helper "/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe"
git credential-manager erase https://dev.azure.com
az login
```

### WSL DNS / network issues

```powershell
# On Windows
wsl --shutdown
# Restart WSL, then inside WSL:
sudo resolvectl flush-caches
```

### Databricks Connect version mismatch

Match `databricks-connect` version to your cluster's Databricks Runtime. Check cluster → Spark version, then:

```bash
uv add "databricks-connect==15.4.*"
```

### Slow file I/O

Move repos from `/mnt/d/...` to `~/src/`:

```bash
mv /mnt/d/path/to/repo ~/src/repo
```

### pyenv build failures

Ensure build dependencies are installed (bootstrap.sh handles this). If a version fails:

```bash
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev libffi-dev liblzma-dev tk-dev
pyenv install 3.12.8
```

## What to Learn Next

Your ETL curriculum lives in [`../etl_curriculum/`](../etl_curriculum/):

- Azure DevOps org setup: [`etl_curriculum/tutorials/1.md`](../etl_curriculum/tutorials/1.md)
- Full process checklist: [`etl_curriculum/to _do.md`](../etl_curriculum/to%20_do.md)

## File Structure

```
devBoxSetup/
├── README.md
├── pyproject.toml    # Configurator dependencies
├── configurator/     # Local-only web UI
│   ├── app.py
│   ├── generator.py
│   ├── profiles.py
│   ├── runner.py
│   ├── schema.json
│   ├── templates/    # Jinja2 artifact templates
│   └── static/       # Wizard UI
├── devbox/           # DevBox customization YAML for IT
├── windows/          # Windows host bootstrap
├── wsl/              # WSL bootstrap + tool installers
├── ide/              # Cursor/VS Code extensions and settings
├── templates/        # Static project and pipeline starters
└── scripts/
    └── doctor.sh     # Environment verification
```