# Artifactory setup, snippet parsing, and diagnostics

function New-ArtifactorySettings {
    return [pscustomobject]@{
        SourceName = $null
        Username   = $null
        Token      = $null
        Url        = $null
    }
}

function Parse-ArtifactorySnippet {
    param([string]$SnippetText)

    $settings = New-ArtifactorySettings
    if ([string]::IsNullOrWhiteSpace($SnippetText)) {
        return $settings
    }

    $lines = $SnippetText -split "`r?`n"
    foreach ($rawLine in $lines) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line.StartsWith("#")) { continue }

        if ($line -match 'poetry\s+config\s+http-basic\.([^\s]+)\s+(\S+)\s+(\S+)') {
            $settings.SourceName = $Matches[1]
            $settings.Username = $Matches[2]
            $settings.Token = $Matches[3]
            continue
        }

        if ($line -match 'poetry\s+source\s+add\s+(\S+)\s+(https?://\S+)') {
            if (-not $settings.SourceName) { $settings.SourceName = $Matches[1] }
            $settings.Url = $Matches[2].TrimEnd('/')
            continue
        }

        if ($line -match 'poetry\s+config\s+repositories\.([^\s]+)\s+(https?://\S+)') {
            if (-not $settings.SourceName) { $settings.SourceName = $Matches[1] }
            $settings.Url = $Matches[2].TrimEnd('/')
            continue
        }

        if ($line -match 'POETRY_HTTP_BASIC_([A-Z0-9_]+)_USERNAME=(.+)') {
            $settings.SourceName = $Matches[1].ToLower() -replace '_', '-'
            $settings.Username = $Matches[2].Trim('"', "'")
            continue
        }

        if ($line -match 'POETRY_HTTP_BASIC_([A-Z0-9_]+)_PASSWORD=(.+)') {
            if (-not $settings.SourceName) {
                $settings.SourceName = $Matches[1].ToLower() -replace '_', '-'
            }
            $settings.Token = $Matches[2].Trim('"', "'")
            continue
        }

        if ($line -match 'pip\s+install\b.*--index-url\s+(https?://\S+)') {
            $indexUrl = $Matches[1]
            if ($indexUrl -match '^https?://([^:]+):([^@]+)@(.+)$') {
                $settings.Username = [Uri]::UnescapeDataString($Matches[1])
                $settings.Token = [Uri]::UnescapeDataString($Matches[2])
                $settings.Url = "https://$($Matches[3])".TrimEnd('/')
            }
            else {
                $settings.Url = $indexUrl.TrimEnd('/')
            }
        }
    }

    return $settings
}

function Read-PyprojectArtifactorySource {
    param([string]$ProjectDir)

    $result = @{ Name = $null; Url = $null }
    $pyprojectPath = Join-Path $ProjectDir "pyproject.toml"
    if (-not (Test-Path $pyprojectPath)) { return $result }

    $content = Get-Content $pyprojectPath -Raw
    if ($content -match '(?ms)\[\[tool\.poetry\.source\]\].*?name\s*=\s*"([^"]+)"') {
        $result.Name = $Matches[1]
    }
    if ($content -match '(?ms)\[\[tool\.poetry\.source\]\].*?url\s*=\s*"([^"]+)"') {
        $result.Url = $Matches[1]
    }
    return $result
}

function Get-ArtifactoryTestPackage {
    param([object]$ArtifactoryConfig)
    if ($ArtifactoryConfig.PSObject.Properties.Name -contains "test_package" -and $ArtifactoryConfig.test_package) {
        return $ArtifactoryConfig.test_package
    }
    return "pip"
}

function Show-ArtifactoryPreview {
    param([object]$Settings)

    Write-Host ""
    Write-Host "  Parsed Artifactory settings:" -ForegroundColor Cyan
    Write-Host "    Source name : $($Settings.SourceName)"
    Write-Host "    Username    : $($Settings.Username)"
    $tokenLen = if ($Settings.Token) { $Settings.Token.Length } else { 0 }
    Write-Host "    Token       : $('*' * [Math]::Min(8, $tokenLen)) ($tokenLen chars)"
    Write-Host "    URL         : $($Settings.Url)"
    Write-Host ""
}

function Update-ConfigFromSettings {
    param(
        [object]$Config,
        [object]$Settings,
        [string]$ConfigPath
    )

    $changed = $false
    if ($Settings.SourceName -and $Config.artifactory.source_name -ne $Settings.SourceName) {
        Write-Warn "Snippet source name '$($Settings.SourceName)' differs from config '$($Config.artifactory.source_name)'."
        if (Confirm-OrSkip -Prompt "Update setup.config.json source_name?" -DefaultYes) {
            $Config.artifactory.source_name = $Settings.SourceName
            $changed = $true
        }
    }
    if ($Settings.Url -and $Config.artifactory.url -ne $Settings.Url) {
        Write-Warn "Snippet URL differs from config URL."
        if (Confirm-OrSkip -Prompt "Update setup.config.json url?" -DefaultYes) {
            $Config.artifactory.url = $Settings.Url
            $changed = $true
        }
    }
    if ($Settings.Username -and $Config.artifactory.username -ne $Settings.Username) {
        if (Confirm-OrSkip -Prompt "Update setup.config.json username?" -DefaultYes) {
            $Config.artifactory.username = $Settings.Username
            $changed = $true
        }
    }
    if ($changed -and $ConfigPath) {
        $Config | ConvertTo-Json -Depth 10 | Set-Content -Path $ConfigPath -Encoding UTF8
        Write-Success "Updated setup.config.json"
    }
}

function Apply-ArtifactoryConfig {
    param(
        [object]$Settings,
        [string]$ProjectDir
    )

    if (-not $Settings.SourceName -or -not $Settings.Username -or -not $Settings.Token) {
        throw "Incomplete Artifactory settings. Need source name, username, and token."
    }

    if (-not (Test-CommandExists "poetry")) {
        throw "Poetry is not installed. Run step 4 first."
    }

    poetry config "http-basic.$($Settings.SourceName)" $Settings.Username $Settings.Token
    Write-SetupLog "Artifactory: configured http-basic.$($Settings.SourceName) for user $($Settings.Username) (token length $($Settings.Token.Length))"
    Write-Success "Credentials saved for Poetry source '$($Settings.SourceName)'."

    if ($ProjectDir -and (Test-Path $ProjectDir)) {
        $pyproject = Read-PyprojectArtifactorySource -ProjectDir $ProjectDir
        if ($pyproject.Name -and $pyproject.Name -ne $Settings.SourceName) {
            Write-Warn "pyproject.toml source name '$($pyproject.Name)' does not match '$($Settings.SourceName)'."
            Write-Info "Fix: in pyproject.toml, set name = `"$($Settings.SourceName)`" under [[tool.poetry.source]]."
        }
        if ($Settings.Url -and $pyproject.Url -and $pyproject.Url -ne $Settings.Url) {
            Write-Warn "pyproject.toml URL differs from configured URL."
            Write-Info "Expected: $($Settings.Url)"
            Write-Info "Found:    $($pyproject.Url)"
        }
    }

    return $true
}

function Add-ArtifactoryDiagnostic {
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

function Test-ArtifactorySetup {
    param(
        [object]$Config,
        [string]$ProjectDir,
        [switch]$Verbose
    )

    $results = [System.Collections.Generic.List[object]]::new()
    $fixes = [System.Collections.Generic.List[string]]::new()
    $artifactory = $Config.artifactory
    $sourceName = $artifactory.source_name
    $url = $artifactory.url
    $testPackage = Get-ArtifactoryTestPackage -ArtifactoryConfig $artifactory

    if (Test-CommandExists "poetry") {
        $ver = poetry --version 2>&1
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Poetry installed" -Status "OK" -Detail $ver -FixHint $null
    }
    else {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Poetry installed" -Status "FAIL" -Detail "not found" -FixHint "Re-run step 4: .\setup.ps1 -Step 4"
        return @{ Results = $results; Fixes = $fixes }
    }

    $poetryConfig = poetry config --list 2>&1 | Out-String
    $username = $null
    $token = $null
    if ($poetryConfig -match "http-basic\.$([regex]::Escape($sourceName))\.username.*?['""]([^'""]+)['""]") {
        $username = $Matches[1]
    }
    if ($poetryConfig -match "http-basic\.$([regex]::Escape($sourceName))\.password.*?['""]([^'""]+)['""]") {
        $token = $Matches[1]
    }

    if ($username -and $token) {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Credentials configured" -Status "OK" -Detail "http-basic.$sourceName" -FixHint $null
    }
    else {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Credentials configured" -Status "FAIL" -Detail "http-basic.$sourceName missing" -FixHint "Run .\setup.ps1 -ArtifactorySetup and paste your JFrog snippet"
    }

    if ($url -match '^https://' -and $url -match '/simple$') {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "URL format" -Status "OK" -Detail "valid PyPI simple index" -FixHint $null
    }
    elseif ($url -match '^https://') {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "URL format" -Status "WARN" -Detail "missing /simple suffix" -FixHint "Append /simple to URL: $url/simple"
    }
    else {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "URL format" -Status "FAIL" -Detail "invalid or missing URL" -FixHint "Set artifactory.url in setup.config.json to your JFrog PyPI simple index URL"
    }

    if ($ProjectDir -and (Test-Path $ProjectDir)) {
        $pyproject = Read-PyprojectArtifactorySource -ProjectDir $ProjectDir
        if ($pyproject.Name -eq $sourceName) {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Source name match" -Status "OK" -Detail $sourceName -FixHint $null
        }
        elseif ($pyproject.Name) {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Source name match" -Status "FAIL" -Detail "pyproject='$($pyproject.Name)' config='$sourceName'" -FixHint "In pyproject.toml, set [[tool.poetry.source]] name = `"$sourceName`""
        }
        else {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Source name match" -Status "WARN" -Detail "pyproject.toml not found yet" -FixHint "Run step 9 to create the Poetry project"
        }
    }

    $proxy = @()
    if ($env:HTTP_PROXY) { $proxy += "HTTP_PROXY=$($env:HTTP_PROXY)" }
    if ($env:HTTPS_PROXY) { $proxy += "HTTPS_PROXY=$($env:HTTPS_PROXY)" }
    if ($proxy.Count -gt 0) {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Proxy detected" -Status "OK" -Detail ($proxy -join ", ") -FixHint $null
    }
    else {
        Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Proxy detected" -Status "OK" -Detail "none" -FixHint $null
    }

    if ($url) {
        try {
            $uri = [Uri]$url
            $hostname = $uri.Host
            $null = [System.Net.Dns]::GetHostAddresses($hostname)
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "DNS resolve" -Status "OK" -Detail $hostname -FixHint $null
        }
        catch {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "DNS resolve" -Status "FAIL" -Detail $_.Exception.Message -FixHint "Check VPN connection and DNS settings"
        }

        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect($hostname, 443)
            $tcp.Close()
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "TCP connect (443)" -Status "OK" -Detail "reachable" -FixHint $null
        }
        catch {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "TCP connect (443)" -Status "FAIL" -Detail $_.Exception.Message -FixHint "Check firewall or corporate proxy settings"
        }

        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
            $detail = "HTTP $($response.StatusCode)"
            $status = if ($response.StatusCode -in 200, 401) { "OK" } else { "WARN" }
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "HTTP probe (no auth)" -Status $status -Detail $detail -FixHint $null
        }
        catch {
            $statusCode = $null
            if ($_.Exception.Response) { $statusCode = [int]$_.Exception.Response.StatusCode }
            if ($statusCode -eq 401) {
                Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "HTTP probe (no auth)" -Status "OK" -Detail "401 Unauthorized (expected)" -FixHint $null
            }
            else {
                $detail = if ($statusCode) { "HTTP $statusCode" } else { $_.Exception.Message }
                Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "HTTP probe (no auth)" -Status "FAIL" -Detail $detail -FixHint "Verify artifactory.url points to the correct PyPI repository"
            }
        }

        if ($username -and $token) {
            try {
                $pair = "${username}:${token}"
                $bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
                $base64 = [System.Convert]::ToBase64String($bytes)
                $response = Invoke-WebRequest -Uri $url -Headers @{ Authorization = "Basic $base64" } -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
                Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Auth probe" -Status "OK" -Detail "HTTP $($response.StatusCode)" -FixHint $null
            }
            catch {
                $statusCode = $null
                if ($_.Exception.Response) { $statusCode = [int]$_.Exception.Response.StatusCode }
                $detail = if ($statusCode) { "HTTP $statusCode" } else { $_.Exception.Message }
                $fix = switch ($statusCode) {
                    401 { "Regenerate Artifactory identity token; username/token may be wrong" }
                    403 { "Token may lack read permission on the repository" }
                    default { "Verify username and token from Artifactory Set Me Up page" }
                }
                Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Auth probe" -Status "FAIL" -Detail $detail -FixHint $fix
            }
        }
        else {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Auth probe" -Status "WARN" -Detail "skipped (no credentials)" -FixHint $null
        }
    }

    if ($username -and $token -and $url) {
        try {
            $searchOut = poetry search $testPackage --source $sourceName 2>&1 | Out-String
            if ($LASTEXITCODE -eq 0 -and $searchOut -notmatch 'error|401|403|404') {
                Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Poetry index access" -Status "OK" -Detail "search $testPackage succeeded" -FixHint $null
            }
            else {
                $detail = ($searchOut.Trim() -replace $token, '***' | Select-Object -First 1)
                if ($detail.Length -gt 80) { $detail = $detail.Substring(0, 80) + "..." }
                Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Poetry index access" -Status "FAIL" -Detail $detail -FixHint "Ensure source name in pyproject.toml matches '$sourceName' and credentials are valid"
                if ($Verbose) { Write-Host "  [verbose] $searchOut" -ForegroundColor DarkGray }
            }
        }
        catch {
            Add-ArtifactoryDiagnostic -Results ([ref]$results) -Fixes ([ref]$fixes) -Check "Poetry index access" -Status "FAIL" -Detail $_.Exception.Message -FixHint "Run .\setup.ps1 -ArtifactoryTroubleshoot -Verbose for details"
        }
    }

    return @{ Results = $results; Fixes = ($fixes | Select-Object -Unique) }
}

function Write-ArtifactoryDiagnosticReport {
    param(
        [array]$Results,
        [array]$Fixes
    )

    Write-Host ""
    Write-Host "Artifactory Diagnostics" -ForegroundColor Cyan
    Write-Host ("-" * 60)
    Write-Host ("{0,-24} {1,-7} {2}" -f "Check", "Status", "Detail")
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

function Get-GuidedArtifactorySettings {
    param([object]$ArtifactoryConfig)

    $settings = New-ArtifactorySettings
    $settings.SourceName = $ArtifactoryConfig.source_name
    $settings.Username = $ArtifactoryConfig.username
    $settings.Url = $ArtifactoryConfig.url

    $envVar = $ArtifactoryConfig.token_env_var
    if ($envVar) {
        $settings.Token = [Environment]::GetEnvironmentVariable($envVar)
    }
    if ([string]::IsNullOrWhiteSpace($settings.Token)) {
        $settings.Token = Read-Secret -Prompt "Enter Artifactory token (input hidden):"
    }
    return $settings
}

function Get-PastedArtifactorySettings {
    param(
        [object]$Config,
        [string]$ConfigPath,
        [string]$SnippetText
    )

    if (-not $SnippetText) {
        Write-Info "Paste your Artifactory 'Set Me Up' snippet below."
        Write-Info "When finished, press Enter on an empty line:"
        Write-Host ""
        $lines = [System.Collections.Generic.List[string]]::new()
        while ($true) {
            $line = Read-Host
            if ([string]::IsNullOrWhiteSpace($line)) { break }
            $lines.Add($line)
        }
        $SnippetText = $lines -join "`n"
    }

    $settings = Parse-ArtifactorySnippet -SnippetText $SnippetText
    if (-not $settings.SourceName) { $settings.SourceName = $Config.artifactory.source_name }
    if (-not $settings.Url) { $settings.Url = $Config.artifactory.url }
    if (-not $settings.Username) { $settings.Username = $Config.artifactory.username }

    if (-not $settings.Token) {
        $settings.Token = Read-Secret -Prompt "Snippet had no token. Enter Artifactory token:"
    }

    Show-ArtifactoryPreview -Settings $settings
    Update-ConfigFromSettings -Config $Config -Settings $settings -ConfigPath $ConfigPath

    if (-not (Confirm-OrSkip -Prompt "Apply these settings?" -DefaultYes)) {
        Write-Warn "Artifactory setup cancelled."
        return $null
    }
    return $settings
}

function Get-ManualArtifactorySettings {
    param([object]$Config)

    $settings = New-ArtifactorySettings
    $settings.SourceName = Read-Host "  Source name [$($Config.artifactory.source_name)]"
    if ([string]::IsNullOrWhiteSpace($settings.SourceName)) { $settings.SourceName = $Config.artifactory.source_name }

    $settings.Username = Read-Host "  Username [$($Config.artifactory.username)]"
    if ([string]::IsNullOrWhiteSpace($settings.Username)) { $settings.Username = $Config.artifactory.username }

    $settings.Url = Read-Host "  Repository URL [$($Config.artifactory.url)]"
    if ([string]::IsNullOrWhiteSpace($settings.Url)) { $settings.Url = $Config.artifactory.url }

    $settings.Token = Read-Secret -Prompt "Enter Artifactory token (input hidden):"
    Show-ArtifactoryPreview -Settings $settings

    if (-not (Confirm-OrSkip -Prompt "Apply these settings?" -DefaultYes)) {
        return $null
    }
    return $settings
}

function Invoke-ArtifactorySetup {
    param(
        [object]$Config,
        [string]$ConfigPath,
        [string]$ProjectDir,
        [string]$SnippetText,
        [ValidateSet("menu", "guided", "paste", "manual", "troubleshoot")]
        [string]$Mode = "menu",
        [switch]$Verbose
    )

    $settings = $null
    $runDiagnostics = $true

    if ($Mode -eq "menu" -and $SnippetText) {
        $Mode = "paste"
    }

    if ($Mode -eq "menu") {
        Write-Host ""
        Write-Host "  How do you want to configure Artifactory?" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "    [1] Guided        - use setup.config.json + ARTIFACTORY_TOKEN"
        Write-Host "    [2] Paste snippet - paste commands from Artifactory Set Me Up"
        Write-Host "    [3] Manual entry  - type source name, username, token, URL"
        Write-Host "    [4] Troubleshoot  - test existing setup without changing anything"
        Write-Host ""
        $choice = Read-Host "  Choose [1-4]"
        $Mode = switch ($choice) {
            "2" { "paste" }
            "3" { "manual" }
            "4" { "troubleshoot" }
            default { "guided" }
        }
    }

    switch ($Mode) {
        "guided" {
            $settings = Get-GuidedArtifactorySettings -ArtifactoryConfig $Config.artifactory
            if ([string]::IsNullOrWhiteSpace($settings.Token)) {
                Write-Warn "No Artifactory token provided."
                return $false
            }
            Apply-ArtifactoryConfig -Settings $settings -ProjectDir $ProjectDir | Out-Null
        }
        "paste" {
            $settings = Get-PastedArtifactorySettings -Config $Config -ConfigPath $ConfigPath -SnippetText $SnippetText
            if (-not $settings) { return $false }
            Apply-ArtifactoryConfig -Settings $settings -ProjectDir $ProjectDir | Out-Null
        }
        "manual" {
            $settings = Get-ManualArtifactorySettings -Config $Config
            if (-not $settings) { return $false }
            Apply-ArtifactoryConfig -Settings $settings -ProjectDir $ProjectDir | Out-Null
        }
        "troubleshoot" {
            $runDiagnostics = $true
            $settings = $null
        }
    }

    if ($runDiagnostics) {
        $diag = Test-ArtifactorySetup -Config $Config -ProjectDir $ProjectDir -Verbose:$Verbose
        Write-ArtifactoryDiagnosticReport -Results $diag.Results -Fixes $diag.Fixes
        $failures = $diag.Results | Where-Object { $_.Status -eq "FAIL" }
        if ($failures.Count -gt 0) {
            Write-Info "For help: .\setup.ps1 -ArtifactoryTroubleshoot"
            return $false
        }
    }
    return $true
}