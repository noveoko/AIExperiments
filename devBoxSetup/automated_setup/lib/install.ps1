# Windows installation helpers

function Get-SetupConfig {
    param([string]$ConfigPath)
    if (-not (Test-Path $ConfigPath)) {
        throw "Config file not found: $ConfigPath`nCopy setup.config.json.example to setup.config.json and fill in your organization values."
    }
    return Get-Content $ConfigPath -Raw | ConvertFrom-Json
}

function Test-PreflightWindows {
    param([string]$ConfigPath)
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        throw "PowerShell 5.1 or later is required."
    }
    if (-not (Test-Path $ConfigPath)) {
        throw "Missing setup.config.json. Copy setup.config.json.example and customize it first."
    }
    try {
        $null = Invoke-WebRequest -Uri "https://www.microsoft.com" -UseBasicParsing -TimeoutSec 10
    }
    catch {
        Write-Warn "Internet connectivity check failed. Some steps may not work offline."
    }
    return $true
}

function Install-GitBash {
    if (Test-CommandExists "bash") {
        Write-Success "Bash already available ($(bash --version 2>&1 | Select-Object -First 1))"
        return $true
    }
    if (-not (Test-CommandExists "winget")) {
        Write-Fail "winget not found. Install Git for Windows manually: https://git-scm.com/download/win"
        return $false
    }
    return Invoke-WithRetry -Description "Install Git for Windows" -Action {
        winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
    }
}

function Install-PyenvWin {
    param([string]$PythonVersion)
    $pyenvRoot = Join-Path $env:USERPROFILE ".pyenv"
    $pyenvWin = Join-Path $pyenvRoot "pyenv-win"

    if (-not (Test-Path $pyenvWin)) {
        Write-Info "Installing pyenv-win..."
        if (-not (Test-Path $pyenvRoot)) {
            New-Item -ItemType Directory -Path $pyenvRoot -Force | Out-Null
        }
        git clone https://github.com/pyenv-win/pyenv-win.git $pyenvWin 2>$null
        if (-not (Test-Path $pyenvWin)) {
            throw "Failed to clone pyenv-win."
        }
    }

    $pathsToAdd = @(
        (Join-Path $pyenvWin "bin"),
        (Join-Path $pyenvWin "shims")
    )
    foreach ($p in $pathsToAdd) {
        if ($env:Path -notlike "*$p*") {
            $env:Path = "$p;$env:Path"
        }
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*$p*") {
            [Environment]::SetEnvironmentVariable("Path", "$userPath;$p", "User")
        }
    }

    $pyenvCmd = Join-Path $pyenvWin "bin\pyenv.bat"
    if (-not (Test-Path $pyenvCmd)) {
        throw "pyenv-win installation incomplete."
    }

    $installed = & $pyenvCmd versions --bare 2>$null
    if ($installed -notcontains $PythonVersion) {
        Write-Info "Installing Python $PythonVersion (this may take a few minutes)..."
        & $pyenvCmd install $PythonVersion
    }
    & $pyenvCmd global $PythonVersion
    & $pyenvCmd rehash

    $pythonExe = Join-Path $pyenvWin "shims\python.exe"
    if (Test-Path $pythonExe) {
        $version = & $pythonExe --version 2>&1
        Write-Success "Python installed: $version"
        return $true
    }
    throw "Python $PythonVersion not available after pyenv-win install."
}

function Install-PoetryWindows {
    if (Test-CommandExists "poetry") {
        $ver = poetry --version 2>&1
        Write-Success "Poetry already installed: $ver"
        return $true
    }
    return Invoke-WithRetry -Description "Install Poetry" -Action {
        $installer = (Invoke-WebRequest -Uri "https://install.python-poetry.org" -UseBasicParsing).Content
        & python -c $installer
        $poetryPath = Join-Path $env:APPDATA "Python\Scripts"
        if ($env:Path -notlike "*$poetryPath*") {
            $env:Path = "$poetryPath;$env:Path"
            $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
            [Environment]::SetEnvironmentVariable("Path", "$userPath;$poetryPath", "User")
        }
        if (-not (Test-CommandExists "poetry")) {
            throw "Poetry not found after installation."
        }
        Write-Success (poetry --version)
    }
}

function Install-VSCodeWindows {
    if (Test-CommandExists "code") {
        Write-Success "VS Code CLI already available."
        return $true
    }
    if (-not (Test-CommandExists "winget")) {
        Write-Warn "winget not found. Install VS Code manually: https://code.visualstudio.com/"
        return $false
    }
    $result = Invoke-WithRetry -Description "Install VS Code" -Action {
        winget install --id Microsoft.VisualStudioCode -e --accept-source-agreements --accept-package-agreements
        $vscodePath = Join-Path ${env:ProgramFiles} "Microsoft VS Code\bin"
        if (Test-Path $vscodePath) {
            $env:Path = "$vscodePath;$env:Path"
        }
    }
    if (Test-CommandExists "code") {
        Write-Success "VS Code installed."
        return $true
    }
    Write-Warn "VS Code installed but 'code' CLI not in PATH. Restart your terminal."
    return $result
}

function Install-DatabricksCliWindows {
    if (Test-CommandExists "databricks") {
        $ver = databricks -v 2>&1
        Write-Success "Databricks CLI already installed: $ver"
        return $true
    }
    if (-not (Test-CommandExists "winget")) {
        Write-Fail "winget not found. Install Databricks CLI manually."
        return $false
    }
    return Invoke-WithRetry -Description "Install Databricks CLI" -Action {
        winget install --id Databricks.DatabricksCLI -e --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")
        if (-not (Test-CommandExists "databricks")) {
            throw "Databricks CLI not found after installation."
        }
        Write-Success (databricks -v 2>&1)
    }
}

function New-PoetryProject {
    param(
        [object]$Config,
        [string]$RepoRoot
    )
    $projectDir = Expand-HomePath $Config.project.directory
    $templatePath = Join-Path $RepoRoot "templates\pyproject.toml.template"
    $preCommitTemplate = Join-Path $RepoRoot "templates\.pre-commit-config.yaml.template"

    if (-not (Test-Path $projectDir)) {
        New-Item -ItemType Directory -Path $projectDir -Force | Out-Null
        Write-Info "Created project directory: $projectDir"
    }

    $pyprojectPath = Join-Path $projectDir "pyproject.toml"
    if (-not (Test-Path $pyprojectPath)) {
        $template = Get-Content $templatePath -Raw
        $content = $template `
            -replace '\{\{PROJECT_NAME\}\}', $Config.project.name `
            -replace '\{\{PYTHON_VERSION\}\}', $Config.python.version `
            -replace '\{\{CLUSTER_RUNTIME\}\}', $Config.databricks.cluster_runtime `
            -replace '\{\{ARTIFACTORY_SOURCE_NAME\}\}', $Config.artifactory.source_name `
            -replace '\{\{ARTIFACTORY_URL\}\}', $Config.artifactory.url
        Set-Content -Path $pyprojectPath -Value $content -Encoding UTF8
        Write-Success "Created pyproject.toml"
    }
    else {
        Write-Info "pyproject.toml already exists, skipping template render."
    }

    $preCommitPath = Join-Path $projectDir ".pre-commit-config.yaml"
    if (-not (Test-Path $preCommitPath) -and (Test-Path $preCommitTemplate)) {
        Copy-Item $preCommitTemplate $preCommitPath
        Write-Success "Created .pre-commit-config.yaml"
    }

    Push-Location $projectDir
    try {
        poetry install
        Write-Success "Poetry dependencies installed."
    }
    finally {
        Pop-Location
    }
    return $projectDir
}

function Install-VSCodeExtensions {
    param([string[]]$Extensions)
    if (-not (Test-CommandExists "code")) {
        Write-Warn "VS Code CLI not available. Install extensions manually from the marketplace."
        return $false
    }
    foreach ($ext in $Extensions) {
        Write-Info "Installing extension: $ext"
        code --install-extension $ext --force 2>&1 | Out-Null
    }
    Write-Success "VS Code extensions installed."
    return $true
}

function Install-PreCommitHooks {
    param(
        [string]$ProjectDir,
        [object]$Config
    )

    $preCommitPath = Join-Path $ProjectDir ".pre-commit-config.yaml"
    if (-not (Test-Path $preCommitPath)) {
        Write-Warn "No .pre-commit-config.yaml found. Skipping pre-commit."
        return $false
    }

    $githubProbe = $null
    if (Get-Command Test-GithubReachability -ErrorAction SilentlyContinue) {
        $githubProbe = Test-GithubReachability -Hosts @("github.com")
        $ghFail = $githubProbe | Where-Object { $_.Status -eq "FAIL" }
        if ($ghFail.Count -gt 0) {
            Write-Warn "github.com is not reachable. pre-commit hooks clone from GitHub."
            $corp = $null
            if ($Config.PSObject.Properties.Name -contains "corporate") { $corp = $Config.corporate }
            if ($corp -and $corp.github_mirror) {
                Apply-GithubMirrorToPreCommit -PreCommitPath $preCommitPath -GithubMirror $corp.github_mirror
            }
            else {
                $skip = Confirm-OrSkip -Prompt "Skip pre-commit hook install?" -DefaultYes
                if ($skip) {
                    Write-Warn "pre-commit hooks skipped."
                    return $false
                }
            }
        }
    }

    Push-Location $ProjectDir
    try {
        poetry run pre-commit install
        Write-Success "pre-commit hooks installed."
        return $true
    }
    finally {
        Pop-Location
    }
}

function Get-VerificationResultsWindows {
    param(
        [object]$Config,
        [string]$ProjectDir
    )
    $results = @()

    if (Test-CommandExists "python") {
        $pyVer = python --version 2>&1
        $status = if ($pyVer -match [regex]::Escape($Config.python.version)) { "OK" } else { "WARN" }
        $results += [pscustomobject]@{ Component = "Python"; Status = $status; Detail = $pyVer }
    }
    else {
        $results += [pscustomobject]@{ Component = "Python"; Status = "FAIL"; Detail = "not found" }
    }

    if (Test-CommandExists "poetry") {
        $results += [pscustomobject]@{ Component = "Poetry"; Status = "OK"; Detail = (poetry --version 2>&1) }
    }
    else {
        $results += [pscustomobject]@{ Component = "Poetry"; Status = "FAIL"; Detail = "not found" }
    }

    if (Test-CommandExists "code") {
        $results += [pscustomobject]@{ Component = "VS Code"; Status = "OK"; Detail = "CLI available" }
    }
    else {
        $results += [pscustomobject]@{ Component = "VS Code"; Status = "WARN"; Detail = "CLI not in PATH" }
    }

    if (Test-CommandExists "bash") {
        $results += [pscustomobject]@{ Component = "Bash"; Status = "OK"; Detail = "available" }
    }
    else {
        $results += [pscustomobject]@{ Component = "Bash"; Status = "FAIL"; Detail = "not found" }
    }

    if (Test-CommandExists "databricks") {
        $results += [pscustomobject]@{ Component = "Databricks CLI"; Status = "OK"; Detail = (databricks -v 2>&1) }
    }
    else {
        $results += [pscustomobject]@{ Component = "Databricks CLI"; Status = "FAIL"; Detail = "not found" }
    }

    $sourceName = $Config.artifactory.source_name
    if (Test-CommandExists "poetry") {
        $poetryConfig = poetry config --list 2>&1 | Out-String
        if ($poetryConfig -match "http-basic\.$([regex]::Escape($sourceName))") {
            $results += [pscustomobject]@{ Component = "Artifactory (Poetry)"; Status = "OK"; Detail = "configured" }
        }
        else {
            $results += [pscustomobject]@{ Component = "Artifactory (Poetry)"; Status = "WARN"; Detail = "not configured" }
        }
    }
    else {
        $results += [pscustomobject]@{ Component = "Artifactory (Poetry)"; Status = "FAIL"; Detail = "poetry not found" }
    }

    $databricksCfg = Join-Path $env:USERPROFILE ".databrickscfg"
    if (Test-Path $databricksCfg) {
        $results += [pscustomobject]@{ Component = "Databricks Auth"; Status = "OK"; Detail = "profile file exists" }
    }
    else {
        $results += [pscustomobject]@{ Component = "Databricks Auth"; Status = "WARN"; Detail = "not configured" }
    }

    if ($ProjectDir -and (Test-Path $ProjectDir) -and (Test-CommandExists "poetry")) {
        Push-Location $ProjectDir
        try {
            $dcVer = poetry run python -c "import databricks.connect; print('ok')" 2>&1
            if ($LASTEXITCODE -eq 0) {
                $results += [pscustomobject]@{ Component = "databricks-connect"; Status = "OK"; Detail = "importable" }
            }
            else {
                $results += [pscustomobject]@{ Component = "databricks-connect"; Status = "FAIL"; Detail = "not importable" }
            }
            foreach ($tool in @("pytest", "ruff", "black")) {
                try {
                    $out = poetry run $tool --version 2>&1
                    $results += [pscustomobject]@{ Component = $tool; Status = "OK"; Detail = ($out | Select-Object -First 1) }
                }
                catch {
                    $results += [pscustomobject]@{ Component = $tool; Status = "FAIL"; Detail = "not found" }
                }
            }
            if (Test-Path ".git\hooks\pre-commit") {
                $results += [pscustomobject]@{ Component = "pre-commit"; Status = "OK"; Detail = "hooks installed" }
            }
            else {
                $results += [pscustomobject]@{ Component = "pre-commit"; Status = "WARN"; Detail = "hooks not installed" }
            }
        }
        finally {
            Pop-Location
        }
    }
    elseif ($ProjectDir -and -not (Test-Path $ProjectDir)) {
        $results += [pscustomobject]@{ Component = "Poetry project"; Status = "WARN"; Detail = "directory not created yet" }
    }

    if (Test-CommandExists "code") {
        $extList = code --list-extensions 2>&1 | Out-String
        $ext = $Config.vscode.extensions[0]
        if ($extList -match [regex]::Escape($ext)) {
            $results += [pscustomobject]@{ Component = "VS Code Databricks ext"; Status = "OK"; Detail = $ext }
        }
        else {
            $results += [pscustomobject]@{ Component = "VS Code Databricks ext"; Status = "WARN"; Detail = "not installed" }
        }
    }

    return $results
}

function Invoke-WslSetup {
    param(
        [string]$RepoRoot,
        [string]$Distro
    )
    if (-not (Test-CommandExists "wsl")) {
        Write-Warn "WSL not installed. Skipping WSL setup."
        return $false
    }
    $driveLetter = $RepoRoot.Substring(0, 1).ToLower()
    $wslPath = $RepoRoot.Substring(2) -replace '\\', '/'
    $wslPath = "/mnt/$driveLetter$wslPath"
    Write-Info "Launching WSL setup in distro '$Distro'..."
    wsl -d $Distro bash "$wslPath/setup.sh" --from-windows
    return $LASTEXITCODE -eq 0
}