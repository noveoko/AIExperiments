#!/usr/bin/env bash
# WSL/Linux installation helpers

get_setup_config() {
    local config_path="$1"
    if [[ ! -f "$config_path" ]]; then
        fail "Config file not found: $config_path"
        fail "Copy setup.config.json.example to setup.config.json and fill in your organization values."
        return 1
    fi
    printf '%s' "$config_path"
}

read_config_value() {
    local config_path="$1"
    local key_path="$2"
    python3 - "$config_path" "$key_path" <<'PY'
import json, sys
config = json.load(open(sys.argv[1], encoding="utf-8"))
value = config
for part in sys.argv[2].split("."):
    value = value[part]
if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(value)
PY
}

test_preflight_wsl() {
    local config_path="$1"
    if [[ ! -f "$config_path" ]]; then
        fail "Missing setup.config.json. Copy setup.config.json.example and customize it first."
        return 1
    fi
    for cmd in curl python3; do
        if ! command_exists "$cmd"; then
            fail "Required command not found: $cmd"
            return 1
        fi
    done
    if ! curl -fsSL --max-time 10 https://www.microsoft.com >/dev/null 2>&1; then
        warn "Internet connectivity check failed. Some steps may not work offline."
    fi
    return 0
}

install_pyenv() {
    local python_version="$1"
    export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
    if [[ ! -d "$PYENV_ROOT" ]]; then
        info "Installing pyenv..."
        curl -fsSL https://pyenv.run | bash
    fi
    export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
    if ! grep -q 'PYENV_ROOT' "$HOME/.bashrc" 2>/dev/null; then
        {
            echo 'export PYENV_ROOT="$HOME/.pyenv"'
            echo 'export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"'
            echo 'eval "$(pyenv init - bash)"'
        } >> "$HOME/.bashrc"
    fi
    eval "$(pyenv init - bash)"
    if ! pyenv versions --bare | grep -qx "$python_version"; then
        info "Installing Python $python_version (this may take a few minutes)..."
        pyenv install -s "$python_version"
    fi
    pyenv global "$python_version"
    pyenv rehash
    success "Python installed: $(python --version 2>&1)"
}

install_poetry_wsl() {
    if command_exists poetry; then
        success "Poetry already installed: $(poetry --version 2>&1)"
        return 0
    fi
    retry "Install Poetry" bash -c 'curl -sSL https://install.python-poetry.org | python3 -'
    export PATH="$HOME/.local/bin:$PATH"
    if ! command_exists poetry; then
        fail "Poetry not found after installation."
        return 1
    fi
    success "$(poetry --version 2>&1)"
}

install_databricks_cli_wsl() {
    if command_exists databricks; then
        success "Databricks CLI already installed: $(databricks -v 2>&1)"
        return 0
    fi
    retry "Install Databricks CLI" bash -c 'curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh'
    export PATH="/usr/local/bin:$PATH"
    if ! command_exists databricks; then
        fail "Databricks CLI not found after installation."
        return 1
    fi
    success "$(databricks -v 2>&1)"
}

new_poetry_project() {
    local config_path="$1"
    local repo_root="$2"
    local project_name project_dir python_version cluster_runtime source_name artifactory_url
    project_name="$(read_config_value "$config_path" "project.name")"
    project_dir="$(expand_home_path "$(read_config_value "$config_path" "project.directory")")"
    python_version="$(read_config_value "$config_path" "python.version")"
    cluster_runtime="$(read_config_value "$config_path" "databricks.cluster_runtime")"
    source_name="$(read_config_value "$config_path" "artifactory.source_name")"
    artifactory_url="$(read_config_value "$config_path" "artifactory.url")"
    local template_path="$repo_root/templates/pyproject.toml.template"
    local precommit_template="$repo_root/templates/.pre-commit-config.yaml.template"

    mkdir -p "$project_dir"
    info "Project directory: $project_dir"

    local pyproject_path="$project_dir/pyproject.toml"
    if [[ ! -f "$pyproject_path" ]]; then
        sed -e "s|{{PROJECT_NAME}}|$project_name|g" \
            -e "s|{{PYTHON_VERSION}}|$python_version|g" \
            -e "s|{{CLUSTER_RUNTIME}}|$cluster_runtime|g" \
            -e "s|{{ARTIFACTORY_SOURCE_NAME}}|$source_name|g" \
            -e "s|{{ARTIFACTORY_URL}}|$artifactory_url|g" \
            "$template_path" > "$pyproject_path"
        success "Created pyproject.toml"
    else
        info "pyproject.toml already exists, skipping template render."
    fi

    if [[ ! -f "$project_dir/.pre-commit-config.yaml" && -f "$precommit_template" ]]; then
        cp "$precommit_template" "$project_dir/.pre-commit-config.yaml"
        success "Created .pre-commit-config.yaml"
    fi

    (
        cd "$project_dir"
        poetry install
    )
    success "Poetry dependencies installed."
    printf '%s' "$project_dir"
}

install_precommit_hooks() {
    local project_dir="$1"
    local config_path="$2"
    local precommit_path="$project_dir/.pre-commit-config.yaml"
    if [[ ! -f "$precommit_path" ]]; then
        warn "No .pre-commit-config.yaml found. Skipping pre-commit."
        return 1
    fi
    if command -v test_github_reachability >/dev/null 2>&1; then
        local probe
        probe="$(test_github_reachability)"
        if echo "$probe" | grep -q $'\tFAIL\t'; then
            warn "github.com is not reachable. pre-commit hooks clone from GitHub."
            local mirror
            mirror="$(get_corporate_config_value "$config_path" "github_mirror")"
            if [[ -n "$mirror" ]]; then
                apply_github_mirror_to_precommit "$precommit_path" "$mirror"
            elif confirm_or_skip "Skip pre-commit hook install?" true; then
                warn "pre-commit hooks skipped."
                return 0
            fi
        fi
    fi
    (
        cd "$project_dir"
        poetry run pre-commit install
    )
    success "pre-commit hooks installed."
}

get_verification_results_wsl() {
    local config_path="$1"
    local project_dir="$2"
    local python_version
    python_version="$(read_config_value "$config_path" "python.version")"

    if command_exists python; then
        local py_ver
        py_ver="$(python --version 2>&1)"
        if [[ "$py_ver" == *"$python_version"* ]]; then
            printf '%s\t%s\t%s\n' "Python" "OK" "$py_ver"
        else
            printf '%s\t%s\t%s\n' "Python" "WARN" "$py_ver"
        fi
    else
        printf '%s\t%s\t%s\n' "Python" "FAIL" "not found"
    fi

    if command_exists poetry; then
        printf '%s\t%s\t%s\n' "Poetry" "OK" "$(poetry --version 2>&1)"
    else
        printf '%s\t%s\t%s\n' "Poetry" "FAIL" "not found"
    fi

    if command_exists bash; then
        printf '%s\t%s\t%s\n' "Bash" "OK" "available"
    else
        printf '%s\t%s\t%s\n' "Bash" "FAIL" "not found"
    fi

    if command_exists databricks; then
        printf '%s\t%s\t%s\n' "Databricks CLI" "OK" "$(databricks -v 2>&1)"
    else
        printf '%s\t%s\t%s\n' "Databricks CLI" "FAIL" "not found"
    fi

    local source_name
    source_name="$(read_config_value "$config_path" "artifactory.source_name")"
    if poetry config --list 2>/dev/null | grep -q "http-basic.$source_name"; then
        printf '%s\t%s\t%s\n' "Artifactory (Poetry)" "OK" "configured"
    else
        printf '%s\t%s\t%s\n' "Artifactory (Poetry)" "WARN" "not configured"
    fi

    if [[ -f "$HOME/.databrickscfg" ]]; then
        printf '%s\t%s\t%s\n' "Databricks Auth" "OK" "profile file exists"
    else
        printf '%s\t%s\t%s\n' "Databricks Auth" "WARN" "not configured"
    fi

    if [[ -n "$project_dir" && -d "$project_dir" ]]; then
        (
            cd "$project_dir"
            if poetry run python -c "import databricks.connect" >/dev/null 2>&1; then
                printf '%s\t%s\t%s\n' "databricks-connect" "OK" "importable"
            else
                printf '%s\t%s\t%s\n' "databricks-connect" "FAIL" "not importable"
            fi
            for tool in pytest ruff black; do
                printf '%s\t%s\t%s\n' "$tool" "OK" "$(poetry run "$tool" --version 2>&1 | head -n1)"
            done
            if [[ -f .git/hooks/pre-commit ]]; then
                printf '%s\t%s\t%s\n' "pre-commit" "OK" "hooks installed"
            else
                printf '%s\t%s\t%s\n' "pre-commit" "WARN" "hooks not installed"
            fi
        )
    fi
}