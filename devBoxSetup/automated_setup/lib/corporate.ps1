# Corporate network: proxy, SSL, connectivity probes, IT export

function Get-CorporateConfig {
    param([object]$Config)
    if ($Config.PSObject.Properties.Name -contains "corporate" -and $Config.corporate) {
        return $Config.corporate
    }
    return [pscustomobject]@{
        proxy_url               = ""
        proxy_username          = ""
        no_proxy                = "localhost,127.0.0.1"
        ca_bundle_path          = ""
        github_mirror           = ""
        skip_cluster_smoke_test = $false
    }
}

function Get-UrlHostname {
    param([string]$Url)
    if ([string]::IsNullOrWhiteSpace($Url)) { return $null }
    try { return ([Uri]$Url).Host } catch { return $null }
}

function Get-DetectedSystemProxy {
    $proxy = $env:HTTPS_PROXY
    if (-not $proxy) { $proxy = $env:HTTP_PROXY }
    if ($proxy) { return $proxy }

    try {
        $winhttp = netsh winhttp show proxy 2>&1 | Out-String
        if ($winhttp -match 'Proxy Server\(s\)\s*:\s*(\S+)') {
            return $Matches[1]
        }
    }
    catch { }

    try {
        $regProxy = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -ErrorAction SilentlyContinue
        if ($regProxy.ProxyEnable -eq 1 -and $regProxy.ProxyServer) {
            return "http://$($regProxy.ProxyServer)"
        }
    }
    catch { }

    return $null
}

function Set-CorporateProxy {
    param(
        [string]$ProxyUrl,
        [string]$NoProxy
    )
    if ([string]::IsNullOrWhiteSpace($ProxyUrl)) { return $false }

    $env:HTTP_PROXY = $ProxyUrl
    $env:HTTPS_PROXY = $ProxyUrl
    $env:NO_PROXY = $NoProxy
    [Environment]::SetEnvironmentVariable("HTTP_PROXY", $ProxyUrl, "User")
    [Environment]::SetEnvironmentVariable("HTTPS_PROXY", $ProxyUrl, "User")
    [Environment]::SetEnvironmentVariable("NO_PROXY", $NoProxy, "User")

    if (Test-CommandExists "git") {
        git config --global http.proxy $ProxyUrl 2>$null
        git config --global https.proxy $ProxyUrl 2>$null
    }

    Write-SetupLog "Corporate: proxy set to $ProxyUrl (no_proxy=$NoProxy)"
    Write-Success "Proxy configured: $ProxyUrl"
    return $true
}

function Set-CorporateCaBundle {
    param([string]$CaBundlePath)

    if (-not (Test-Path $CaBundlePath)) {
        Write-Warn "CA bundle not found: $CaBundlePath"
        return $false
    }

    $env:SSL_CERT_FILE = $CaBundlePath
    $env:REQUESTS_CA_BUNDLE = $CaBundlePath
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $CaBundlePath, "User")
    [Environment]::SetEnvironmentVariable("REQUESTS_CA_BUNDLE", $CaBundlePath, "User")

    if (Test-CommandExists "git") {
        git config --global http.sslCAInfo $CaBundlePath 2>$null
    }

    Write-SetupLog "Corporate: CA bundle set to $CaBundlePath"
    Write-Success "Corporate CA bundle configured."
    return $true
}

function Test-EndpointConnectivity {
    param(
        [string]$Label,
        [string]$Url
    )

    $result = [pscustomobject]@{
        Label      = $Label
        Url        = $Url
        Status     = "SKIP"
        Detail     = "not configured"
        FixHint    = $null
    }

    if ([string]::IsNullOrWhiteSpace($Url)) { return $result }

    $hostname = Get-UrlHostname -Url $Url
    if (-not $hostname) {
        $result.Status = "FAIL"
        $result.Detail = "invalid URL"
        $result.FixHint = "Check URL in setup.config.json"
        return $result
    }

    try {
        $null = [System.Net.Dns]::GetHostAddresses($hostname)
        $dnsOk = $true
    }
    catch {
        $result.Status = "FAIL"
        $result.Detail = "DNS failed: $($_.Exception.Message)"
        $result.FixHint = "Connect to VPN and verify DNS for $hostname"
        return $result
    }

    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect($hostname, 443)
        $tcp.Close()
    }
    catch {
        $result.Status = "FAIL"
        $result.Detail = "TCP 443 blocked: $($_.Exception.Message)"
        $result.FixHint = "Ask IT to allow outbound HTTPS to $hostname (see -GenerateItWhitelist)"
        return $result
    }

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        $result.Status = "OK"
        $result.Detail = "HTTP $($response.StatusCode)"
        return $result
    }
    catch {
        $statusCode = $null
        if ($_.Exception.Response) { $statusCode = [int]$_.Exception.Response.StatusCode }
        $msg = $_.Exception.Message

        if ($msg -match 'SSL|TLS|certificate|trust') {
            $result.Status = "FAIL"
            $result.Detail = "SSL/TLS error"
            $result.FixHint = "Set corporate.ca_bundle_path in config and re-run step 2"
            return $result
        }
        if ($statusCode -eq 401 -or $statusCode -eq 407) {
            $result.Status = "OK"
            $result.Detail = "HTTP $statusCode (host reachable)"
            return $result
        }
        if ($statusCode) {
            $result.Status = "WARN"
            $result.Detail = "HTTP $statusCode"
            $result.FixHint = "Host reachable but returned unexpected status"
            return $result
        }

        $result.Status = "FAIL"
        $result.Detail = $msg
        $result.FixHint = "Check proxy settings (step 2) or VPN connection"
        return $result
    }
}

function Write-ConnectivityReport {
    param([array]$Results)

    Write-Host ""
    Write-Host "Connectivity Probes" -ForegroundColor Cyan
    Write-Host ("-" * 60)
    foreach ($r in $Results) {
        Write-VerifyRow -Component $r.Label -Status $r.Status -Detail $r.Detail
        if ($r.FixHint) { Write-Info "  Fix: $($r.FixHint)" }
    }
    Write-Host ("-" * 60)
}

function Invoke-CorporateNetworkSetup {
    param([object]$Config)

    $corp = Get-CorporateConfig -Config $Config
    $detected = Get-DetectedSystemProxy
    $proxyUrl = $corp.proxy_url
    if ([string]::IsNullOrWhiteSpace($proxyUrl) -and $detected) {
        Write-Info "Detected system proxy: $detected"
        if (Confirm-OrSkip -Prompt "Use detected proxy?" -DefaultYes) {
            $proxyUrl = $detected
        }
    }
    if ([string]::IsNullOrWhiteSpace($proxyUrl)) {
        $proxyUrl = Read-Host "  Proxy URL (leave blank if none, e.g. http://proxy.corp:8080)"
    }

    $artHost = Get-UrlHostname -Url $Config.artifactory.url
    $dbHost = Get-UrlHostname -Url $Config.databricks.host
    $noProxy = $corp.no_proxy
    if ($artHost -and $noProxy -notlike "*$artHost*") { $noProxy = "$noProxy,$artHost" }
    if ($dbHost -and $noProxy -notlike "*$dbHost*") { $noProxy = "$noProxy,$dbHost" }

    if (-not [string]::IsNullOrWhiteSpace($proxyUrl)) {
        Set-CorporateProxy -ProxyUrl $proxyUrl -NoProxy $noProxy | Out-Null
    }
    else {
        Write-Info "No proxy configured."
    }

    $caPath = $corp.ca_bundle_path
    if ([string]::IsNullOrWhiteSpace($caPath)) {
        $caPath = Read-Host "  CA bundle path (leave blank if not needed)"
    }
    if (-not [string]::IsNullOrWhiteSpace($caPath)) {
        Set-CorporateCaBundle -CaBundlePath $caPath | Out-Null
    }

    $probes = @(
        (Test-EndpointConnectivity -Label "Artifactory" -Url $Config.artifactory.url)
        (Test-EndpointConnectivity -Label "Databricks" -Url $Config.databricks.host)
        (Test-EndpointConnectivity -Label "GitHub" -Url "https://github.com")
        (Test-EndpointConnectivity -Label "Poetry installer" -Url "https://install.python-poetry.org")
    )
    Write-ConnectivityReport -Results $probes

    $failures = $probes | Where-Object { $_.Status -eq "FAIL" }
    if ($failures.Count -gt 0) {
        Write-Warn "Some endpoints are unreachable. Run -GenerateItWhitelist to open an IT ticket."
        return $false
    }
    return $true
}

function Get-ItWhitelistHosts {
    param([object]$Config)

    $hosts = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $static = @(
        "github.com"
        "raw.githubusercontent.com"
        "install.python-poetry.org"
        "www.python.org"
        "pypi.org"
    )
    foreach ($h in $static) { [void]$hosts.Add($h) }

    $art = Get-UrlHostname -Url $Config.artifactory.url
    $db = Get-UrlHostname -Url $Config.databricks.host
    if ($art) { [void]$hosts.Add($art) }
    if ($db) { [void]$hosts.Add($db) }

    return $hosts
}

function Export-ItWhitelist {
    param(
        [object]$Config,
        [string]$OutputPath
    )

    $hosts = Get-ItWhitelistHosts -Config $Config
    $lines = @(
        "# IT Firewall / Proxy Whitelist Request"
        "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "# Machine: $env:COMPUTERNAME | User: $env:USERNAME"
        ""
        "Outbound HTTPS (TCP 443) required for:"
    )
    foreach ($h in ($hosts | Sort-Object)) {
        $note = switch -Regex ($h) {
            "jfrog|artifactory" { "Artifactory PyPI" }
            "databricks" { "Databricks workspace" }
            "github" { "pre-commit hooks, pyenv-win, CLI installers" }
            "python\.org" { "Python downloads (pyenv)" }
            "poetry" { "Poetry installer" }
            default { "" }
        }
        if ($note) { $lines += "  - $h  ($note)" } else { $lines += "  - $h" }
    }
    $lines += @(
        ""
        "Ports: 443 (outbound)"
        ""
        "Notes: Developer machine setup script. See setup.log for failure details."
        "If winget is used, additional Microsoft CDN domains may be required."
    )

    $content = $lines -join "`n"
    Set-Content -Path $OutputPath -Value $content -Encoding UTF8
    Write-Success "IT whitelist written to: $OutputPath"
    return $OutputPath
}

function Export-SupportBundle {
    param(
        [object]$Config,
        [string]$ConfigPath,
        [string]$RepoRoot,
        [string]$ProjectDir
    )

    $bundleDir = Join-Path $RepoRoot "support-bundle"
    if (Test-Path $bundleDir) { Remove-Item $bundleDir -Recurse -Force }
    New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null

    $logSrc = Join-Path $RepoRoot "setup.log"
    if (Test-Path $logSrc) {
        Copy-Item $logSrc (Join-Path $bundleDir "setup.log")
    }

    $redactedConfig = $Config | ConvertTo-Json -Depth 10
    $redactedConfig = $redactedConfig -replace '(token|password|pat|secret)[^"]*"(?:[^"\\]|\\.)*"', '$1": "[REDACTED]"'
    Set-Content (Join-Path $bundleDir "setup.config.redacted.json") -Value $redactedConfig -Encoding UTF8

    $summary = @(
        "Support Bundle Summary"
        "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "OS: $([Environment]::OSVersion.VersionString)"
        "User: $env:USERNAME"
        "HTTP_PROXY: $($env:HTTP_PROXY)"
        "HTTPS_PROXY: $($env:HTTPS_PROXY)"
        "NO_PROXY: $($env:NO_PROXY)"
        "SSL_CERT_FILE: $($env:SSL_CERT_FILE)"
    )
    if (Test-CommandExists "python") { $summary += "Python: $(python --version 2>&1)" }
    if (Test-CommandExists "poetry") { $summary += "Poetry: $(poetry --version 2>&1)" }
    if (Test-CommandExists "databricks") { $summary += "Databricks CLI: $(databricks -v 2>&1)" }
    Set-Content (Join-Path $bundleDir "environment-summary.txt") -Value ($summary -join "`n") -Encoding UTF8

    try {
        $artDiag = Test-ArtifactorySetup -Config $Config -ProjectDir $ProjectDir
        $artLines = $artDiag.Results | ForEach-Object { "$($_.Check)`t$($_.Status)`t$($_.Detail)" }
        Set-Content (Join-Path $bundleDir "artifactory-diagnostics.txt") -Value ($artLines -join "`n")
    }
    catch { }

    try {
        if (Get-Command Test-DatabricksSetup -ErrorAction SilentlyContinue) {
            $dbDiag = Test-DatabricksSetup -Config $Config
            $dbLines = $dbDiag.Results | ForEach-Object { "$($_.Check)`t$($_.Status)`t$($_.Detail)" }
            Set-Content (Join-Path $bundleDir "databricks-diagnostics.txt") -Value ($dbLines -join "`n")
        }
    }
    catch { }

    $zipPath = Join-Path $RepoRoot "support-bundle.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path "$bundleDir\*" -DestinationPath $zipPath -Force

    Write-Success "Support bundle: $zipPath"
    return $zipPath
}

function Test-GithubReachability {
    param([string[]]$Hosts = @("github.com"))

    $results = @()
    foreach ($targetHost in ($Hosts | Select-Object -Unique)) {
        $url = "https://$targetHost"
        $probe = Test-EndpointConnectivity -Label $targetHost -Url $url
        $results += $probe
    }
    return $results
}

function Apply-GithubMirrorToPreCommit {
    param(
        [string]$PreCommitPath,
        [string]$GithubMirror
    )

    if (-not (Test-Path $PreCommitPath) -or [string]::IsNullOrWhiteSpace($GithubMirror)) {
        return $false
    }

    $mirror = $GithubMirror.TrimEnd('/')
    $content = Get-Content $PreCommitPath -Raw
    $content = $content -replace 'https://github\.com/', "$mirror/"
    Set-Content -Path $PreCommitPath -Value $content -Encoding UTF8
    Write-Success "Rewrote pre-commit repos to use mirror: $mirror"
    return $true
}