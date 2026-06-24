#Requires -Version 5.1
<#
.SYNOPSIS
    Standard practice dev environment setup (Artifactory for Python only).
.DESCRIPTION
    Self-contained script. Python/pip packages route through Corporate Artifactory (PyPI);
    all other dependencies download from trusted upstream sources.
    Persistence uses standard user-profile locations:
      ~/.standard-practice/     setup state, config, credentials, ledger, logs
      %APPDATA%\pip\pip.ini    pip index (Artifactory)
      %APPDATA%\pypoetry\      poetry repository config
      ~/.databrickscfg          Databricks credentials
      User PATH env var         pyenv, Git, VS Code
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
$script:SelfPath = $MyInvocation.MyCommand.Path

#region Persistence paths (user profile)
$script:StandardPracticeDataDir = Join-Path $env:USERPROFILE '.standard-practice'
$script:SetupDataDir = $script:StandardPracticeDataDir
$script:ConfigPath = Join-Path $script:SetupDataDir 'config.json'
$script:CredentialsPath = Join-Path $script:SetupDataDir 'credentials.json'
$script:StatePath = Join-Path $script:SetupDataDir 'state.json'
$script:LogPath = Join-Path $script:SetupDataDir 'setup.log'
#endregion

#region Embedded trusted sources
$script:TrustedSourcesJson = @'
{
  "version": "1.0.0",
  "description": "Trusted upstream sources for non-Python dependencies (standard practice mode)",
  "sources": {
    "git-for-windows": {
      "name": "Git for Windows (Git Bash)",
      "category": "system",
      "publisher": "Git for Windows Project",
      "sourceUrl": "https://github.com/git-for-windows/git/releases/download/v2.43.0.windows.1/Git-2.43.0-64-bit.exe",
      "riskRating": "Low",
      "riskRationale": "Official Git for Windows release on GitHub",
      "artifactory": "no"
    },
    "wsl-ubuntu": {
      "name": "WSL Ubuntu",
      "category": "system",
      "publisher": "Canonical / Microsoft",
      "sourceUrl": "wsl --install -d Ubuntu (Microsoft WSL distribution service)",
      "riskRating": "Low",
      "riskRationale": "Official Microsoft WSL distribution channel",
      "artifactory": "no"
    },
    "pyenv-win": {
      "name": "pyenv-win",
      "category": "toolchain",
      "publisher": "pyenv-win (GitHub)",
      "sourceUrl": "https://github.com/pyenv-win/pyenv-win/archive/master.zip",
      "riskRating": "Low",
      "riskRationale": "Official pyenv-win repository release archive",
      "artifactory": "no"
    },
    "python-3.10.11": {
      "name": "Python 3.10.11",
      "category": "runtime",
      "publisher": "Python Software Foundation",
      "sourceUrl": "https://www.python.org/ftp/python/3.10.11/python-3.10.11-win32.zip",
      "riskRating": "Low",
      "riskRationale": "Official python.org distribution",
      "artifactory": "no"
    },
    "vscode": {
      "name": "Visual Studio Code",
      "category": "ide",
      "publisher": "Microsoft",
      "sourceUrl": "https://code.visualstudio.com/sha/download?build=stable&os=win32-x64-user",
      "riskRating": "Low",
      "riskRationale": "Official Microsoft VS Code download endpoint",
      "artifactory": "no"
    },
    "ext-databricks": {
      "name": "VS Code Databricks extension",
      "category": "vscode-extension",
      "publisher": "Databricks",
      "sourceUrl": "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/databricks/vsextensions/databricks/latest/vspackage",
      "extensionId": "databricks.databricks",
      "riskRating": "Low",
      "riskRationale": "Official Visual Studio Marketplace publisher endpoint",
      "artifactory": "no"
    },
    "ext-python": {
      "name": "VS Code Python extension",
      "category": "vscode-extension",
      "publisher": "Microsoft",
      "sourceUrl": "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/ms-python/vsextensions/python/latest/vspackage",
      "extensionId": "ms-python.python",
      "riskRating": "Low",
      "riskRationale": "Official Visual Studio Marketplace publisher endpoint",
      "artifactory": "no"
    },
    "ext-poetry": {
      "name": "VS Code Poetry extension",
      "category": "vscode-extension",
      "publisher": "Microsoft",
      "sourceUrl": "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/ms-python/vsextensions/vscode-poetry/latest/vspackage",
      "extensionId": "ms-python.vscode-poetry",
      "riskRating": "Low",
      "riskRationale": "Official Visual Studio Marketplace publisher endpoint",
      "artifactory": "no"
    }
  },
  "pypiPackages": [
    { "name": "poetry", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "pytest", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "pyspark", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "pandas", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "numpy", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "pyyaml", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "requests", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "databricks-sdk", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "databricks-cli", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" },
    { "name": "databricks-connect", "category": "python-package", "riskRating": "Low", "riskRationale": "Corporate Artifactory PyPI proxy - controlled supply chain" }
  ]
}
'@

$script:VerifyComponents = @(
    [pscustomobject]@{ id = 'git-bash'; name = 'Git Bash'; step = 2 }
    [pscustomobject]@{ id = 'wsl-ubuntu'; name = 'WSL Ubuntu'; step = 3 }
    [pscustomobject]@{ id = 'pyenv-win'; name = 'pyenv-win'; step = 4 }
    [pscustomobject]@{ id = 'python-3.10.11'; name = 'Python 3.10.11'; step = 5 }
    [pscustomobject]@{ id = 'poetry'; name = 'Poetry'; step = 6 }
    [pscustomobject]@{ id = 'pytest'; name = 'pytest'; step = 8 }
    [pscustomobject]@{ id = 'pyspark'; name = 'pyspark'; step = 8 }
    [pscustomobject]@{ id = 'pandas'; name = 'pandas'; step = 8 }
    [pscustomobject]@{ id = 'numpy'; name = 'numpy'; step = 8 }
    [pscustomobject]@{ id = 'pyyaml'; name = 'pyyaml'; step = 8 }
    [pscustomobject]@{ id = 'requests'; name = 'requests'; step = 8 }
    [pscustomobject]@{ id = 'databricks-sdk'; name = 'databricks-sdk'; step = 8 }
    [pscustomobject]@{ id = 'databricks-cli'; name = 'Databricks CLI'; step = 9 }
    [pscustomobject]@{ id = 'databricks-connect'; name = 'Databricks Connect'; step = 10 }
    [pscustomobject]@{ id = 'databrickscfg'; name = '.databrickscfg'; step = 11 }
    [pscustomobject]@{ id = 'vscode'; name = 'VS Code'; step = 12 }
    [pscustomobject]@{ id = 'vscode-extensions'; name = 'VS Code Extensions'; step = 13 }
)
#endregion

#region Library
function Write-SetupBanner {
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host '       Dev Environment Setup  (Corporate Artifactory)        ' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  This wizard will install and configure:' -ForegroundColor White
    Write-Host '    Python 3.10.11, pyenv-win, Git Bash, WSL Ubuntu, Poetry,' -ForegroundColor DarkGray
    Write-Host '    Databricks CLI/Connect, VS Code + extensions, and more.' -ForegroundColor DarkGray
    Write-Host ''
    Write-Host '  All downloads and packages route through Artifactory only.' -ForegroundColor Yellow
    Write-Host ''
}

function Write-SetupStepHeader {
    param(
        [int]$StepNumber,
        [int]$TotalSteps,
        [string]$Title
    )
    Write-Host ''
    Write-Host "  -- Step $StepNumber of $TotalSteps : $Title --" -ForegroundColor Cyan
    Write-Host ''
}

function Write-SetupSuccess {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-SetupFailure {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Write-SetupWarning {
    param([string]$Message)
    Write-Host "  ! $Message" -ForegroundColor Yellow
}

function Write-SetupInfo {
    param([string]$Message)
    Write-Host "  >> $Message" -ForegroundColor White
}

function Write-SetupHint {
    param([string]$Message)
    Write-Host "  HINT: $Message" -ForegroundColor DarkYellow
}

function Read-SetupPrompt {
    param(
        [string]$Message,
        [string]$Default = ''
    )
    if ($Default) {
        $input = Read-Host "  $Message (default: $Default)"
        if ([string]::IsNullOrWhiteSpace($input)) { return $Default }
        return $input.Trim()
    }
    return (Read-Host "  $Message").Trim()
}

function Read-SetupYesNo {
    param(
        [string]$Message,
        [string]$Default = 'Y'
    )
    $answer = Read-SetupPrompt -Message $Message -Default $Default
    return -not ($answer -match '^(n|no)$')
}

function Read-SetupSecurePrompt {
    param([string]$Message)
    $secure = Read-Host "  $Message" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Read-SetupValidatedPrompt {
    param(
        [string]$Message,
        [scriptblock]$Validator,
        [string]$ErrorHint,
        [string]$Default = ''
    )
    while ($true) {
        $value = Read-SetupPrompt -Message $Message -Default $Default
        if (& $Validator $value) {
            return $value
        }
        Write-SetupWarning $ErrorHint
    }
}

$script:SetupDataDir = $script:DefaultSetupDataDir
$script:ConfigPath = Join-Path $script:SetupDataDir 'config.json'
$script:CredentialsPath = Join-Path $script:SetupDataDir 'credentials.json'
$script:StatePath = Join-Path $script:SetupDataDir 'state.json'
$script:LogPath = Join-Path $script:SetupDataDir 'setup.log'

function Set-SetupDataDir {
    param([string]$DataDir)
    $script:SetupDataDir = $DataDir
    $script:ConfigPath = Join-Path $script:SetupDataDir 'config.json'
    $script:CredentialsPath = Join-Path $script:SetupDataDir 'credentials.json'
    $script:StatePath = Join-Path $script:SetupDataDir 'state.json'
    $script:LogPath = Join-Path $script:SetupDataDir 'setup.log'
}

function Initialize-StandardPracticeEnvironment {
    Set-SetupDataDir -DataDir $script:StandardPracticeDataDir
    Initialize-SetupEnvironment
    Initialize-DependencyLedger -DataDir $script:StandardPracticeDataDir
}

function Initialize-SetupEnvironment {
    foreach ($dir in @($script:SetupDataDir, (Join-Path $script:SetupDataDir 'downloads'), (Join-Path $script:SetupDataDir 'cache'))) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    if (-not (Test-Path $script:LogPath)) {
        New-Item -ItemType File -Path $script:LogPath -Force | Out-Null
    }
}

function Write-SetupLog {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR', 'DEBUG')]
        [string]$Level = 'INFO'
    )
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogPath -Value $line -Encoding UTF8
}

function Get-SetupConfig {
    if (Test-Path $script:ConfigPath) {
        return Get-Content -Path $script:ConfigPath -Raw | ConvertFrom-Json
    }
    return $null
}

function Save-SetupConfig {
    param([psobject]$Config)
    $Config | ConvertTo-Json -Depth 10 | Set-Content -Path $script:ConfigPath -Encoding UTF8
    Write-SetupLog "Saved setup config to $script:ConfigPath"
}

function Get-SetupCredentials {
    if (Test-Path $script:CredentialsPath) {
        $cred = Get-Content -Path $script:CredentialsPath -Raw | ConvertFrom-Json
        if ($cred.ApiKey) {
            $cred.ApiKey = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($cred.ApiKey))
        }
        if ($cred.Password) {
            $cred.Password = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($cred.Password))
        }
        return $cred
    }
    return $null
}

function Save-SetupCredentials {
    param(
        [string]$Username,
        [string]$ApiKey,
        [string]$Password
    )
    $payload = [ordered]@{}
    if ($Username) { $payload.Username = $Username }
    if ($ApiKey) {
        $payload.ApiKey = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($ApiKey))
    }
    if ($Password) {
        $payload.Password = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Password))
    }
    $payload | ConvertTo-Json | Set-Content -Path $script:CredentialsPath -Encoding UTF8
    $acl = Get-Acl $script:CredentialsPath
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $env:USERNAME, 'FullControl', 'Allow'
    )
    $acl.SetAccessRule($rule)
    Set-Acl -Path $script:CredentialsPath -AclObject $acl
    Write-SetupLog "Saved credentials (restricted ACL)"
}

function Get-SetupState {
    if (Test-Path $script:StatePath) {
        return Get-Content -Path $script:StatePath -Raw | ConvertFrom-Json
    }
    return [pscustomobject]@{
        steps    = @{}
        lastStep = -1
        started  = (Get-Date).ToString('o')
    }
}

function Save-SetupState {
    param([psobject]$State)
    if (-not $State.steps) {
        $State | Add-Member -NotePropertyName steps -NotePropertyValue @{} -Force
    }
    $State | ConvertTo-Json -Depth 10 | Set-Content -Path $script:StatePath -Encoding UTF8
}

function Update-StepState {
    param(
        [int]$StepNumber,
        [string]$StepName,
        [ValidateSet('pending', 'running', 'completed', 'failed', 'skipped')]
        [string]$Status,
        [int]$Attempts = 0,
        [string]$ErrorMessage = ''
    )
    $state = Get-SetupState
    if (-not $state.steps) {
        $state.steps = @{}
    }
    $stepKey = "step_$StepNumber"
    $state.steps | Add-Member -NotePropertyName $stepKey -NotePropertyValue ([pscustomobject]@{
        name         = $StepName
        status       = $Status
        attempts     = $Attempts
        errorMessage = $ErrorMessage
        updated      = (Get-Date).ToString('o')
    }) -Force
    if ($Status -eq 'completed') {
        $state.lastStep = [Math]::Max($state.lastStep, $StepNumber)
    }
    Save-SetupState -State $state
}

function Test-StepCompleted {
    param([int]$StepNumber)
    $state = Get-SetupState
    $stepKey = "step_$StepNumber"
    if ($state.steps.PSObject.Properties.Name -contains $stepKey) {
        return $state.steps.$stepKey.status -eq 'completed'
    }
    return $false
}

function Add-ToUserPath {
    param([string[]]$Paths)
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $segments = $userPath -split ';' | Where-Object { $_ }
    $changed = $false
    foreach ($p in $Paths) {
        if ($p -and ($segments -notcontains $p)) {
            $segments += $p
            $changed = $true
        }
    }
    if ($changed) {
        $newPath = ($segments -join ';')
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        $env:Path = (($env:Path -split ';') + $Paths | Select-Object -Unique) -join ';'
        Write-SetupLog "Updated user PATH with: $($Paths -join ', ')"
    }
}

function Set-UserEnvironmentVariable {
    param(
        [string]$Name,
        [string]$Value
    )
    [Environment]::SetEnvironmentVariable($Name, $Value, 'User')
    Set-Item -Path "Env:$Name" -Value $Value
    Write-SetupLog "Set user env $Name"
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Request-AdminElevation {
    param([string]$Reason)
    Write-SetupInfo $Reason
    if (Test-IsAdministrator) {
        return $true
    }
    $answer = Read-SetupPrompt -Message 'Administrator privileges are required. Elevate now? [Y/n]' -Default 'Y'
    if ($answer -match '^(n|no)$') {
        return $false
    }
    Write-SetupInfo 'Requesting elevation...'
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$script:SelfPath`" -Resume"
    return $false
}

function Get-DownloadsDir {
    return Join-Path $script:SetupDataDir 'downloads'
}

function Get-CacheDir {
    return Join-Path $script:SetupDataDir 'cache'
}

function Get-DevProjectDir {
    $dir = Join-Path $env:USERPROFILE 'devenv-workspace'
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    return $dir
}

function Get-ArtifactoryAuthHeader {
    param($Config, $Credentials)
    if ($Credentials.ApiKey) {
        if ($Credentials.Username) {
            $pair = "$($Credentials.Username):$($Credentials.ApiKey)"
            $bytes = [Text.Encoding]::ASCII.GetBytes($pair)
            return @{ Authorization = "Basic $([Convert]::ToBase64String($bytes))" }
        }
        return @{ 'X-JFrog-Art-Api' = $Credentials.ApiKey }
    }
    if ($Credentials.Username -and $Credentials.Password) {
        $pair = "$($Credentials.Username):$($Credentials.Password)"
        $bytes = [Text.Encoding]::ASCII.GetBytes($pair)
        return @{ Authorization = "Basic $([Convert]::ToBase64String($bytes))" }
    }
    return @{}
}


function Test-ArtifactoryEndpoint {
    param(
        [string]$Url,
        $Config,
        $Credentials,
        [switch]$HeadOnly
    )
    try {
        $headers = Get-ArtifactoryAuthHeader -Config $Config -Credentials $Credentials
        $params = @{
            Uri             = $Url
            Method          = if ($HeadOnly) { 'Head' } else { 'Get' }
            Headers         = $headers
            UseBasicParsing = $true
            TimeoutSec      = 30
            ErrorAction     = 'Stop'
        }
        if ($Config.Proxy) {
            $params.Proxy = $Config.Proxy
        }
        $response = Invoke-WebRequest @params
        return [pscustomobject]@{
            Success    = $true
            StatusCode = [int]$response.StatusCode
            Url        = $Url
        }
    }
    catch {
        $status = $null
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        return [pscustomobject]@{
            Success    = $false
            StatusCode = $status
            Url        = $Url
            Error      = $_.Exception.Message
        }
    }
}


function Get-ArtifactoryPypiUrl {
    param($Config)
    $repo = $Config.Repos.pypi
    $base = $Config.BaseUrl.TrimEnd('/')
    return "$base/api/pypi/$repo/simple"
}


function Test-PypiRepo {
    param(
        [string]$RepoName,
        $Config,
        $Credentials
    )
    $base = $Config.BaseUrl.TrimEnd('/')
    $url = "$base/api/pypi/$RepoName/simple/pip/"
    return Test-ArtifactoryEndpoint -Url $url -Config $Config -Credentials $Credentials
}


function Set-ArtifactoryPipConfig {
    param($Config, $Credentials)
    $indexUrl = Get-ArtifactoryPypiUrl -Config $Config
    $pipDir = Join-Path $env:APPDATA 'pip'
    if (-not (Test-Path $pipDir)) {
        New-Item -ItemType Directory -Path $pipDir -Force | Out-Null
    }
    $pipIni = Join-Path $pipDir 'pip.ini'
    $trustedHost = ([uri]$Config.BaseUrl).Host
    @"
[global]
index-url = $indexUrl
no-index = false
trusted-host = $trustedHost

[install]
trusted-host = $trustedHost
"@ | Set-Content -Path $pipIni -Encoding UTF8

    $env:PIP_INDEX_URL = $indexUrl
    $env:PIP_TRUSTED_HOST = $trustedHost
    Write-SetupLog "Configured pip.ini with Artifactory index"
}


function Set-ArtifactoryPoetryConfig {
    param($Config)
    $indexUrl = Get-ArtifactoryPypiUrl -Config $Config
    $poetryConfig = Join-Path $env:APPDATA 'pypoetry'
    if (-not (Test-Path $poetryConfig)) {
        New-Item -ItemType Directory -Path $poetryConfig -Force | Out-Null
    }
    $configToml = Join-Path $poetryConfig 'config.toml'
    @"
[repositories.artifactory]
url = "$indexUrl"

[virtualenvs]
in-project = true
"@ | Set-Content -Path $configToml -Encoding UTF8
    Write-SetupLog "Configured poetry config.toml with Artifactory"
}


function Invoke-ArtifactoryPipInstall {
    param(
        [string[]]$Packages,
        $Config,
        [string]$PythonExe = 'python'
    )
    $indexUrl = Get-ArtifactoryPypiUrl -Config $Config
    Assert-ArtifactoryUrl -Url $indexUrl -Config $Config
    $trustedHost = ([uri]$Config.BaseUrl).Host
    $args = @(
        '-m', 'pip', 'install',
        '--index-url', $indexUrl,
        '--trusted-host', $trustedHost,
        '--no-cache-dir'
    ) + $Packages

    Write-SetupLog "pip install: $($Packages -join ', ')"
    $output = & $PythonExe @args 2>&1
    $output | ForEach-Object { Write-SetupLog $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed: $($output -join "`n")"
    }
}


$script:DependencyLedger = @()
$script:LedgerPath = $null

function Initialize-DependencyLedger {
    param([string]$DataDir)
    $script:LedgerPath = Join-Path $DataDir 'dependency-ledger.json'
    if (Test-Path $script:LedgerPath) {
        $script:DependencyLedger = @(Get-Content $script:LedgerPath -Raw | ConvertFrom-Json)
    }
    else {
        $script:DependencyLedger = @()
    }
}

function Add-DependencyRecord {
    param(
        [string]$Name,
        [string]$Category,
        [string]$SourceUrl,
        [string]$Publisher = '',
        [ValidateSet('yes', 'no')]
        [string]$Artifactory,
        [ValidateSet('Low', 'Medium', 'High')]
        [string]$RiskRating,
        [string]$RiskRationale = '',
        [ValidateSet('installed', 'skipped', 'failed', 'already_present', 'configured')]
        [string]$Status,
        [string]$Version = '',
        [string]$InstallMethod = '',
        [string]$Notes = ''
    )

    $sourceHost = ''
    if ($SourceUrl -match '^https?://([^/]+)') {
        $sourceHost = $Matches[1]
    }

    $record = [pscustomobject]@{
        name            = $Name
        category        = $Category
        source_url      = $SourceUrl
        source_host     = $sourceHost
        publisher       = $Publisher
        artifactory     = $Artifactory
        risk_rating     = $RiskRating
        risk_rationale  = $RiskRationale
        status          = $Status
        version         = $Version
        install_method  = $InstallMethod
        notes           = $Notes
        recorded_at     = (Get-Date).ToString('o')
    }

    $script:DependencyLedger = @($script:DependencyLedger | Where-Object { $_.name -ne $Name }) + $record
    Save-DependencyLedger
    return $record
}

function Save-DependencyLedger {
    if (-not $script:LedgerPath) { return }
    $script:DependencyLedger | ConvertTo-Json -Depth 5 | Set-Content -Path $script:LedgerPath -Encoding UTF8
}

function Get-DependencyLedger {
    return $script:DependencyLedger
}

function Get-TrustedSources {
    return $script:TrustedSourcesJson | ConvertFrom-Json
}

function Invoke-TrustedDownload {
    param(
        [string]$Url,
        [string]$Destination,
        [string]$Name
    )
    Write-SetupInfo "Downloading $Name from trusted source..."
    Write-SetupLog "Trusted download: $Url -> $Destination"
    $params = @{
        Uri             = $Url
        OutFile         = $Destination
        UseBasicParsing = $true
        TimeoutSec      = 600
        ErrorAction     = 'Stop'
    }
    Invoke-WebRequest @params
    if (-not (Test-Path $Destination)) {
        throw "Download failed - file not found at $Destination"
    }
    return $Destination
}

function Get-GitBashPath {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe'),
        (Join-Path ${env:ProgramFiles} 'Git\bin\bash.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Git\bin\bash.exe')
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    return $null
}

function Test-GitBashInstalled {
    $bash = Get-GitBashPath
    if (-not $bash) { return $false }
    try {
        $out = & $bash --version 2>&1
        return ($out -match 'bash')
    }
    catch { return $false }
}

function Test-WSLUbuntuInstalled {
    try {
        $list = wsl -l -v 2>&1 | Out-String
        return ($list -match 'Ubuntu')
    }
    catch { return $false }
}

function Test-PyenvWinInstalled {
    $pyenvRoot = Join-Path $env:USERPROFILE '.pyenv\pyenv-win'
    $pyenvBat = Join-Path $pyenvRoot 'bin\pyenv.bat'
    if (-not (Test-Path $pyenvBat)) { return $false }
    try {
        $out = & cmd /c "`"$pyenvBat`" --version" 2>&1
        return ($out -match 'pyenv')
    }
    catch { return $false }
}

function Get-PyenvPythonPath {
    $versions = Join-Path $env:USERPROFILE '.pyenv\pyenv-win\versions'
    $target = Join-Path $versions '3.10.11'
    $python = Join-Path $target 'python.exe'
    if (Test-Path $python) { return $python }
    return $null
}

function Test-Python311Installed {
    $python = Get-PyenvPythonPath
    if (-not $python) {
        $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
    if (-not $python) { return $false }
    try {
        $out = & $python --version 2>&1
        return ($out -match '3\.10\.11')
    }
    catch { return $false }
}

function Get-ActivePython {
    $python = Get-PyenvPythonPath
    if ($python) { return $python }
    return (Get-Command python -ErrorAction SilentlyContinue).Source
}

function Test-PoetryInstalled {
    try {
        $out = poetry --version 2>&1
        return ($out -match 'Poetry')
    }
    catch { return $false }
}

function Test-PythonPackageInstalled {
    param([string]$PackageName)
    $python = Get-ActivePython
    if (-not $python) { return $false }
    $importName = $PackageName
    switch ($PackageName) {
        'pyyaml' { $importName = 'yaml' }
        'databricks-sdk' { $importName = 'databricks.sdk' }
        'databricks-cli' { return Test-DatabricksCliInstalled }
        'databricks-connect' { $importName = 'databricks.connect' }
    }
    try {
        & $python -c "import $importName" 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch { return $false }
}

function Test-DatabricksCliInstalled {
    try {
        $out = databricks --version 2>&1
        return ($out -match 'Databricks|databricks|Version')
    }
    catch { return $false }
}

function Test-DatabricksConnectInstalled {
    return Test-PythonPackageInstalled -PackageName 'databricks-connect'
}

function Get-DatabricksCfgPath {
    return Join-Path $env:USERPROFILE '.databrickscfg'
}

function Test-DatabricksCfgConfigured {
    $path = Get-DatabricksCfgPath
    if (-not (Test-Path $path)) { return $false }
    $content = Get-Content $path -Raw
    if ($content -notmatch '\[.+\]') { return $false }
    if ($content -notmatch 'host\s*=') { return $false }
    if ($content -notmatch 'token\s*=') { return $false }
    return $true
}

function Test-VSCodeInstalled {
    try {
        $out = code --version 2>&1
        return ($out -match '^\d+\.\d+')
    }
    catch { return $false }
}

function Test-VSCodeExtensionInstalled {
    param([string]$ExtensionId)
    try {
        $list = code --list-extensions 2>&1
        return ($list -contains $ExtensionId)
    }
    catch { return $false }
}

function Test-VSCodeExtensionsInstalled {
    $trusted = Get-TrustedSources
    foreach ($key in @('ext-databricks', 'ext-python', 'ext-poetry')) {
        $extId = $trusted.sources.$key.extensionId
        if (-not (Test-VSCodeExtensionInstalled -ExtensionId $extId)) { return $false }
    }
    return $true
}

function Invoke-ComponentVerification {
    param($Config)
    $manifest = [pscustomobject]@{ verifyComponents = $script:VerifyComponents }
    $results = @()

    foreach ($comp in $manifest.verifyComponents) {
        $status = 'FAIL'
        $detail = ''
        $action = ''

        switch ($comp.id) {
            'git-bash' {
                if (Test-GitBashInstalled) {
                    $status = 'OK'
                    $bash = Get-GitBashPath
                    $detail = (& $bash --version 2>&1 | Select-Object -First 1)
                }
                else { $action = 'Re-run step 2; verify Git installer in Artifactory generic repo' }
            }
            'wsl-ubuntu' {
                if (Test-WSLUbuntuInstalled) {
                    $status = 'OK'
                    $detail = 'Ubuntu distro registered in WSL'
                }
                else { $action = 'Re-run step 3; may require admin for WSL features' }
            }
            'pyenv-win' {
                if (Test-PyenvWinInstalled) {
                    $status = 'OK'
                    $detail = 'pyenv-win installed'
                }
                else { $action = 'Re-run step 4; verify pyenv-win.zip in Artifactory' }
            }
            'python-3.10.11' {
                if (Test-Python311Installed) {
                    $status = 'OK'
                    $python = Get-ActivePython
                    $detail = (& $python --version 2>&1)
                }
                else { $action = 'Re-run step 5; verify python-3.10.11-win32.zip mirror' }
            }
            'poetry' {
                if (Test-PoetryInstalled) {
                    $status = 'OK'
                    $detail = (poetry --version 2>&1)
                }
                else { $action = 'Re-run step 6; check PyPI mirror has poetry' }
            }
            'pytest' { $status, $detail, $action = Get-PackageVerifyResult 'pytest' 8 }
            'pyspark' { $status, $detail, $action = Get-PackageVerifyResult 'pyspark' 8 }
            'pandas' { $status, $detail, $action = Get-PackageVerifyResult 'pandas' 8 }
            'numpy' { $status, $detail, $action = Get-PackageVerifyResult 'numpy' 8 }
            'pyyaml' { $status, $detail, $action = Get-PackageVerifyResult 'pyyaml' 8 }
            'requests' { $status, $detail, $action = Get-PackageVerifyResult 'requests' 8 }
            'databricks-sdk' { $status, $detail, $action = Get-PackageVerifyResult 'databricks-sdk' 8 }
            'databricks-cli' {
                if (Test-DatabricksCliInstalled) {
                    $status = 'OK'
                    $detail = (databricks --version 2>&1 | Select-Object -First 1)
                }
                else { $action = 'Re-run step 9; check PyPI mirror has databricks-cli' }
            }
            'databricks-connect' {
                if (Test-DatabricksConnectInstalled) {
                    $status = 'OK'
                    $detail = 'databricks.connect importable'
                }
                else { $action = 'Re-run step 10; match databricks-connect version to cluster runtime' }
            }
            'databrickscfg' {
                if (Test-DatabricksCfgConfigured) {
                    $status = 'OK'
                    $detail = "~/.databrickscfg configured"
                }
                else { $action = 'Re-run step 11; provide host and token' }
            }
            'vscode' {
                if (Test-VSCodeInstalled) {
                    $status = 'OK'
                    $detail = (code --version 2>&1 | Select-Object -First 1)
                }
                else { $action = 'Re-run step 12; verify VS Code installer in Artifactory' }
            }
            'vscode-extensions' {
                if (Test-VSCodeExtensionsInstalled) {
                    $status = 'OK'
                    $detail = 'All required extensions installed'
                }
                else { $action = 'Re-run step 13; verify .vsix files in Artifactory' }
            }
        }

        $results += [pscustomobject]@{
            Id       = $comp.id
            Name     = $comp.name
            Step     = $comp.step
            Status   = $status
            Detail   = $detail
            Action   = $action
        }
    }

    return $results
}

function Get-PackageVerifyResult {
    param([string]$Package, [int]$Step)
    if (Test-PythonPackageInstalled -PackageName $Package) {
        return 'OK', "$Package installed", ''
    }
    return 'FAIL', '', "Re-run step $Step; check PyPI mirror has $Package"
}

function Invoke-StepPreflight {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        throw 'PowerShell 5.1 or later is required'
    }
    $policy = Get-ExecutionPolicy -Scope CurrentUser
    if ($policy -eq 'Restricted') {
        Write-SetupWarning 'Execution policy is Restricted for CurrentUser'
        if (Read-SetupYesNo -Message 'Set ExecutionPolicy to RemoteSigned (CurrentUser)? [Y/n]') {
            Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
        }
    }
    $freeGb = (Get-PSDrive C).Free / 1GB
    if ($freeGb -lt 5) {
        Write-SetupWarning "Low disk space on C: ($([math]::Round($freeGb,1)) GB free). Recommend 5+ GB."
    }
    Write-SetupSuccess 'Preflight checks passed'
    return $true
}


function Test-StepPreflight {
    return ($PSVersionTable.PSVersion.Major -ge 5)
}

function Test-StepArtifactory {
    $cfg = Get-SetupConfig
    $cred = Get-SetupCredentials
    if (-not $cfg -or -not $cred) { return $false }
    $probe = Test-PypiRepo -RepoName $cfg.Repos.pypi -Config $cfg -Credentials $cred
    return $probe.Success
}

function Invoke-StepPackageIndexConfig {
    param($Config)
    Set-ArtifactoryPipConfig -Config $Config -Credentials (Get-SetupCredentials)
    Set-ArtifactoryPoetryConfig -Config $Config
    return $true
}


function Test-StepPackageIndexConfig {
    $pipIni = Join-Path $env:APPDATA 'pip\pip.ini'
    if (-not (Test-Path $pipIni)) { return $false }
    $content = Get-Content $pipIni -Raw
    $cfg = Get-SetupConfig
    return ($content -match ([regex]::Escape($cfg.BaseUrl)) -or $content -match 'artifactory')
}

function Test-StepPythonPackages {
    $packages = @('pytest', 'pyspark', 'pandas', 'numpy', 'pyyaml', 'requests', 'databricks-sdk')
    foreach ($p in $packages) {
        if (-not (Test-PythonPackageInstalled -PackageName $p)) { return $false }
    }
    return $true
}

function Invoke-StepDatabricksCfg {
    param($Config, $Credentials)
    Write-SetupInfo 'Configuring ~/.databrickscfg'
    $profile = Read-SetupPrompt -Message 'Profile name' -Default 'DEFAULT'
    $dbHost = Read-SetupValidatedPrompt `
        -Message 'Databricks host URL (https://...)' `
        -Validator { param($v) $v -match '^https://' } `
        -ErrorHint 'Host must start with https://'
    $token = Read-SetupSecurePrompt -Message 'Databricks personal access token'

    $cfgPath = Get-DatabricksCfgPath
    $section = "[$profile]"
    $entry = @"
$section
host = $dbHost
token = $token

"@
    if (Test-Path $cfgPath) {
        $existing = Get-Content $cfgPath -Raw
        if ($existing -match "\[$([regex]::Escape($profile))\]") {
            Write-SetupWarning "Profile [$profile] exists - overwriting"
            $existing = $existing -replace "(?s)\[$([regex]::Escape($profile))\].*?(?=\[|\z)", ''
            $entry = $existing.TrimEnd() + "`n`n" + $entry
        }
        else {
            $entry = $existing.TrimEnd() + "`n`n" + $entry
        }
    }
    Set-Content -Path $cfgPath -Value $entry.TrimEnd() -Encoding UTF8

    $acl = Get-Acl $cfgPath
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($env:USERNAME, 'FullControl', 'Allow')
    $acl.SetAccessRule($rule)
    Set-Acl -Path $cfgPath -AclObject $acl

    Write-SetupInfo 'Validating Databricks connection...'
    try {
        $headers = @{ Authorization = "Bearer $token" }
        $apiUrl = "$($dbHost.TrimEnd('/'))/api/2.0/clusters/list"
        $resp = Invoke-RestMethod -Uri $apiUrl -Headers $headers -Method Get -TimeoutSec 30 -ErrorAction Stop
        Write-SetupSuccess 'Databricks API connection verified'
    }
    catch {
        Write-SetupWarning "API validation failed: $($_.Exception.Message) - config saved, verify token/host manually"
    }
    return $true
}


function Write-StandardPracticeBanner {
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host '   Standard Practice Setup  (Artifactory: Python only)       ' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  Python packages  -> Corporate Artifactory (PyPI)' -ForegroundColor Yellow
    Write-Host '  All other deps   -> Trusted upstream sources' -ForegroundColor Green
    Write-Host ''
}

function Invoke-StandardPracticeArtifactorySetup {
    $trusted = Get-TrustedSources
    Write-SetupInfo 'Artifactory configuration (Python/PyPI only)'

    $baseUrl = Read-SetupValidatedPrompt `
        -Message 'Artifactory base URL' `
        -Validator { param($v) $v -match '^https?://' } `
        -ErrorHint 'URL must start with http:// or https://'

    $authMethod = Read-SetupPrompt -Message 'Auth: [1] API key  [2] Username/password' -Default '1'
    $username = $null; $apiKey = $null; $password = $null
    if ($authMethod -eq '2') {
        $username = Read-SetupPrompt -Message 'Artifactory username'
        $password = Read-SetupSecurePrompt -Message 'Artifactory password'
    }
    else {
        $username = Read-SetupPrompt -Message 'Artifactory username (optional)' -Default ''
        $apiKey = Read-SetupSecurePrompt -Message 'Artifactory API key'
    }

    Save-SetupCredentials -Username $username -ApiKey $apiKey -Password $password
    $cred = Get-SetupCredentials

    $config = [pscustomobject]@{
        BaseUrl = $baseUrl.TrimEnd('/')
        Proxy   = $null
        Repos   = [pscustomobject]@{
            pypi            = $null
            generic         = $null
            vscodeExtension = $null
        }
        ArtifactOverrides = @{}
        Mode              = 'standard-practice'
    }

    $trustedSources = Get-TrustedSources
    foreach ($repoName in @('pypi-remote', 'pypi-virtual', 'pypi-local', 'python-remote')) {
        $probe = Test-PypiRepo -RepoName $repoName -Config $config -Credentials $cred
        if ($probe.Success) {
            $config.Repos.pypi = $repoName
            Write-SetupSuccess "PyPI repo found: $repoName"
            break
        }
    }
    if (-not $config.Repos.pypi) {
        $config.Repos.pypi = Read-SetupPrompt -Message 'Enter PyPI repository name'
    }

    $pypiUrl = Get-ArtifactoryPypiUrl -Config $config
    Add-DependencyRecord `
        -Name 'Artifactory PyPI Index' `
        -Category 'python-index' `
        -SourceUrl $pypiUrl `
        -Publisher 'Corporate Artifactory' `
        -Artifactory 'yes' `
        -RiskRating 'Low' `
        -RiskRationale 'Corporate-controlled PyPI proxy; sole index for Python packages' `
        -Status 'configured' `
        -InstallMethod 'pip/poetry index-url configuration'

    foreach ($pkg in $trustedSources.pypiPackages) {
        Add-DependencyRecord `
            -Name $pkg.name `
            -Category 'python-package' `
            -SourceUrl "$pypiUrl/$($pkg.name)/" `
            -Publisher 'Corporate Artifactory (PyPI proxy)' `
            -Artifactory 'yes' `
            -RiskRating $pkg.riskRating `
            -RiskRationale $pkg.riskRationale `
            -Status 'pending' `
            -InstallMethod 'pip install --index-url Artifactory'
    }

    Save-SetupConfig -Config $config
    Set-ArtifactoryPipConfig -Config $config -Credentials $cred
    $script:SetupConfig = $config
    $script:SetupCredentials = $cred
    return $config
}

function Get-StandardPracticeConfig {
    $existing = Get-SetupConfig
    $cred = Get-SetupCredentials
    if ($existing -and $cred -and $existing.Repos.pypi) {
        Write-SetupInfo "Using saved Artifactory config: $($existing.BaseUrl) (PyPI: $($existing.Repos.pypi))"
        if (-not (Read-SetupYesNo -Message 'Reconfigure Artifactory PyPI? [y/N]' -Default 'N')) {
            return $existing
        }
    }
    return Invoke-StandardPracticeArtifactorySetup
}

function Register-PythonPackageInstalled {
    param(
        [string]$PackageName,
        $Config,
        [string]$Status = 'installed'
    )
    $pypiUrl = Get-ArtifactoryPypiUrl -Config $Config
    $trusted = Get-TrustedSources
    $meta = $trusted.pypiPackages | Where-Object { $_.name -eq $PackageName } | Select-Object -First 1
    $version = ''
    $python = Get-ActivePython
    if ($python) {
        try {
            $version = (& $python -m pip show $PackageName 2>&1 | Select-String '^Version:' | ForEach-Object { $_.Line -replace '^Version:\s*', '' })
        }
        catch { }
    }
    Add-DependencyRecord `
        -Name $PackageName `
        -Category 'python-package' `
        -SourceUrl "$pypiUrl/$PackageName/" `
        -Publisher 'Corporate Artifactory (PyPI proxy)' `
        -Artifactory 'yes' `
        -RiskRating $(if ($meta) { $meta.riskRating } else { 'Low' }) `
        -RiskRationale $(if ($meta) { $meta.riskRationale } else { 'Installed via Artifactory PyPI index' }) `
        -Status $Status `
        -Version $version `
        -InstallMethod 'pip install --index-url Artifactory'
}

function Invoke-SPStepGitBash {
    $trusted = Get-TrustedSources
    $src = $trusted.sources.'git-for-windows'
    if (Test-GitBashInstalled) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'already_present' -InstallMethod 'exe-silent'
        return $true
    }
    $dest = Join-Path (Get-DownloadsDir) 'Git-Installer.exe'
    Invoke-TrustedDownload -Url $src.sourceUrl -Destination $dest -Name $src.name
    $proc = Start-Process -FilePath $dest -ArgumentList '/VERYSILENT', '/NORESTART', '/CURRENTUSER' -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'failed' -InstallMethod 'exe-silent'
        throw "Git installer exited with code $($proc.ExitCode)"
    }
    Add-ToUserPath @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\bin'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd')
    )
    Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
        -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
        -RiskRationale $src.riskRationale -Status 'installed' -Version '2.43.0' -InstallMethod 'exe-silent'
    return $true
}

function Invoke-SPStepWSLUbuntu {
    $trusted = Get-TrustedSources
    $src = $trusted.sources.'wsl-ubuntu'
    if (Test-WSLUbuntuInstalled) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'already_present' -InstallMethod 'wsl --install'
        return $true
    }
    $wslStatus = wsl --status 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0 -or $wslStatus -match 'not installed|disabled') {
        if (-not (Test-IsAdministrator)) {
            $elevated = Request-AdminElevation -Reason 'WSL feature installation requires Administrator.'
            if (-not $elevated) { throw 'WSL not enabled and elevation declined' }
        }
        else {
            dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
            dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
        }
    }
    Write-SetupInfo 'Installing Ubuntu via Microsoft WSL distribution service...'
    wsl --install -d Ubuntu --no-launch 2>&1 | ForEach-Object { Write-SetupLog $_ }
    if ($LASTEXITCODE -ne 0) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'failed' -InstallMethod 'wsl --install'
        throw 'wsl --install -d Ubuntu failed - reboot may be required'
    }
    Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
        -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
        -RiskRationale $src.riskRationale -Status 'installed' -InstallMethod 'wsl --install -d Ubuntu'
    return $true
}

function Invoke-SPStepPyenvWin {
    $trusted = Get-TrustedSources
    $src = $trusted.sources.'pyenv-win'
    if (Test-PyenvWinInstalled) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'already_present' -InstallMethod 'zip-extract'
        return $true
    }
    $zipDest = Join-Path (Get-DownloadsDir) 'pyenv-win.zip'
    Invoke-TrustedDownload -Url $src.sourceUrl -Destination $zipDest -Name $src.name
    $pyenvRoot = Join-Path $env:USERPROFILE '.pyenv\pyenv-win'
    if (Test-Path $pyenvRoot) { Remove-Item $pyenvRoot -Recurse -Force }
    Expand-Archive -Path $zipDest -DestinationPath (Join-Path $env:USERPROFILE '.pyenv') -Force
    $nested = Get-ChildItem (Join-Path $env:USERPROFILE '.pyenv') -Directory | Where-Object { $_.Name -like 'pyenv-win*' } | Select-Object -First 1
    if ($nested -and $nested.FullName -ne $pyenvRoot) {
        Rename-Item $nested.FullName 'pyenv-win'
    }
    Set-UserEnvironmentVariable -Name 'PYENV' -Value $pyenvRoot
    Set-UserEnvironmentVariable -Name 'PYENV_ROOT' -Value $pyenvRoot
    Set-UserEnvironmentVariable -Name 'PYENV_HOME' -Value $pyenvRoot
    Add-ToUserPath @(
        (Join-Path $pyenvRoot 'bin'),
        (Join-Path $pyenvRoot 'shims')
    )
    Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
        -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
        -RiskRationale $src.riskRationale -Status 'installed' -InstallMethod 'zip-extract'
    return $true
}

function Invoke-SPStepPython {
    $trusted = Get-TrustedSources
    $src = $trusted.sources.'python-3.10.11'
    if (Test-Python311Installed) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'already_present' -Version '3.10.11'
        return $true
    }
    $zipDest = Join-Path (Get-DownloadsDir) 'python-3.10.11-win32.zip'
    Invoke-TrustedDownload -Url $src.sourceUrl -Destination $zipDest -Name $src.name
    $pyenvRoot = Join-Path $env:USERPROFILE '.pyenv\pyenv-win'
    $versionsDir = Join-Path $pyenvRoot 'versions\3.10.11'
    if (Test-Path $versionsDir) { Remove-Item $versionsDir -Recurse -Force }
    New-Item -ItemType Directory -Path $versionsDir -Force | Out-Null
    Expand-Archive -Path $zipDest -DestinationPath $versionsDir -Force
    $pyenvBat = Join-Path $pyenvRoot 'bin\pyenv.bat'
    & cmd /c "`"$pyenvBat`" rehash" 2>&1 | Out-Null
    & cmd /c "`"$pyenvBat`" global 3.10.11" 2>&1 | Out-Null
    $pythonExe = Join-Path $versionsDir 'python.exe'
    if (-not (Test-Path $pythonExe)) {
        $nested = Get-ChildItem $versionsDir -Recurse -Filter 'python.exe' | Select-Object -First 1
        if ($nested) {
            Copy-Item (Join-Path $nested.Directory.FullName '*') -Destination $versionsDir -Recurse -Force
        }
    }
    Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
        -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
        -RiskRationale $src.riskRationale -Status 'installed' -Version '3.10.11' -InstallMethod 'pyenv-win + python.org zip'
    return $true
}

function Invoke-SPStepPoetry {
    param($Config)
    if (Test-PoetryInstalled) {
        Register-PythonPackageInstalled -PackageName 'poetry' -Config $Config -Status 'already_present'
        return $true
    }
    $python = Get-ActivePython
    if (-not $python) { throw 'Python not found - complete step 5 first' }
    Invoke-ArtifactoryPipInstall -Packages @('poetry') -Config $Config -PythonExe $python
    Add-ToUserPath @((Join-Path (Split-Path $python) 'Scripts'))
    Register-PythonPackageInstalled -PackageName 'poetry' -Config $Config
    return $true
}

function Invoke-SPStepPythonPackages {
    param($Config)
    $python = Get-ActivePython
    if (-not $python) { throw 'Python not found' }
    $packages = @('pytest', 'pyspark', 'pandas', 'numpy', 'pyyaml', 'requests', 'databricks-sdk')
    Invoke-ArtifactoryPipInstall -Packages $packages -Config $Config -PythonExe $python
    foreach ($p in $packages) {
        Register-PythonPackageInstalled -PackageName $p -Config $Config
    }
    return $true
}

function Invoke-SPStepDatabricksCli {
    param($Config)
    if (Test-DatabricksCliInstalled) {
        Register-PythonPackageInstalled -PackageName 'databricks-cli' -Config $Config -Status 'already_present'
        return $true
    }
    $python = Get-ActivePython
    Invoke-ArtifactoryPipInstall -Packages @('databricks-cli') -Config $Config -PythonExe $python
    Add-ToUserPath @((Join-Path (Split-Path $python) 'Scripts'))
    Register-PythonPackageInstalled -PackageName 'databricks-cli' -Config $Config
    return $true
}

function Invoke-SPStepDatabricksConnect {
    param($Config)
    if (Test-DatabricksConnectInstalled) {
        Register-PythonPackageInstalled -PackageName 'databricks-connect' -Config $Config -Status 'already_present'
        return $true
    }
    $python = Get-ActivePython
    $version = Read-SetupPrompt -Message 'Databricks cluster runtime version (e.g. 13.3)' -Default '13.3'
    Invoke-ArtifactoryPipInstall -Packages @("databricks-connect==$($version.Trim()).*") -Config $Config -PythonExe $python
    Register-PythonPackageInstalled -PackageName 'databricks-connect' -Config $Config
    return $true
}

function Invoke-SPStepDatabricksCfg {
    Invoke-StepDatabricksCfg -Config $script:SetupConfig -Credentials $script:SetupCredentials | Out-Null
    Add-DependencyRecord `
        -Name '.databrickscfg' `
        -Category 'configuration' `
        -SourceUrl 'local://~/.databrickscfg (user-provided credentials)' `
        -Publisher 'User / Databricks workspace' `
        -Artifactory 'no' `
        -RiskRating 'Low' `
        -RiskRationale 'Local config file; credentials supplied by user, not downloaded' `
        -Status 'configured' `
        -InstallMethod 'interactive prompt'
    return $true
}

function Invoke-SPStepVSCode {
    $trusted = Get-TrustedSources
    $src = $trusted.sources.vscode
    if (Test-VSCodeInstalled) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'already_present'
        return $true
    }
    $dest = Join-Path (Get-DownloadsDir) 'VSCodeUserSetup.exe'
    Invoke-TrustedDownload -Url $src.sourceUrl -Destination $dest -Name $src.name
    $proc = Start-Process -FilePath $dest -ArgumentList '/VERYSILENT', '/MERGETASKS=!runcode', '/CURRENTUSER' -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'failed'
        throw "VS Code installer exited with $($proc.ExitCode)"
    }
    Add-ToUserPath @((Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\bin'))
    $ver = (code --version 2>&1 | Select-Object -First 1)
    Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
        -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
        -RiskRationale $src.riskRationale -Status 'installed' -Version $ver -InstallMethod 'exe-silent'
    return $true
}

function Invoke-SPStepVSCodeExtensions {
    $trusted = Get-TrustedSources
    $extKeys = @('ext-databricks', 'ext-python', 'ext-poetry')
    foreach ($key in $extKeys) {
        $src = $trusted.sources.$key
        if (Test-VSCodeExtensionInstalled -ExtensionId $src.extensionId) {
            Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
                -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
                -RiskRationale $src.riskRationale -Status 'already_present' -InstallMethod 'code --install-extension (marketplace)'
            continue
        }
        Write-SetupInfo "Installing $($src.extensionId) from VS Marketplace..."
        & code --install-extension $src.extensionId --force 2>&1 | ForEach-Object { Write-SetupLog $_ }
        if ($LASTEXITCODE -ne 0) {
            Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
                -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
                -RiskRationale $src.riskRationale -Status 'failed' -InstallMethod 'code --install-extension'
            throw "Failed to install extension $($src.extensionId)"
        }
        Add-DependencyRecord -Name $src.name -Category $src.category -SourceUrl $src.sourceUrl `
            -Publisher $src.publisher -Artifactory $src.artifactory -RiskRating $src.riskRating `
            -RiskRationale $src.riskRationale -Status 'installed' -InstallMethod 'code --install-extension (marketplace)'
    }
    return $true
}

function Invoke-SPStepFinalReport {
    param($Config, [array]$StepResults)
    $verification = Invoke-ComponentVerification -Config $Config
    return Write-StandardPracticeDependencyReport -Config $Config -StepResults $StepResults -VerificationResults $verification
}

function Invoke-SetupStep {
    param(
        [int]$StepNumber,
        [int]$TotalSteps,
        [string]$Name,
        [string]$Title,
        [scriptblock]$Action,
        [scriptblock]$Verify,
        [string]$FailureHint = 'Check setup.log for details and retry this step.',
        [int]$MaxRetries = 3,
        [switch]$SkipIfCompleted,
        [switch]$Force
    )

    if ($SkipIfCompleted -and -not $Force) {
        if (Test-StepCompleted -StepNumber $StepNumber) {
            if (& $Verify) {
                Write-SetupStepHeader -StepNumber $StepNumber -TotalSteps $TotalSteps -Title $Title
                Write-SetupSuccess "$Title - already completed, skipping"
                return [pscustomobject]@{ Success = $true; Skipped = $true; Attempts = 0 }
            }
            Write-SetupWarning "$Title - marked complete but verification failed; re-running"
        }
    }

    Write-SetupStepHeader -StepNumber $StepNumber -TotalSteps $TotalSteps -Title $Title
    Update-StepState -StepNumber $StepNumber -StepName $Name -Status 'running'

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        Write-SetupInfo "Attempt $attempt of $MaxRetries..."
        Write-SetupLog "Step $StepNumber ($Name) attempt $attempt"

        try {
            $actionResult = & $Action
            if ($actionResult -eq $false) {
                throw "Action returned false for step $Name"
            }

            Start-Sleep -Milliseconds 500

            $verified = & $Verify
            if ($verified) {
                Update-StepState -StepNumber $StepNumber -StepName $Name -Status 'completed' -Attempts $attempt
                Write-SetupSuccess "$Title - done"
                Write-SetupLog "Step $StepNumber ($Name) completed on attempt $attempt"
                return [pscustomobject]@{ Success = $true; Skipped = $false; Attempts = $attempt }
            }

            throw "Verification failed for step $Name"
        }
        catch {
            $err = $_.Exception.Message
            Write-SetupLog "Step $StepNumber ($Name) attempt $attempt failed: $err" -Level ERROR
            Update-StepState -StepNumber $StepNumber -StepName $Name -Status 'running' -Attempts $attempt -ErrorMessage $err

            if ($attempt -lt $MaxRetries) {
                Write-SetupWarning "Attempt $attempt failed: $err"
                Write-SetupHint $FailureHint
                Write-SetupInfo 'Retrying...'
                Start-Sleep -Seconds 2
            }
            else {
                Update-StepState -StepNumber $StepNumber -StepName $Name -Status 'failed' -Attempts $attempt -ErrorMessage $err
                Write-SetupFailure "$Title - failed after $MaxRetries attempts"
                Write-SetupHint $FailureHint
                return [pscustomobject]@{ Success = $false; Skipped = $false; Attempts = $attempt; Error = $err }
            }
        }
    }
}

function Write-StandardPracticeDependencyReport {
    param(
        $Config,
        [array]$StepResults = @(),
        [array]$VerificationResults = @()
    )

    $ledger = Get-DependencyLedger
    $timestamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
    $dataDir = if ($script:StandardPracticeDataDir) { $script:StandardPracticeDataDir } else { $script:SetupDataDir }
    $reportPath = Join-Path $dataDir "standard-practice-report-$timestamp.md"
    $jsonPath = Join-Path $dataDir "standard-practice-report-$timestamp.json"

    $artifactoryCount = @($ledger | Where-Object { $_.artifactory -eq 'yes' }).Count
    $trustedCount = @($ledger | Where-Object { $_.artifactory -eq 'no' }).Count
    $lowRisk = @($ledger | Where-Object { $_.risk_rating -eq 'Low' }).Count
    $mediumRisk = @($ledger | Where-Object { $_.risk_rating -eq 'Medium' }).Count
    $highRisk = @($ledger | Where-Object { $_.risk_rating -eq 'High' }).Count
    $installed = @($ledger | Where-Object { $_.status -in @('installed', 'already_present', 'configured') }).Count
    $failed = @($ledger | Where-Object { $_.status -eq 'failed' }).Count

    $lines = @(
        '# Standard Practice Setup - Dependency Source Report',
        '',
        "Generated: $timestamp",
        'Mode: Artifactory for Python packages only; trusted upstream for all other dependencies',
        '',
        '## Executive Summary',
        '',
        "| Metric | Count |",
        "|--------|-------|",
        "| Total dependencies tracked | $($ledger.Count) |",
        "| Installed / configured | $installed |",
        "| Failed | $failed |",
        "| Via Artifactory | $artifactoryCount |",
        "| Via trusted upstream | $trustedCount |",
        "| Low risk | $lowRisk |",
        "| Medium risk | $mediumRisk |",
        "| High risk | $highRisk |",
        ''
    )

    if ($Config) {
        $lines += '## Artifactory Configuration (Python only)'
        $lines += ''
        $lines += "- Base URL: $($Config.BaseUrl)"
        $lines += "- PyPI repo: $($Config.Repos.pypi)"
        $lines += "- PyPI index: $(Get-ArtifactoryPypiUrl -Config $Config)"
        $lines += ''
    }

    $lines += '## Dependency Breakdown by Source'
    $lines += ''
    $lines += '| Name | Category | Source URL | Source Host | Artifactory | Risk | Status | Version | Install Method |'
    $lines += '|------|----------|------------|-------------|-------------|------|--------|---------|----------------|'

    foreach ($r in ($ledger | Sort-Object category, name)) {
        $url = ($r.source_url -replace '\|', '/' -replace "`n", ' ')
        if ($url.Length -gt 80) { $url = $url.Substring(0, 77) + '...' }
        $lines += "| $($r.name) | $($r.category) | $url | $($r.source_host) | $($r.artifactory) | $($r.risk_rating) | $($r.status) | $($r.version) | $($r.install_method) |"
    }

    $lines += ''
    $lines += '## Risk Rationale Detail'
    $lines += ''
    foreach ($r in ($ledger | Sort-Object risk_rating, name)) {
        $lines += "### $($r.name) [$($r.risk_rating)]"
        $lines += "- **Source:** $($r.source_url)"
        $lines += "- **Publisher:** $($r.publisher)"
        $lines += "- **Artifactory:** $($r.artifactory)"
        $lines += "- **Rationale:** $($r.risk_rationale)"
        if ($r.notes) { $lines += "- **Notes:** $($r.notes)" }
        $lines += ''
    }

    $lines += '## By Category'
    $lines += ''
    $categories = $ledger | Group-Object category
    foreach ($grp in $categories) {
        $artiInCat = @($grp.Group | Where-Object { $_.artifactory -eq 'yes' }).Count
        $lines += "### $($grp.Name) ($($grp.Count) items, $artiInCat via Artifactory)"
        foreach ($item in $grp.Group) {
            $lines += "- $($item.name): $($item.source_host) [artifactory=$($item.artifactory), risk=$($item.risk_rating), status=$($item.status)]"
        }
        $lines += ''
    }

    if ($VerificationResults.Count -gt 0) {
        $lines += '## Component Verification'
        $lines += ''
        $lines += '| Component | Status | Detail |'
        $lines += '|-----------|--------|--------|'
        foreach ($v in $VerificationResults) {
            $detail = if ($v.Detail) { $v.Detail -replace '\|', '/' } else { '-' }
            $lines += "| $($v.Name) | $($v.Status) | $detail |"
        }
        $lines += ''
    }

    if ($StepResults.Count -gt 0) {
        $failedSteps = @($StepResults | Where-Object { $_.Success -eq $false })
        if ($failedSteps.Count -gt 0) {
            $lines += '## Failed Steps'
            $lines += ''
            foreach ($s in $failedSteps) {
                $lines += "- $($s.Error)"
            }
            $lines += ''
        }
    }

    $lines += '## Policy Compliance'
    $lines += ''
    $pythonNonArtifactory = @($ledger | Where-Object {
        $_.category -eq 'python-package' -and $_.artifactory -eq 'no'
    })
    $nonPythonArtifactory = @($ledger | Where-Object {
        $_.category -ne 'python-package' -and $_.artifactory -eq 'yes'
    })

    if ($pythonNonArtifactory.Count -eq 0) {
        $lines += '- [PASS] All Python packages routed through Artifactory'
    }
    else {
        $lines += '- [FAIL] Python packages found outside Artifactory:'
        foreach ($p in $pythonNonArtifactory) { $lines += "  - $($p.name)" }
    }

    if ($nonPythonArtifactory.Count -eq 0) {
        $lines += '- [PASS] No non-Python dependencies routed through Artifactory'
    }
    else {
        $lines += '- [WARN] Non-Python dependencies unexpectedly via Artifactory:'
        foreach ($p in $nonPythonArtifactory) { $lines += "  - $($p.name)" }
    }

    $content = $lines -join "`n"
    Set-Content -Path $reportPath -Value $content -Encoding UTF8
    $ledger | ConvertTo-Json -Depth 5 | Set-Content -Path $jsonPath -Encoding UTF8

    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host '  STANDARD PRACTICE DEPENDENCY REPORT' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host "  Total tracked:     $($ledger.Count)" -ForegroundColor White
    Write-Host "  Via Artifactory:   $artifactoryCount (Python packages)" -ForegroundColor Green
    Write-Host "  Trusted upstream:  $trustedCount" -ForegroundColor Green
    Write-Host "  Low / Med / High:  $lowRisk / $mediumRisk / $highRisk" -ForegroundColor White
    Write-Host ''
    Write-Host '  Dependency table (source / risk / artifactory):' -ForegroundColor Cyan
    Write-Host ''

    foreach ($r in ($ledger | Sort-Object category, name)) {
        $artiColor = if ($r.artifactory -eq 'yes') { 'Yellow' } else { 'Green' }
        $riskColor = switch ($r.risk_rating) {
            'Low' { 'Green' }
            'Medium' { 'Yellow' }
            'High' { 'Red' }
        }
        Write-Host "  [$($r.category)] $($r.name)" -ForegroundColor White
        Write-Host "      source:      $($r.source_url)" -ForegroundColor DarkGray
        Write-Host "      artifactory: $($r.artifactory)" -ForegroundColor $artiColor
        Write-Host "      risk:        $($r.risk_rating) - $($r.status)" -ForegroundColor $riskColor
    }

    Write-Host ''
    Write-Host "  Markdown report: $reportPath" -ForegroundColor White
    Write-Host "  JSON report:     $jsonPath" -ForegroundColor DarkGray
    Write-Host ''

    Write-SetupLog "Standard practice report: $reportPath"
    return ($failed -eq 0)
}
#endregion

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