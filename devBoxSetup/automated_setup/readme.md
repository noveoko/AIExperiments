# Development Machine Setup

Interactive CLI scripts that guide semi-technical developers through setting up a Databricks development environment on **Windows** (with optional **WSL**).

## What Gets Installed

| Component | Purpose |
|---|---|
| Python 3.10.11 | Runtime (via pyenv-win / pyenv) |
| Bash | Command shell (Git Bash on Windows) |
| Poetry | Python package and environment manager |
| VS Code | Editor |
| Databricks CLI | Workspace and deployment management |
| Databricks VS Code extension | In-editor Databricks integration |
| Artifactory credentials | Private PyPI registry access via Poetry |
| Databricks authentication | OAuth or PAT workspace login |
| databricks-connect | Local-to-cluster Python connectivity |
| pytest, pytest-mock, pytest-xdist | Testing |
| ruff, black, pre-commit | Linting, formatting, git hooks |

## Quick Start (Developers)

### 1. Get the config file from IT

Your IT team should provide a `setup.config.json` (copied from `setup.config.json.example` with your organization's values filled in).

### 2. Set your Artifactory token

```powershell
$env:ARTIFACTORY_TOKEN = "your-token-here"
```

Or set it permanently in Windows Environment Variables.

### 3. Run the setup

Open PowerShell in this folder and run:

```powershell
.\setup.ps1
```

The script walks you through each step with plain-language explanations. Press Enter to proceed, or type `skip` to defer a step.

### 4. Verify everything

```powershell
.\setup.ps1 -VerifyOnly
```

## Quick Start (IT)

1. Copy `setup.config.json.example` to `setup.config.json`
2. Fill in organization values:

| Field | Description |
|---|---|
| `artifactory.url` | Your JFrog Artifactory PyPI simple index URL |
| `artifactory.username` | Artifactory username |
| `databricks.host` | Databricks workspace URL (e.g. `https://adb-xxx.azuredatabricks.net`) |
| `databricks.cluster_runtime` | Cluster DBR version for databricks-connect (e.g. `17.3`) |
| `project.name` / `project.directory` | Where the Poetry project will be created |

3. Distribute the folder (zip or git clone) to developers
4. **Do not commit** `setup.config.json` — it is in `.gitignore`

## WSL Setup

When `wsl.run_wsl_setup` is `true` in the config, `setup.ps1` offers to run the same toolchain inside WSL after Windows steps complete.

You can also run WSL setup directly:

```bash
./setup.sh
```

## Resuming After a Failure

```powershell
# Windows — resume from step 8 (Artifactory)
.\setup.ps1 -Step 8
```

```bash
# WSL — resume from step 8
./setup.sh --step 8
```

## Dry Run

Preview what the script would do without making changes:

```powershell
.\setup.ps1 -DryRun
```

```bash
./setup.sh --dry-run
```

## Corporate / Locked-Down Environments

Many steps assume outbound HTTPS and admin rights. If you are on a corporate laptop:

1. **Gather tokens first** — step 1 walks you through VPN, Artifactory token, and Databricks PAT
2. **Run proxy/SSL early** — step 2 detects proxy, sets `HTTP_PROXY`/`NO_PROXY`, and configures your CA bundle
3. **Use PAT for Databricks** — OAuth is often blocked by corporate SSO; choose option 2 at step 9
4. **pre-commit needs GitHub** — step 12 probes github.com; skip or set `corporate.github_mirror` in config
5. **Open an IT ticket** — `.\setup.ps1 -GenerateItWhitelist` exports required domains
6. **Escalate failures** — `.\setup.ps1 -GenerateSupportBundle` creates a redacted zip for helpdesk

### Corporate-only commands

```powershell
.\setup.ps1 -CorporatePreflight          # Steps 1-2 only
.\setup.ps1 -DatabricksTroubleshoot
.\setup.ps1 -GenerateItWhitelist
.\setup.ps1 -GenerateSupportBundle
```

IT should pre-fill in `setup.config.json`:

| Field | Purpose |
|---|---|
| `corporate.proxy_url` | Default proxy (e.g. `http://proxy.corp:8080`) |
| `corporate.ca_bundle_path` | Path to corporate root CA PEM file |
| `corporate.no_proxy` | Internal domains that bypass proxy |
| `corporate.github_mirror` | Internal GitHub mirror for pre-commit hooks |
| `databricks.cluster_id` | Cluster to validate at step 13 |

## Artifactory Setup (the painful part)

Step 7 offers four options. Most developers with a JFrog account should use **Paste snippet**:

1. In JFrog Artifactory, open your PyPI repository
2. Click **Set Me Up** > **Poetry**
3. Copy the commands shown (typically `poetry config http-basic.<name> <user> <token>`)
4. At step 7, choose `[2] Paste snippet` and paste the block
5. Confirm the parsed preview, then review the diagnostic report

### Standalone Artifactory commands

```powershell
# Interactive menu (guided / paste / manual / troubleshoot)
.\setup.ps1 -ArtifactorySetup

# Diagnostics only — no changes
.\setup.ps1 -ArtifactoryTroubleshoot

# Apply a snippet directly (non-interactive)
.\setup.ps1 -ArtifactorySnippet "poetry config http-basic.artifactory myuser mytoken"

# Extra detail on failures
.\setup.ps1 -ArtifactoryTroubleshoot -ArtifactoryVerbose
```

```bash
./setup.sh --artifactory-setup
./setup.sh --artifactory-troubleshoot
./setup.sh --artifactory-snippet "poetry config http-basic.artifactory myuser mytoken"
```

### What the diagnostics check

| Check | What it means if it fails |
|---|---|
| Credentials configured | Poetry does not have `http-basic.<source>` — re-paste snippet |
| URL format | URL missing `/simple` suffix — common JFrog copy-paste mistake |
| Source name match | `pyproject.toml` source name differs from Poetry credentials |
| DNS / TCP connect | VPN, firewall, or proxy issue |
| Auth probe | Bad username/token or expired identity token |
| Poetry index access | Credentials work over HTTP but Poetry cannot search the index |

## Troubleshooting

| Problem | Solution |
|---|---|
| `setup.config.json not found` | Copy `setup.config.json.example` to `setup.config.json` and customize |
| `winget not found` | Install App Installer from Microsoft Store, or install tools manually |
| `code` not recognized | Restart terminal after VS Code install, or add VS Code to PATH |
| Poetry install fails on Artifactory | Run `.\setup.ps1 -ArtifactoryTroubleshoot` and follow suggested fixes |
| Artifactory 401 / 403 | Regenerate identity token with read permission; re-paste snippet |
| Source name mismatch | Ensure `pyproject.toml` `name` matches snippet `http-basic.<name>` |
| Databricks OAuth fails | Try `auth_method: "pat"` in config and use a Personal Access Token |
| Python version mismatch | Re-run step 3: `.\setup.ps1 -Step 3` |

Logs are written to `setup.log` in this directory.

## Project Structure

```
automated_setup/
├── setup.ps1                  # Windows entry point
├── setup.sh                   # WSL / Linux / Git Bash entry point
├── setup.config.json.example  # IT configuration template
├── lib/
│   ├── ui.ps1 / ui.sh         # Prompts, logging, retry helpers
│   ├── install.ps1 / install.sh
│   ├── artifactory.ps1 / artifactory.sh  # Snippet parser + diagnostics
│   ├── corporate.ps1 / corporate.sh      # Proxy, SSL, IT whitelist, support bundle
│   ├── prerequisites.ps1 / prerequisites.sh
│   └── databricks.ps1 / databricks.sh    # Auth menu + diagnostics
└── templates/
    ├── pyproject.toml.template
    └── .pre-commit-config.yaml.template
```