#Requires -Version 5.1
<#
.SYNOPSIS
  Windows host bootstrap for Microsoft DevBox.
.DESCRIPTION
  Installs WSL2, configures .wslconfig, installs host tools, then runs WSL bootstrap.
  Run in user context on first DevBox login. Some steps may require IT-approved elevation.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SetupRoot = Split-Path -Parent $PSScriptRoot
$WslDistro = "Ubuntu-24.04"
$WslConfigPath = Join-Path $env:USERPROFILE ".wslconfig"
$WslConfigExample = Join-Path $PSScriptRoot ".wslconfig.example"

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Step "DevBox Windows bootstrap starting..."

# --- WSL2 ---
Write-Step "Checking WSL..."
if (-not (Test-Command wsl)) {
    Write-Step "Installing WSL (may require admin / IT approval)..."
    wsl --install --no-distribution
} else {
    $wslList = wsl --list --quiet 2>$null
    if ($wslList -notmatch "Ubuntu") {
        Write-Step "Installing $WslDistro..."
        wsl --install -d $WslDistro
    } else {
        Write-Step "WSL distro already present"
    }
}

# Ensure WSL2 default
wsl --set-default-version 2 2>$null | Out-Null

# --- .wslconfig ---
if (-not (Test-Path $WslConfigPath)) {
    if (Test-Path $WslConfigExample) {
        Copy-Item $WslConfigExample $WslConfigPath
        Write-Step "Created $WslConfigPath from example"
        Write-Host "    Restart WSL after editing: wsl --shutdown" -ForegroundColor Yellow
    }
} else {
    Write-Step ".wslconfig already exists"
}

# --- WinGet packages (user context) ---
$packages = @(
    @{ Id = "Microsoft.AzureCLI"; Name = "Azure CLI" },
    @{ Id = "Git.Git"; Name = "Git for Windows" },
    @{ Id = "Microsoft.WindowsTerminal"; Name = "Windows Terminal" }
)

if (Test-Command winget) {
    foreach ($pkg in $packages) {
        $installed = winget list --id $pkg.Id --accept-source-agreements 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Step "Installing $($pkg.Name) via winget..."
            winget install --id $pkg.Id --accept-package-agreements --accept-source-agreements
        } else {
            Write-Step "$($pkg.Name) already installed"
        }
    }
} else {
    Write-Host "winget not available — ask IT to pre-install Azure CLI, Git, Windows Terminal" -ForegroundColor Yellow
}

# --- Cursor / VS Code (optional, user-installed) ---
$codeCmd = $null
if (Test-Command cursor) { $codeCmd = "cursor" }
elseif (Test-Command code) { $codeCmd = "code" }

if ($codeCmd) {
    Write-Step "Installing IDE extensions from $SetupRoot/ide/extensions.txt..."
    $extFile = Join-Path $SetupRoot "ide\extensions.txt"
    if (Test-Path $extFile) {
        Get-Content $extFile | Where-Object { $_ -and $_ -notmatch '^\s*#' } | ForEach-Object {
            & $codeCmd --install-extension $_ --force 2>$null
        }
    }
} else {
    Write-Host "Cursor/VS Code not found — install manually and run ide extension install later" -ForegroundColor Yellow
}

# --- Run WSL bootstrap ---
Write-Step "Running WSL bootstrap..."
$wslSetupPath = (wsl -d $WslDistro wslpath -a $SetupRoot 2>$null)
if ($wslSetupPath) {
    wsl -d $WslDistro bash "$wslSetupPath/wsl/bootstrap.sh"
} else {
    Write-Host "Could not resolve WSL path. After Ubuntu is ready, run inside WSL:" -ForegroundColor Yellow
    Write-Host "  bash ~/tools/devBoxSetup/wsl/bootstrap.sh" -ForegroundColor Yellow
}

Write-Step "Windows bootstrap complete."
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Open Windows Terminal → Ubuntu (WSL)"
Write-Host "  2. source ~/.bashrc"
Write-Host "  3. az login"
Write-Host "  4. databricks auth login --host https://adb-<id>.azuredatabricks.net"
Write-Host "  5. bash ~/tools/devBoxSetup/scripts/doctor.sh"