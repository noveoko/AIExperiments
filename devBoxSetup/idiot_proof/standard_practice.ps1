#Requires -Version 5.1
<#
.SYNOPSIS
    Standard practice dev environment setup (Artifactory for Python only).
.DESCRIPTION
    Same toolchain as Setup-DevEnvironment.ps1, but:
      - Python/pip packages -> Corporate Artifactory (PyPI) only
      - All other dependencies -> Trusted upstream (python.org, GitHub, Microsoft, VS Marketplace)
    Generates a detailed dependency source report with risk ratings at the end.
.PARAMETER Resume
    Resume from last session.
.PARAMETER ReportOnly
    Regenerate dependency report from ledger without installing.
.EXAMPLE
    .\standard_practice.ps1
.EXAMPLE
    .\standard_practice.ps1 -Resume
.EXAMPLE
    .\standard_practice.ps1 -ReportOnly
#>
[CmdletBinding()]
param(
    [switch]$Resume,
    [switch]$ReportOnly
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module (Join-Path $ScriptDir 'DevEnvSetup') -Force

Initialize-StandardPracticeEnvironment

$TotalSteps = 14
$script:SetupConfig = $null
$script:SetupCredentials = $null

Write-StandardPracticeBanner

if ($ReportOnly) {
    $script:SetupConfig = Get-SetupConfig
    if (-not $script:SetupConfig) {
        Write-SetupFailure 'No saved config. Run standard_practice.ps1 first.'
        exit 1
    }
    $verification = Invoke-ComponentVerification -Config $script:SetupConfig
    $ok = Write-StandardPracticeDependencyReport -Config $script:SetupConfig -VerificationResults $verification
    exit $(if ($ok) { 0 } else { 1 })
}

$startStep = if ($Resume) {
    $state = Get-SetupState
    [Math]::Min($state.lastStep + 1, $TotalSteps)
} else { 0 }

if (-not $Resume) {
    if (-not (Read-SetupYesNo -Message 'Begin standard practice setup? [Y/n]' -Default 'Y')) {
        Write-SetupInfo 'Setup cancelled.'
        exit 0
    }
}

$stepResults = @()

if ($startStep -le 0) {
    $stepResults += Invoke-SetupStep -StepNumber 0 -TotalSteps $TotalSteps `
        -Name 'Preflight' -Title 'Preflight Checks' `
        -Action { Invoke-StepPreflight } `
        -Verify { Test-StepPreflight } `
        -FailureHint 'Ensure PowerShell 5.1+ and RemoteSigned execution policy.' `
        -SkipIfCompleted:(!$Resume)
}

if ($startStep -le 1) {
    $stepResults += Invoke-SetupStep -StepNumber 1 -TotalSteps $TotalSteps `
        -Name 'ArtifactoryPyPI' -Title 'Artifactory PyPI Configuration (Python only)' `
        -Action {
            $script:SetupConfig = Get-StandardPracticeConfig
            $script:SetupCredentials = Get-SetupCredentials
            return $true
        } `
        -Verify { Test-StepArtifactory } `
        -FailureHint 'Verify Artifactory URL, API key, and PyPI repo name.' `
        -SkipIfCompleted:(!$Resume)
    $script:SetupConfig = Get-SetupConfig
    $script:SetupCredentials = Get-SetupCredentials
}

if (-not $script:SetupConfig) {
    $script:SetupConfig = Get-SetupConfig
    $script:SetupCredentials = Get-SetupCredentials
}
if (-not $script:SetupConfig) {
    Write-SetupFailure 'Artifactory PyPI must be configured. Re-run with -Resume.'
    exit 1
}

if ($startStep -le 2) {
    $stepResults += Invoke-SetupStep -StepNumber 2 -TotalSteps $TotalSteps `
        -Name 'GitBash' -Title 'Installing Git Bash (trusted: GitHub)' `
        -Action { Invoke-SPStepGitBash } `
        -Verify { Test-GitBashInstalled } `
        -FailureHint 'Check network access to github.com/releases.' `
        -SkipIfCompleted
}

if ($startStep -le 3) {
    $stepResults += Invoke-SetupStep -StepNumber 3 -TotalSteps $TotalSteps `
        -Name 'WSLUbuntu' -Title 'Installing WSL Ubuntu (trusted: Microsoft)' `
        -Action { Invoke-SPStepWSLUbuntu } `
        -Verify { Test-WSLUbuntuInstalled } `
        -FailureHint 'Enable WSL features; reboot if needed after dism.' `
        -SkipIfCompleted
}

if ($startStep -le 4) {
    $stepResults += Invoke-SetupStep -StepNumber 4 -TotalSteps $TotalSteps `
        -Name 'PyenvWin' -Title 'Installing pyenv-win (trusted: GitHub)' `
        -Action { Invoke-SPStepPyenvWin } `
        -Verify { Test-PyenvWinInstalled } `
        -FailureHint 'Check network access to github.com/pyenv-win.' `
        -SkipIfCompleted
}

if ($startStep -le 5) {
    $stepResults += Invoke-SetupStep -StepNumber 5 -TotalSteps $TotalSteps `
        -Name 'Python' -Title 'Installing Python 3.10.11 (trusted: python.org)' `
        -Action { Invoke-SPStepPython } `
        -Verify { Test-Python311Installed } `
        -FailureHint 'Check network access to python.org/ftp.' `
        -SkipIfCompleted
}

if ($startStep -le 6) {
    $stepResults += Invoke-SetupStep -StepNumber 6 -TotalSteps $TotalSteps `
        -Name 'Poetry' -Title 'Installing Poetry (Artifactory PyPI)' `
        -Action { Invoke-SPStepPoetry -Config $script:SetupConfig } `
        -Verify { Test-PoetryInstalled } `
        -FailureHint 'Ensure poetry is in Artifactory PyPI repo.' `
        -SkipIfCompleted
}

if ($startStep -le 7) {
    $stepResults += Invoke-SetupStep -StepNumber 7 -TotalSteps $TotalSteps `
        -Name 'PackageIndex' -Title 'Locking pip/Poetry to Artifactory' `
        -Action { Invoke-StepPackageIndexConfig -Config $script:SetupConfig } `
        -Verify { Test-StepPackageIndexConfig } `
        -FailureHint 'Check write access to pip/poetry config dirs.' `
        -SkipIfCompleted
}

if ($startStep -le 8) {
    $stepResults += Invoke-SetupStep -StepNumber 8 -TotalSteps $TotalSteps `
        -Name 'PythonPackages' -Title 'Installing Python Libraries (Artifactory PyPI)' `
        -Action { Invoke-SPStepPythonPackages -Config $script:SetupConfig } `
        -Verify { Test-StepPythonPackages } `
        -FailureHint 'Verify packages exist in Artifactory PyPI mirror.' `
        -SkipIfCompleted
}

if ($startStep -le 9) {
    $stepResults += Invoke-SetupStep -StepNumber 9 -TotalSteps $TotalSteps `
        -Name 'DatabricksCli' -Title 'Installing Databricks CLI (Artifactory PyPI)' `
        -Action { Invoke-SPStepDatabricksCli -Config $script:SetupConfig } `
        -Verify { Test-DatabricksCliInstalled } `
        -FailureHint 'Ensure databricks-cli is in Artifactory PyPI.' `
        -SkipIfCompleted
}

if ($startStep -le 10) {
    $stepResults += Invoke-SetupStep -StepNumber 10 -TotalSteps $TotalSteps `
        -Name 'DatabricksConnect' -Title 'Installing Databricks Connect (Artifactory PyPI)' `
        -Action { Invoke-SPStepDatabricksConnect -Config $script:SetupConfig } `
        -Verify { Test-DatabricksConnectInstalled } `
        -FailureHint 'Match databricks-connect version to cluster runtime.' `
        -SkipIfCompleted
}

if ($startStep -le 11) {
    $stepResults += Invoke-SetupStep -StepNumber 11 -TotalSteps $TotalSteps `
        -Name 'DatabricksCfg' -Title 'Configuring .databrickscfg' `
        -Action { Invoke-SPStepDatabricksCfg } `
        -Verify { Test-DatabricksCfgConfigured } `
        -FailureHint 'Provide valid Databricks host and token.' `
        -SkipIfCompleted
}

if ($startStep -le 12) {
    $stepResults += Invoke-SetupStep -StepNumber 12 -TotalSteps $TotalSteps `
        -Name 'VSCode' -Title 'Installing VS Code (trusted: Microsoft)' `
        -Action { Invoke-SPStepVSCode } `
        -Verify { Test-VSCodeInstalled } `
        -FailureHint 'Check network access to code.visualstudio.com.' `
        -SkipIfCompleted
}

if ($startStep -le 13) {
    $stepResults += Invoke-SetupStep -StepNumber 13 -TotalSteps $TotalSteps `
        -Name 'VSCodeExtensions' -Title 'Installing VS Code Extensions (trusted: Marketplace)' `
        -Action { Invoke-SPStepVSCodeExtensions } `
        -Verify { Test-VSCodeExtensionsInstalled } `
        -FailureHint 'Check network access to marketplace.visualstudio.com.' `
        -SkipIfCompleted
}

$stepResults += Invoke-SetupStep -StepNumber 14 -TotalSteps $TotalSteps `
    -Name 'DependencyReport' -Title 'Generating Dependency Source Report' `
    -Action { Invoke-SPStepFinalReport -Config $script:SetupConfig -StepResults $stepResults } `
    -Verify { $true } -Force

$failed = @($stepResults | Where-Object { $_.Success -eq $false }).Count
if ($failed -gt 0) {
    Write-SetupWarning "$failed step(s) failed. See dependency report and setup.log."
    exit 1
}

Write-SetupSuccess 'Standard practice setup complete!'
exit 0
