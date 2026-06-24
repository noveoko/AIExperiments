# Shared UI helpers for setup.ps1

$script:SetupLogPath = Join-Path $PSScriptRoot "..\setup.log"
$script:DryRun = $false
$script:TotalSteps = 16

function Initialize-SetupUi {
    param(
        [string]$LogPath,
        [bool]$DryRun = $false
    )
    $script:SetupLogPath = $LogPath
    $script:DryRun = $DryRun
}

function Write-SetupLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $script:SetupLogPath -Value $line -Encoding UTF8
}

function Write-Step {
    param(
        [int]$Number,
        [string]$Title,
        [string]$Description
    )
    Write-Host ""
    Write-Host ("=" * 46) -ForegroundColor Cyan
    Write-Host "  Step $Number of $($script:TotalSteps): $Title" -ForegroundColor Cyan
    Write-Host ("=" * 46) -ForegroundColor Cyan
    Write-Host ""
    if ($Description) {
        Write-Host "  $Description" -ForegroundColor DarkGray
        Write-Host ""
    }
    Write-SetupLog "STEP $Number`: $Title"
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message"
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
    Write-SetupLog "OK: $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
    Write-SetupLog "WARN: $Message"
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
    Write-SetupLog "FAIL: $Message"
}

function Confirm-OrSkip {
    param(
        [string]$Prompt = "Continue?",
        [switch]$DefaultYes
    )
    $suffix = if ($DefaultYes) { "[Y/n/skip]" } else { "[y/N/skip]" }
    $response = Read-Host "  $Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $DefaultYes
    }
    switch ($response.ToLower()) {
        "y" { return $true }
        "yes" { return $true }
        "n" { return $false }
        "no" { return $false }
        "skip" { return "skip" }
        default { return $false }
    }
}

function Read-Secret {
    param([string]$Prompt)
    $secure = Read-Host "  $Prompt" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Invoke-WithRetry {
    param(
        [scriptblock]$Action,
        [string]$Description,
        [int]$MaxAttempts = 3
    )
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            if ($script:DryRun) {
                Write-Info "[dry-run] Would run: $Description"
                return $true
            }
            & $Action
            return $true
        }
        catch {
            Write-Fail "$Description failed (attempt $attempt/$MaxAttempts): $($_.Exception.Message)"
            if ($attempt -lt $MaxAttempts) {
                $retry = Confirm-OrSkip -Prompt "Retry?" -DefaultYes
                if (-not $retry) { return $false }
            }
        }
    }
    return $false
}

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Expand-HomePath {
    param([string]$Path)
    if ($Path -match '^~(/|\\|$)') {
        return $Path -replace '^~', $env:USERPROFILE
    }
    return $Path
}

function Write-VerifyRow {
    param(
        [string]$Component,
        [string]$Status,
        [string]$Detail
    )
    $color = switch ($Status) {
        "OK" { "Green" }
        "WARN" { "Yellow" }
        default { "Red" }
    }
    Write-Host ("{0,-22} {1,-7} {2}" -f $Component, $Status, $Detail) -ForegroundColor $color
}

function Write-SummaryTable {
    param([array]$Results)
    Write-Host ""
    Write-Host "Verification Summary" -ForegroundColor Cyan
    Write-Host ("-" * 60)
    Write-Host ("{0,-22} {1,-7} {2}" -f "Component", "Status", "Detail")
    Write-Host ("-" * 60)
    foreach ($row in $Results) {
        Write-VerifyRow -Component $row.Component -Status $row.Status -Detail $row.Detail
    }
    Write-Host ("-" * 60)
}