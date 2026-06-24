# Dev Environment Setup Wizard

An interactive, React-CLI-inspired PowerShell wizard that walks you from a fresh Windows PowerShell session to a fully configured Databricks/Python development environment.

**Every download and package install routes through corporate Artifactory only** — no public PyPI, GitHub, or Microsoft CDN fallbacks.

## What Gets Installed

| Component | Version / Detail |
|-----------|------------------|
| Python | 3.10.11 (via pyenv-win) |
| pyenv-win | Latest mirrored zip |
| Git Bash | Git for Windows |
| Bash | Git Bash + WSL Ubuntu |
| WSL Ubuntu | Imported from Artifactory rootfs |
| Poetry | Via Artifactory PyPI |
| Databricks CLI | Via Artifactory PyPI |
| Databricks Connect | Version matched to your cluster runtime |
| `.databrickscfg` | Interactive host + token setup |
| VS Code | User-scope install |
| VS Code extensions | Databricks, Python, Poetry |
| Python libraries | pyspark, pandas, numpy, pyyaml, requests, databricks-sdk, pytest |

## Quick Start

```powershell
# 1. Open PowerShell (admin NOT required to start)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 2. Navigate to this folder
cd C:\Users\Admin\utils\quick_scripts

# 3. Run the wizard
.\Setup-DevEnvironment.ps1
```

### Resume after failure

```powershell
.\Setup-DevEnvironment.ps1 -Resume
```

### Re-check status without installing

```powershell
.\Setup-DevEnvironment.ps1 -ReportOnly
```

## Artifactory Setup

Replace `<custom_corporate_artifactory_url>` with your corporate Artifactory base URL when prompted (e.g. `https://artifactory.corp.example.com`).

### Required repositories

The wizard auto-probes common repo names, then asks you to confirm or supply names for:

| Repo type | Purpose | Common names probed |
|-----------|---------|---------------------|
| PyPI | Python packages | `pypi-remote`, `pypi-virtual`, `pypi-local` |
| Generic | Installers & archives | `generic-local`, `generic-tools` |
| VS Code extensions | `.vsix` files | `vscode-extensions`, `generic-local` |

### Required artifacts to mirror

Upload these to your Artifactory **generic** repository:

| Path in generic repo | Description |
|----------------------|-------------|
| `git/Git-2.43.0-64-bit.exe` | Git for Windows (Git Bash) |
| `wsl/ubuntu/ubuntu-22.04-wsl.tar.gz` | Ubuntu WSL rootfs tarball |
| `pyenv-win/pyenv-win.zip` | pyenv-win release zip |
| `python/3.10.11/python-3.10.11-win32.zip` | Python 3.10.11 for pyenv-win |
| `vscode/VSCodeUserSetup-x64.exe` | VS Code user installer |

Upload these to your **VS Code extension** repository (or generic):

| Path | Extension ID |
|------|--------------|
| `databricks.databricks.vsix` | `databricks.databricks` |
| `ms-python.python.vsix` | `ms-python.python` |
| `ms-python.vscode-poetry.vsix` | `ms-python.vscode-poetry` |

### Required PyPI packages (via PyPI proxy/virtual repo)

- `poetry`
- `pytest`
- `pyspark`
- `pandas`
- `numpy`
- `pyyaml`
- `requests`
- `databricks-sdk`
- `databricks-cli`
- `databricks-connect`

## How It Works

1. **Preflight** — checks PowerShell version, execution policy, disk space
2. **Artifactory** — probes repos, wizard for missing mappings, saves config
3. **Git Bash** — silent user-scope install from Artifactory
4. **WSL Ubuntu** — imports Ubuntu from Artifactory tarball (admin if WSL not enabled)
5. **pyenv-win** — extracted from Artifactory zip
6. **Python 3.10.11** — installed via pyenv-win from Artifactory mirror
7. **Poetry** — pip install from Artifactory
8. **pip/Poetry config** — locks indexes to Artifactory only
9. **Python libraries** — pip install from Artifactory
10. **Databricks CLI** — pip install from Artifactory
11. **Databricks Connect** — version prompted, pip install from Artifactory
12. **`.databrickscfg`** — interactive setup with API validation
13. **VS Code** — user-scope install from Artifactory
14. **VS Code extensions** — `.vsix` install from Artifactory
15. **Final report** — gap analysis saved to disk

Each step retries up to **3 times** on failure, then continues to the next step.

## Output Files

All state is stored in `%USERPROFILE%\.devenv-setup\`:

| File | Purpose |
|------|---------|
| `config.json` | Artifactory URL and repo names |
| `credentials.json` | API key (user-only ACL) |
| `state.json` | Per-step completion status |
| `setup.log` | Detailed log |
| `setup-report-<timestamp>.md` | Final gap report |
| `downloads/` | Cached installers |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Artifactory 401 | Check API key and repo read permissions |
| PyPI package not found | Verify package exists in PyPI virtual/proxy repo |
| WSL import fails | Run as Admin to enable WSL features; reboot if prompted |
| pyenv Python install fails | Confirm `python-3.10.11-win32.zip` is mirrored |
| VS Code `code` not found | Open a new PowerShell window (PATH updated) or re-run step 12 |
| databricks-connect version mismatch | Re-run step 10 with your cluster's Databricks runtime version |

## Project Structure

```
quick_scripts/
├── Setup-DevEnvironment.ps1      # Entry point
├── README.md
└── DevEnvSetup/
    ├── DevEnvSetup.psm1            # Module loader
    ├── Config/
    │   └── artifact-manifest.json  # Artifact catalog + probe paths
    └── Private/
        ├── Core.ps1                # State, config, PATH helpers
        ├── UI.ps1                  # Banner, prompts, colored output
        ├── Invoke-SetupStep.ps1    # Retry/verify wrapper
        ├── Artifactory.ps1         # Probe, wizard, downloads, pip config
        ├── Verify.ps1              # Per-component verification
        ├── Steps.ps1               # Step implementations
        └── Write-SetupReport.ps1   # Final gap report
```
