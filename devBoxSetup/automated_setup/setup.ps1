#Requires -Version 5.1
<#
.SYNOPSIS
  Interactive development machine setup for Windows (+ optional WSL).
#>
[CmdletBinding()]
param(
    [int]$Step = 1,
    [switch]$DryRun,
    [switch]$VerifyOnly,
    [switch]$ArtifactoryTroubleshoot,
    [switch]$ArtifactorySetup,
    [string]$ArtifactorySnippet,
    [switch]$ArtifactoryVerbose,
    [switch]$CorporatePreflight,
    [switch]$DatabricksTroubleshoot,
    [switch]$DatabricksSetup,
    [switch]$GenerateItWhitelist,
    [switch]$GenerateSupportBundle
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$ConfigPath = Join-Path $RepoRoot "setup.config.json"
$LogPath = Join-Path $RepoRoot "setup.log"

. (Join-Path $RepoRoot "lib\ui.ps1")
. (Join-Path $RepoRoot "lib\install.ps1")
. (Join-Path $RepoRoot "lib\artifactory.ps1")
. (Join-Path $RepoRoot "lib\corporate.ps1")
. (Join-Path $RepoRoot "lib\prerequisites.ps1")
. (Join-Path $RepoRoot "lib\databricks.ps1")

Initialize-SetupUi -LogPath $LogPath -DryRun:$DryRun

Write-Host ""
Write-Host "  Development Machine Setup" -ForegroundColor Cyan
Write-Host "  Windows + optional WSL" -ForegroundColor DarkGray
Write-Host ""

function Get-ConfigOrExit {
    if (-not (Test-Path $ConfigPath)) {
        Write-Fail "setup.config.json not found. Copy setup.config.json.example first."
        exit 1
    }
    return Get-SetupConfig -ConfigPath $ConfigPath
}

if ($VerifyOnly) {
    $config = Get-ConfigOrExit
    $projectDir = Expand-HomePath $config.project.directory
    $results = Get-VerificationResultsWindows -Config $config -ProjectDir $projectDir
    Write-SummaryTable -Results $results
    exit 0
}

if ($GenerateItWhitelist) {
    $config = Get-ConfigOrExit
    $out = Join-Path $RepoRoot "it-whitelist-request.txt"
    Export-ItWhitelist -Config $config -OutputPath $out | Out-Null
    exit 0
}

if ($GenerateSupportBundle) {
    $config = Get-ConfigOrExit
    $projectDir = Expand-HomePath $config.project.directory
    Export-SupportBundle -Config $config -ConfigPath $ConfigPath -RepoRoot $RepoRoot -ProjectDir $projectDir | Out-Null
    exit 0
}

if ($ArtifactoryTroubleshoot -or $ArtifactorySetup -or $ArtifactorySnippet) {
    $config = Get-ConfigOrExit
    $projectDir = Expand-HomePath $config.project.directory
    $mode = if ($ArtifactoryTroubleshoot) { "troubleshoot" }
            elseif ($ArtifactorySnippet) { "paste" }
            else { "menu" }
    $ok = Invoke-ArtifactorySetup -Config $config -ConfigPath $ConfigPath -ProjectDir $projectDir `
        -SnippetText $ArtifactorySnippet -Mode $mode -Verbose:$ArtifactoryVerbose
    exit $(if ($ok) { 0 } else { 1 })
}

if ($DatabricksTroubleshoot -or $DatabricksSetup) {
    $config = Get-ConfigOrExit
    $mode = if ($DatabricksTroubleshoot) { "troubleshoot" } else { "menu" }
    $ok = Invoke-DatabricksSetup -Config $config -Mode $mode
    exit $(if ($ok) { 0 } else { 1 })
}

if ($CorporatePreflight) {
    $config = Get-ConfigOrExit
    Invoke-PrerequisitesChecks -ConfigPath $ConfigPath -Config $config | Out-Null
    Invoke-CorporateNetworkSetup -Config $config | Out-Null
    exit 0
}

if (-not (Test-Path $LogPath)) {
    New-Item -ItemType File -Path $LogPath -Force | Out-Null
}

$config = $null
$projectDir = $null

if ($Step -gt 1 -and (Test-Path $ConfigPath)) {
    $config = Get-SetupConfig -ConfigPath $ConfigPath
    $projectDir = Expand-HomePath $config.project.directory
}

function Run-Step {
    param(
        [int]$Number,
        [string]$Title,
        [string]$Description,
        [scriptblock]$Action
    )
    if ($Number -lt $Step) { return }
    Write-Step -Number $Number -Title $Title -Description $Description
    if (-not (Confirm-OrSkip -Prompt "Proceed with this step?" -DefaultYes)) {
        Write-Warn "Skipped step $Number."
        return
    }
    & $Action
}

try {
    Run-Step 1 "Prerequisites" "Confirm VPN, tokens, and permissions before we install anything." {
        Test-PreflightWindows -ConfigPath $ConfigPath | Out-Null
        $script:config = Get-SetupConfig -ConfigPath $ConfigPath
        Invoke-PrerequisitesChecks -ConfigPath $ConfigPath -Config $config | Out-Null
        Write-Success "Prerequisites complete."
    }

    Run-Step 2 "Network, Proxy and SSL" "Configure corporate proxy and CA certificates so downloads can reach internal services." {
        Invoke-CorporateNetworkSetup -Config $config | Out-Null
    }

    Run-Step 3 "Bash Shell" "Bash lets you run Linux-style commands. On Windows we install Git Bash." {
        Install-GitBash | Out-Null
    }

    Run-Step 4 "Python $($config.python.version)" "Python is the programming language used for Databricks development." {
        Install-PyenvWin -PythonVersion $config.python.version | Out-Null
    }

    Run-Step 5 "Poetry" "Poetry manages Python packages and virtual environments for your project." {
        Install-PoetryWindows | Out-Null
    }

    Run-Step 6 "Visual Studio Code" "VS Code is the recommended editor for Databricks development." {
        Install-VSCodeWindows | Out-Null
    }

    Run-Step 7 "Databricks CLI" "The Databricks CLI lets you manage workspaces, clusters, and deployments from your terminal." {
        Install-DatabricksCliWindows | Out-Null
    }

    Run-Step 8 "Artifactory Credentials" "Artifactory is your organization's private package registry. We configure Poetry to authenticate." {
        $dir = if ($projectDir) { $projectDir } else { Expand-HomePath $config.project.directory }
        Invoke-ArtifactorySetup -Config $config -ConfigPath $ConfigPath -ProjectDir $dir -Verbose:$ArtifactoryVerbose | Out-Null
    }

    Run-Step 9 "Databricks Authentication" "Connect your computer to your Databricks workspace. PAT is recommended in corporate environments." {
        $dbMode = if ($config.databricks.auth_method -eq "pat") { "pat" } else { "menu" }
        Invoke-DatabricksSetup -Config $config -Mode $dbMode | Out-Null
    }

    Run-Step 10 "Poetry Project" "We create a starter project with all required Python dependencies." {
        $script:projectDir = New-PoetryProject -Config $config -RepoRoot $RepoRoot
    }

    Run-Step 11 "VS Code Extensions" "The Databricks extension adds workspace integration directly in VS Code." {
        Install-VSCodeExtensions -Extensions $config.vscode.extensions | Out-Null
    }

    Run-Step 12 "pre-commit Hooks" "pre-commit runs code quality checks automatically before each commit." {
        if ($projectDir) {
            Install-PreCommitHooks -ProjectDir $projectDir -Config $config | Out-Null
        }
    }

    Run-Step 13 "databricks-connect Validation" "Verify your machine can reach the configured Databricks cluster." {
        if ($projectDir) {
            Test-DatabricksConnectCluster -Config $config -ProjectDir $projectDir | Out-Null
        }
    }

    Run-Step 14 "WSL Setup (optional)" "Set up the same Python toolchain inside WSL for Linux-based workflows." {
        if ($config.wsl.run_wsl_setup) {
            $choice = Confirm-OrSkip -Prompt "Also set up tools inside WSL ($($config.wsl.distro))?" -DefaultYes
            if ($choice -eq $true) {
                Invoke-WslSetup -RepoRoot $RepoRoot -Distro $config.wsl.distro | Out-Null
            }
            elseif ($choice -eq "skip") {
                Write-Warn "WSL setup skipped."
            }
        }
        else {
            Write-Info "WSL setup disabled in config (wsl.run_wsl_setup = false)."
        }
    }

    Run-Step 15 "Verification" "Final check that everything is installed and configured correctly." {
        if (-not $projectDir) {
            $projectDir = Expand-HomePath $config.project.directory
        }
        $results = Get-VerificationResultsWindows -Config $config -ProjectDir $projectDir
        Write-SummaryTable -Results $results
        $failures = $results | Where-Object { $_.Status -eq "FAIL" }
        if ($failures.Count -gt 0) {
            Write-Host ""
            Write-Warn "Some components need attention. Re-run with -Step N to retry a specific step."
            Write-Info "Log file: $LogPath"
            exit 1
        }
        Write-Host ""
        Write-Success "Setup complete! Your project is at: $projectDir"
        Write-Info "Activate the environment: cd `"$projectDir`"; poetry shell"
    }

    Run-Step 16 "IT Export (optional)" "Generate files to share with IT or helpdesk if something still fails." {
        if (Confirm-OrSkip -Prompt "Export IT whitelist request file?" -DefaultYes) {
            Export-ItWhitelist -Config $config -OutputPath (Join-Path $RepoRoot "it-whitelist-request.txt") | Out-Null
        }
        if (Confirm-OrSkip -Prompt "Export support bundle for helpdesk?" -DefaultYes) {
            if (-not $projectDir) { $projectDir = Expand-HomePath $config.project.directory }
            Export-SupportBundle -Config $config -ConfigPath $ConfigPath -RepoRoot $RepoRoot -ProjectDir $projectDir | Out-Null
        }
    }
}
catch {
    Write-Fail $_.Exception.Message
    Write-Info "Log file: $LogPath"
    Write-Info "Resume with: .\setup.ps1 -Step <step-number>"
    Write-Info "IT help: .\setup.ps1 -GenerateItWhitelist or -GenerateSupportBundle"
    exit 1
}