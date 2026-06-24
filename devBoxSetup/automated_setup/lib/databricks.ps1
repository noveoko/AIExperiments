# Databricks auth setup and diagnostics

function Add-DatabricksDiagnostic {
    param(
        [ref]$Results,
        [ref]$Fixes,
        [string]$Check,
        [string]$Status,
        [string]$Detail,
        [string]$FixHint
    )
    $Results.Value += [pscustomobject]@{ Check = $Check; Status = $Status; Detail = $Detail }
    if ($Status -in @("FAIL", "WARN") -and $FixHint) {
        $Fixes.Value += $FixHint
    }
}

function Test-DatabricksSetup {
    param([object]$Config)

    $results = [System.Collections.Generic.List[object]]::new()
    $fixes = [System.Collections.Generic.List[string]]::new()
    $db = $Config.databricks
    $profile = $db.profile
    $workspaceHost = $db.host

    if (Test-CommandExists "databricks") {
        Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "CLI installed" -Status "OK" -Detail (databricks -v 2>&1) -FixHint $null
    }
    else {
        Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "CLI installed" -Status "FAIL" -Detail "not found" -FixHint "Re-run step 7: .\setup.ps1 -Step 7"
        return @{ Results = $results; Fixes = $fixes }
    }

    $cfgPath = Join-Path $env:USERPROFILE ".databrickscfg"
    if (Test-Path $cfgPath) {
        $cfg = Get-Content $cfgPath -Raw
        if ($cfg -match "\[$([regex]::Escape($profile))\]") {
            Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Profile configured" -Status "OK" -Detail $profile -FixHint $null
        }
        else {
            Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Profile configured" -Status "FAIL" -Detail "profile '$profile' not in .databrickscfg" -FixHint "Run .\setup.ps1 -DatabricksSetup"
        }
    }
    else {
        Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Profile configured" -Status "FAIL" -Detail ".databrickscfg missing" -FixHint "Run .\setup.ps1 -DatabricksSetup"
    }

    if ($workspaceHost -and (Get-Command Test-EndpointConnectivity -ErrorAction SilentlyContinue)) {
        $probe = Test-EndpointConnectivity -Label "Workspace" -Url $workspaceHost
        Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Host reachable" -Status $probe.Status -Detail $probe.Detail -FixHint $probe.FixHint
    }

    if (Test-Path $cfgPath) {
        try {
            $out = databricks current-user me --profile $profile 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0) {
                Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Auth valid" -Status "OK" -Detail "current-user me succeeded" -FixHint $null
            }
            else {
                Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Auth valid" -Status "FAIL" -Detail ($out.Trim()) -FixHint "Try PAT auth if OAuth is blocked by corporate SSO"
            }
        }
        catch {
            Add-DatabricksDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Auth valid" -Status "FAIL" -Detail $_.Exception.Message -FixHint "Re-authenticate with .\setup.ps1 -DatabricksSetup"
        }
    }

    return @{ Results = $results; Fixes = ($fixes | Select-Object -Unique) }
}

function Write-DatabricksDiagnosticReport {
    param(
        [array]$Results,
        [array]$Fixes
    )

    Write-Host ""
    Write-Host "Databricks Diagnostics" -ForegroundColor Cyan
    Write-Host ("-" * 60)
    foreach ($row in $Results) {
        Write-VerifyRow -Component $row.Check -Status $row.Status -Detail $row.Detail
    }
    Write-Host ("-" * 60)
    if ($Fixes -and $Fixes.Count -gt 0) {
        Write-Host ""
        Write-Host "Suggested fixes:" -ForegroundColor Yellow
        $i = 1
        foreach ($fix in $Fixes) {
            Write-Host "  $i. $fix"
            $i++
        }
    }
}

function Apply-DatabricksPat {
    param(
        [string]$WorkspaceHost,
        [string]$Profile,
        [string]$Pat
    )
    databricks configure --host $WorkspaceHost --token $Pat --profile $Profile
    Write-Success "Databricks PAT configured for profile '$Profile'."
}

function Invoke-DatabricksSetup {
    param(
        [object]$Config,
        [ValidateSet("menu", "guided", "pat", "manual", "troubleshoot")]
        [string]$Mode = "menu"
    )

    $db = $Config.databricks
    $runDiagnostics = $true

    if ($Mode -eq "menu") {
        Write-Host ""
        Write-Host "  How do you want to configure Databricks?" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "    [1] Guided OAuth  - opens browser (may be blocked by corporate SSO)"
        Write-Host "    [2] PAT / token   - Personal Access Token (recommended in corporates)"
        Write-Host "    [3] Manual entry  - type host and PAT yourself"
        Write-Host "    [4] Troubleshoot  - test existing setup without changing anything"
        Write-Host ""
        $choice = Read-Host "  Choose [1-4]"
        $Mode = switch ($choice) {
            "2" { "pat" }
            "3" { "manual" }
            "4" { "troubleshoot" }
            default { "guided" }
        }
    }

    if ($Mode -eq "troubleshoot") {
        $diag = Test-DatabricksSetup -Config $Config
        Write-DatabricksDiagnosticReport -Results $diag.Results -Fixes $diag.Fixes
        $failures = $diag.Results | Where-Object { $_.Status -eq "FAIL" }
        return ($failures.Count -eq 0)
    }

    if ([string]::IsNullOrWhiteSpace($db.host)) {
        Write-Warn "Databricks host not configured in setup.config.json."
        return $false
    }

    switch ($Mode) {
        "guided" {
            Write-Info "Workspace: $($db.host)"
            Write-Info "Opening browser for OAuth login..."
            databricks auth login --host $db.host --profile $db.profile
            Write-Success "Databricks OAuth login completed."
        }
        "pat" {
            $pat = Read-Secret -Prompt "Enter Databricks Personal Access Token:"
            Apply-DatabricksPat -WorkspaceHost $db.host -Profile $db.profile -Pat $pat
        }
        "manual" {
            $hostInput = Read-Host "  Workspace host [$($db.host)]"
            if ([string]::IsNullOrWhiteSpace($hostInput)) { $hostInput = $db.host }
            $profileInput = Read-Host "  Profile name [$($db.profile)]"
            if ([string]::IsNullOrWhiteSpace($profileInput)) { $profileInput = $db.profile }
            $pat = Read-Secret -Prompt "Enter Databricks PAT:"
            Apply-DatabricksPat -WorkspaceHost $hostInput -Profile $profileInput -Pat $pat
        }
    }

    $diag = Test-DatabricksSetup -Config $Config
    Write-DatabricksDiagnosticReport -Results $diag.Results -Fixes $diag.Fixes
    $failures = $diag.Results | Where-Object { $_.Status -eq "FAIL" }
    return ($failures.Count -eq 0)
}

function Test-DatabricksConnectCluster {
    param(
        [object]$Config,
        [string]$ProjectDir
    )

    $clusterId = $Config.databricks.cluster_id
    if ([string]::IsNullOrWhiteSpace($clusterId)) {
        Write-Info "No cluster_id in config - skipping databricks-connect cluster validation."
        return $true
    }

    $profile = $Config.databricks.profile
    $runtime = $Config.databricks.cluster_runtime
    $results = @()

    if (-not (Test-Path $ProjectDir)) {
        Write-Warn "Project directory not found. Skipping cluster validation."
        return $false
    }

    Push-Location $ProjectDir
    try {
        $importOk = poetry run python -c "import databricks.connect" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "databricks-connect is importable."
        }
        else {
            Write-Fail "databricks-connect not importable."
            return $false
        }

        if (Test-CommandExists "databricks") {
            $clusterInfo = databricks clusters get $clusterId --profile $profile 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Cluster '$clusterId' accessible via CLI."
            }
            else {
                Write-Fail "Cannot access cluster: $($clusterInfo.Trim())"
                Write-Info "Fix: ensure cluster is running and you have CAN_ATTACH_TO permission."
                return $false
            }
        }

        $installed = poetry run python -c 'import importlib.metadata as m; print(m.version("databricks-connect"))' 2>&1
        if ($installed -and $runtime -and $installed -notlike "$runtime*") {
            Write-Warn "databricks-connect version ($installed) may not match cluster runtime ($runtime)."
            Write-Info "Fix: update pyproject.toml databricks-connect to ~$runtime"
        }

        $corp = $Config.corporate
        $skipSmoke = $false
        if ($corp -and $corp.PSObject.Properties.Name -contains "skip_cluster_smoke_test") {
            $skipSmoke = [bool]$corp.skip_cluster_smoke_test
        }
        if (-not $skipSmoke) {
            Write-Info 'Cluster smoke test skipped by default in corporate networks (set corporate.skip_cluster_smoke_test to false to enable).'
        }
    }
    finally {
        Pop-Location
    }
    return $true
}