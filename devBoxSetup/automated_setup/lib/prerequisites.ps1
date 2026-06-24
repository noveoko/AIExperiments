# Prerequisites wizard and corporate preflight checks

function Show-TokenHelp {
    Write-Host ""
    Write-Host "  Token how-to:" -ForegroundColor Cyan
    Write-Host "    Artifactory : JFrog > User Profile > Identity Token > Generate"
    Write-Host "    Databricks  : Workspace > User Settings > Developer > Access Tokens"
    Write-Host "    Or use OAuth at step 9 if your org allows browser login"
    Write-Host ""
}

function Invoke-PrerequisitesWizard {
    Write-Host ""
    Write-Host "  Before we install anything, confirm you have:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    [ ] Connected to corporate VPN (if required)"
    Write-Host "    [ ] Artifactory identity token (or will paste snippet at step 8)"
    Write-Host "    [ ] Databricks workspace access approved by IT"
    Write-Host "    [ ] Databricks PAT ready (only if OAuth is blocked)"
    Write-Host "    [ ] Admin rights OR pre-approved software via Software Center"
    Write-Host ""

    $response = Read-Host "  Press Enter when ready, or type 'help' for token links"
    if ($response -eq "help") {
        Show-TokenHelp
        $null = Read-Host "  Press Enter when ready to continue"
    }
}

function Test-ExecutionPolicy {
    $policy = Get-ExecutionPolicy -Scope CurrentUser
    if ($policy -eq "Restricted") {
        Write-Warn "PowerShell execution policy is Restricted."
        Write-Info "Fix: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned"
        return $false
    }
    Write-Info "Execution policy: $policy"
    return $true
}

function Test-AdminRights {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if ($isAdmin) {
        Write-Info "Running with administrator privileges."
    }
    else {
        Write-Warn "Not running as administrator. winget installs may require elevation or IT pre-approval."
    }
    return $true
}

function Test-WingetAvailable {
    if (Test-CommandExists "winget") {
        Write-Info "winget is available."
        return $true
    }
    Write-Warn "winget not found. Use Software Center for Git, VS Code, and Databricks CLI."
    return $false
}

function Test-ConfiguredHostReachability {
    param([object]$Config)

    if (-not (Get-Command Test-EndpointConnectivity -ErrorAction SilentlyContinue)) {
        return $true
    }

    $probes = @()
    if ($Config.artifactory.url) {
        $probes += Test-EndpointConnectivity -Label "Artifactory (preflight)" -Url $Config.artifactory.url
    }
    if ($Config.databricks.host) {
        $probes += Test-EndpointConnectivity -Label "Databricks (preflight)" -Url $Config.databricks.host
    }

    if ($probes.Count -eq 0) { return $true }

    $failures = $probes | Where-Object { $_.Status -eq "FAIL" }
    foreach ($p in $probes) {
        if ($p.Status -eq "OK") {
            Write-Success "$($p.Label): reachable"
        }
        elseif ($p.Status -eq "FAIL") {
            Write-Warn "$($p.Label): $($p.Detail)"
            if ($p.FixHint) { Write-Info "  $($p.FixHint)" }
        }
        else {
            Write-Info "$($p.Label): $($p.Detail)"
        }
    }

    if ($failures.Count -gt 0) {
        Write-Warn "Some corporate endpoints are unreachable. Step 2 (proxy/SSL) may fix this."
        if (-not (Confirm-OrSkip -Prompt "Continue anyway?" -DefaultYes)) {
            return $false
        }
    }
    return $true
}

function Invoke-PrerequisitesChecks {
    param(
        [string]$ConfigPath,
        [object]$Config
    )

    Invoke-PrerequisitesWizard
    Test-ExecutionPolicy | Out-Null
    Test-AdminRights | Out-Null
    Test-WingetAvailable | Out-Null
    Test-ConfiguredHostReachability -Config $Config | Out-Null
    return $true
}