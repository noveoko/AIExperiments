#Requires -Version 5.1
<#
.SYNOPSIS
    Idiot-proof dev environment setup wizard (Artifactory-only).
.DESCRIPTION
    Interactive step-by-step installer for Python, pyenv-win, Git Bash, WSL Ubuntu,
    Poetry, Databricks CLI/Connect, VS Code, and required Python libraries.
    All downloads and packages route through corporate Artifactory.
.PARAMETER Resume
    Resume from last session, skipping completed steps.
.PARAMETER ReportOnly
    Generate verification report without running install steps.
.PARAMETER Elevated
    Internal flag used when re-launching for admin elevation.
.EXAMPLE
    .\Setup-DevEnvironment.ps1
.EXAMPLE
    .\Setup-DevEnvironment.ps1 -Resume
.EXAMPLE
    .\Setup-DevEnvironment.ps1 -ReportOnly
#>
[CmdletBinding()]
param(
    [switch]$Resume,
    [switch]$ReportOnly,
    [switch]$Elevated
)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModulePath = Join-Path $ScriptDir 'DevEnvSetup'

Import-Module $ModulePath -Force
Initialize-SetupEnvironment

$TotalSteps = 14
$script:SetupConfig = $null
$script:SetupCredentials = $null
$Manifest = Get-Manifest

Write-SetupBanner

if ($ReportOnly) {
    $script:SetupConfig = Get-SetupConfig
    if (-not $script:SetupConfig) {
        Write-SetupFailure 'No saved Artifactory config. Run setup first.'
        exit 1
    }
    $allOk = Invoke-StepFinalReport -Config $script:SetupConfig
    exit $(if ($allOk) { 0 } else { 1 })
}

$startStep = if ($Resume) {
    $state = Get-SetupState
    [Math]::Min($state.lastStep + 1, $TotalSteps)
}
else {
    0
}

if (-not $Resume) {
    if (-not (Read-SetupYesNo -Message 'Ready to begin setup? [Y/n]' -Default 'Y')) {
        Write-SetupInfo 'Setup cancelled.'
        exit 0
    }
}

$stepResults = @()

# Step 0: Preflight
if ($startStep -le 0) {
    $stepResults += Invoke-SetupStep -StepNumber 0 -TotalSteps $TotalSteps `
        -Name 'Preflight' -Title 'Preflight Checks' `
        -Action { Invoke-StepPreflight } `
        -Verify { Test-StepPreflight } `
        -FailureHint 'Ensure PowerShell 5.1+ and set ExecutionPolicy RemoteSigned for CurrentUser.' `
        -SkipIfCompleted:(!$Resume)
}

# Step 1: Artifactory
if ($startStep -le 1) {
    $stepResults += Invoke-SetupStep -StepNumber 1 -TotalSteps $TotalSteps `
        -Name 'Artifactory' -Title 'Artifactory Configuration' `
        -Action { Invoke-StepArtifactory -Manifest $Manifest } `
        -Verify { Test-StepArtifactory } `
        -FailureHint 'Verify Artifactory URL, API key permissions, and PyPI repo name.' `
        -SkipIfCompleted:(!$Resume)
    $script:SetupConfig = Get-SetupConfig
    $script:SetupCredentials = Get-SetupCredentials
}

if (-not $script:SetupConfig) {
    $script:SetupConfig = Get-SetupConfig
    $script:SetupCredentials = Get-SetupCredentials
}
if (-not $script:SetupConfig -or -not $script:SetupCredentials) {
    Write-SetupFailure 'Artifactory must be configured before continuing. Re-run with -Resume.'
    exit 1
}

# Step 2: Git Bash
if ($startStep -le 2) {
    $stepResults += Invoke-SetupStep -StepNumber 2 -TotalSteps $TotalSteps `
        -Name 'GitBash' -Title 'Installing Git Bash' `
        -Action { Invoke-StepGitBash -Config $script:SetupConfig -Credentials $script:SetupCredentials -Manifest $Manifest } `
        -Verify { Test-GitBashInstalled } `
        -FailureHint 'Mirror Git-2.x-64-bit.exe to Artifactory generic repo at git/ path.' `
        -SkipIfCompleted
}

# Step 3: WSL Ubuntu
if ($startStep -le 3) {
    $stepResults += Invoke-SetupStep -StepNumber 3 -TotalSteps $TotalSteps `
        -Name 'WSLUbuntu' -Title 'Installing WSL Ubuntu' `
        -Action { Invoke-StepWSLUbuntu -Config $script:SetupConfig -Credentials $script:SetupCredentials -Manifest $Manifest } `
        -Verify { Test-WSLUbuntuInstalled } `
        -FailureHint 'Enable WSL (may need admin + reboot). Mirror Ubuntu rootfs tarball to Artifactory.' `
        -SkipIfCompleted
}

# Step 4: pyenv-win
if ($startStep -le 4) {
    $stepResults += Invoke-SetupStep -StepNumber 4 -TotalSteps $TotalSteps `
        -Name 'PyenvWin' -Title 'Installing pyenv-win' `
        -Action { Invoke-StepPyenvWin -Config $script:SetupConfig -Credentials $script:SetupCredentials -Manifest $Manifest } `
        -Verify { Test-PyenvWinInstalled } `
        -FailureHint 'Mirror pyenv-win.zip to Artifactory generic repo.' `
        -SkipIfCompleted
}

# Step 5: Python 3.10.11
if ($startStep -le 5) {
    $stepResults += Invoke-SetupStep -StepNumber 5 -TotalSteps $TotalSteps `
        -Name 'Python' -Title 'Installing Python 3.10.11' `
        -Action { Invoke-StepPython -Config $script:SetupConfig -Credentials $script:SetupCredentials -Manifest $Manifest } `
        -Verify { Test-Python311Installed } `
        -FailureHint 'Mirror python-3.10.11-win32.zip to Artifactory for pyenv-win.' `
        -SkipIfCompleted
}

# Step 6: Poetry
if ($startStep -le 6) {
    $stepResults += Invoke-SetupStep -StepNumber 6 -TotalSteps $TotalSteps `
        -Name 'Poetry' -Title 'Installing Poetry' `
        -Action { Invoke-StepPoetry -Config $script:SetupConfig } `
        -Verify { Test-PoetryInstalled } `
        -FailureHint 'Ensure poetry is available in Artifactory PyPI repo.' `
        -SkipIfCompleted
}

# Step 7: Package index config
if ($startStep -le 7) {
    $stepResults += Invoke-SetupStep -StepNumber 7 -TotalSteps $TotalSteps `
        -Name 'PackageIndex' -Title 'Locking pip/Poetry to Artifactory' `
        -Action { Invoke-StepPackageIndexConfig -Config $script:SetupConfig } `
        -Verify { Test-StepPackageIndexConfig } `
        -FailureHint 'Check write access to %APPDATA%\pip and %APPDATA%\pypoetry.' `
        -SkipIfCompleted
}

# Step 8: Python libraries
if ($startStep -le 8) {
    $stepResults += Invoke-SetupStep -StepNumber 8 -TotalSteps $TotalSteps `
        -Name 'PythonPackages' -Title 'Installing Python Libraries' `
        -Action { Invoke-StepPythonPackages -Config $script:SetupConfig -Manifest $Manifest } `
        -Verify { Test-StepPythonPackages } `
        -FailureHint 'Verify pyspark, pandas, numpy, pyyaml, requests, databricks-sdk, pytest in PyPI mirror.' `
        -SkipIfCompleted
}

# Step 9: Databricks CLI
if ($startStep -le 9) {
    $stepResults += Invoke-SetupStep -StepNumber 9 -TotalSteps $TotalSteps `
        -Name 'DatabricksCli' -Title 'Installing Databricks CLI' `
        -Action { Invoke-StepDatabricksCli -Config $script:SetupConfig } `
        -Verify { Test-DatabricksCliInstalled } `
        -FailureHint 'Ensure databricks-cli is in Artifactory PyPI repo.' `
        -SkipIfCompleted
}

# Step 10: Databricks Connect
if ($startStep -le 10) {
    $stepResults += Invoke-SetupStep -StepNumber 10 -TotalSteps $TotalSteps `
        -Name 'DatabricksConnect' -Title 'Installing Databricks Connect' `
        -Action { Invoke-StepDatabricksConnect -Config $script:SetupConfig } `
        -Verify { Test-DatabricksConnectInstalled } `
        -FailureHint 'Match databricks-connect version to your cluster Databricks runtime.' `
        -SkipIfCompleted
}

# Step 11: .databrickscfg
if ($startStep -le 11) {
    $stepResults += Invoke-SetupStep -StepNumber 11 -TotalSteps $TotalSteps `
        -Name 'DatabricksCfg' -Title 'Configuring .databrickscfg' `
        -Action { Invoke-StepDatabricksCfg -Config $script:SetupConfig -Credentials $script:SetupCredentials } `
        -Verify { Test-DatabricksCfgConfigured } `
        -FailureHint 'Provide valid Databricks workspace host (https://...) and personal access token.' `
        -SkipIfCompleted
}

# Step 12: VS Code
if ($startStep -le 12) {
    $stepResults += Invoke-SetupStep -StepNumber 12 -TotalSteps $TotalSteps `
        -Name 'VSCode' -Title 'Installing VS Code' `
        -Action { Invoke-StepVSCode -Config $script:SetupConfig -Credentials $script:SetupCredentials -Manifest $Manifest } `
        -Verify { Test-VSCodeInstalled } `
        -FailureHint 'Mirror VSCodeUserSetup-x64.exe to Artifactory generic repo.' `
        -SkipIfCompleted
}

# Step 13: VS Code extensions
if ($startStep -le 13) {
    $stepResults += Invoke-SetupStep -StepNumber 13 -TotalSteps $TotalSteps `
        -Name 'VSCodeExtensions' -Title 'Installing VS Code Extensions' `
        -Action { Invoke-StepVSCodeExtensions -Config $script:SetupConfig -Credentials $script:SetupCredentials -Manifest $Manifest } `
        -Verify { Test-VSCodeExtensionsInstalled } `
        -FailureHint 'Mirror .vsix files: databricks.databricks, ms-python.python, ms-python.vscode-poetry.' `
        -SkipIfCompleted
}

# Step 14: Final report
$stepResults += Invoke-SetupStep -StepNumber 14 -TotalSteps $TotalSteps `
    -Name 'FinalReport' -Title 'Generating Final Report' `
    -Action { Invoke-StepFinalReport -Config $script:SetupConfig } `
    -Verify { $true } `
    -SkipIfCompleted:$false -Force

$failed = @($stepResults | Where-Object { $_.Success -eq $false }).Count
if ($failed -gt 0) {
    Write-SetupWarning "$failed step(s) failed. See report and setup.log, then re-run with -Resume."
    exit 1
}

Write-SetupSuccess 'Setup complete!'
exit 0
