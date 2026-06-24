#!/usr/bin/env bash
# Interactive development machine setup for WSL / Linux / Git Bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="$REPO_ROOT/setup.config.json"
LOG_PATH="$REPO_ROOT/setup.log"
FROM_WINDOWS=false
DRY_RUN=false
VERIFY_ONLY=false
ARTIFACTORY_TROUBLESHOOT=false
ARTIFACTORY_SETUP=false
ARTIFACTORY_SNIPPET=""
ARTIFACTORY_VERBOSE=false
CORPORATE_PREFLIGHT=false
DATABRICKS_TROUBLESHOOT=false
DATABRICKS_SETUP=false
GENERATE_IT_WHITELIST=false
GENERATE_SUPPORT_BUNDLE=false
START_STEP=1

usage() {
    cat <<'EOF'
Usage: ./setup.sh [options]

Options:
  --from-windows              Invoked by setup.ps1 from Windows
  --dry-run                   Print actions without executing
  --verify-only               Run verification checks only
  --corporate-preflight       Run prerequisites + proxy/SSL checks only
  --artifactory-troubleshoot  Run Artifactory diagnostics only
  --artifactory-setup         Interactive Artifactory setup menu
  --artifactory-snippet TEXT  Apply pasted Artifactory snippet
  --databricks-troubleshoot   Run Databricks diagnostics only
  --databricks-setup          Interactive Databricks setup menu
  --generate-it-whitelist     Export IT firewall whitelist request
  --generate-support-bundle   Export redacted support bundle for helpdesk
  --verbose                   Extra diagnostic output
  --step N                    Resume from step N (1-16)
  -h, --help                  Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --from-windows) FROM_WINDOWS=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --verify-only) VERIFY_ONLY=true; shift ;;
        --corporate-preflight) CORPORATE_PREFLIGHT=true; shift ;;
        --artifactory-troubleshoot) ARTIFACTORY_TROUBLESHOOT=true; shift ;;
        --artifactory-setup) ARTIFACTORY_SETUP=true; shift ;;
        --artifactory-snippet) ARTIFACTORY_SNIPPET="${2:-}"; shift 2 ;;
        --databricks-troubleshoot) DATABRICKS_TROUBLESHOOT=true; shift ;;
        --databricks-setup) DATABRICKS_SETUP=true; shift ;;
        --generate-it-whitelist) GENERATE_IT_WHITELIST=true; shift ;;
        --generate-support-bundle) GENERATE_SUPPORT_BUNDLE=true; shift ;;
        --verbose) ARTIFACTORY_VERBOSE=true; shift ;;
        --step) START_STEP="${2:-1}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# shellcheck source=lib/ui.sh
source "$REPO_ROOT/lib/ui.sh"
# shellcheck source=lib/install.sh
source "$REPO_ROOT/lib/install.sh"
# shellcheck source=lib/artifactory.sh
source "$REPO_ROOT/lib/artifactory.sh"
# shellcheck source=lib/corporate.sh
source "$REPO_ROOT/lib/corporate.sh"
# shellcheck source=lib/prerequisites.sh
source "$REPO_ROOT/lib/prerequisites.sh"
# shellcheck source=lib/databricks.sh
source "$REPO_ROOT/lib/databricks.sh"

init_setup_ui "$LOG_PATH" "$DRY_RUN"

echo ""
echo "  Development Machine Setup"
echo "  WSL / Linux / Git Bash"
echo ""

run_step() {
    local number="$1"
    local title="$2"
    local description="$3"
    shift 3
    if (( number < START_STEP )); then
        return 0
    fi
    step "$number" "$title" "$description"
    if [[ "$FROM_WINDOWS" != "true" ]]; then
        if ! confirm_or_skip "Proceed with this step?" true; then
            warn "Skipped step $number."
            return 0
        fi
    fi
    "$@"
}

if [[ "$VERIFY_ONLY" == "true" ]]; then
    [[ ! -f "$CONFIG_PATH" ]] && { fail "setup.config.json not found."; exit 1; }
    project_dir="$(expand_home_path "$(read_config_value "$CONFIG_PATH" "project.directory")")"
    get_verification_results_wsl "$CONFIG_PATH" "$project_dir" | write_summary_table
    exit 0
fi

if [[ "$GENERATE_IT_WHITELIST" == "true" ]]; then
    [[ ! -f "$CONFIG_PATH" ]] && { fail "setup.config.json not found."; exit 1; }
    export_it_whitelist "$CONFIG_PATH" "$REPO_ROOT/it-whitelist-request.txt"
    exit 0
fi

if [[ "$GENERATE_SUPPORT_BUNDLE" == "true" ]]; then
    [[ ! -f "$CONFIG_PATH" ]] && { fail "setup.config.json not found."; exit 1; }
    project_dir="$(expand_home_path "$(read_config_value "$CONFIG_PATH" "project.directory")")"
    export_support_bundle "$CONFIG_PATH" "$REPO_ROOT" "$project_dir"
    exit 0
fi

if [[ "$CORPORATE_PREFLIGHT" == "true" ]]; then
    [[ ! -f "$CONFIG_PATH" ]] && { fail "setup.config.json not found."; exit 1; }
    invoke_prerequisites_checks "$CONFIG_PATH"
    invoke_corporate_network_setup "$CONFIG_PATH"
    exit 0
fi

if [[ "$ARTIFACTORY_TROUBLESHOOT" == "true" || "$ARTIFACTORY_SETUP" == "true" || -n "$ARTIFACTORY_SNIPPET" ]]; then
    [[ ! -f "$CONFIG_PATH" ]] && { fail "setup.config.json not found."; exit 1; }
    project_dir="$(expand_home_path "$(read_config_value "$CONFIG_PATH" "project.directory")")"
    mode="menu"
    [[ "$ARTIFACTORY_TROUBLESHOOT" == "true" ]] && mode="troubleshoot"
    [[ -n "$ARTIFACTORY_SNIPPET" ]] && mode="paste"
    verbose_flag="false"
    [[ "$ARTIFACTORY_VERBOSE" == "true" ]] && verbose_flag="true"
    invoke_artifactory_setup "$CONFIG_PATH" "$project_dir" "$ARTIFACTORY_SNIPPET" "$mode" "$verbose_flag"
    exit $?
fi

if [[ "$DATABRICKS_TROUBLESHOOT" == "true" || "$DATABRICKS_SETUP" == "true" ]]; then
    [[ ! -f "$CONFIG_PATH" ]] && { fail "setup.config.json not found."; exit 1; }
    mode="menu"
    [[ "$DATABRICKS_TROUBLESHOOT" == "true" ]] && mode="troubleshoot"
    invoke_databricks_setup "$CONFIG_PATH" "$mode"
    exit $?
fi

touch "$LOG_PATH"
PROJECT_DIR=""

main() {
    run_step 1 "Prerequisites" "Confirm VPN, tokens, and permissions before we install anything." \
        _step_prerequisites

    run_step 2 "Network, Proxy and SSL" "Configure corporate proxy and CA certificates." \
        invoke_corporate_network_setup "$CONFIG_PATH"

    local python_version
    python_version="$(read_config_value "$CONFIG_PATH" "python.version")"

    run_step 3 "Bash Shell" "Bash is the command shell used for development scripts." \
        success "Bash available: $(bash --version | head -n1)"

    run_step 4 "Python $python_version" "Python is the programming language used for Databricks development." \
        install_pyenv "$python_version"

    run_step 5 "Poetry" "Poetry manages Python packages and virtual environments for your project." \
        install_poetry_wsl

    run_step 6 "Visual Studio Code" "On WSL, use VS Code on Windows with the Remote - WSL extension." \
        info "Skipped on WSL — use Windows VS Code with Remote - WSL."

    run_step 7 "Databricks CLI" "The Databricks CLI lets you manage workspaces, clusters, and deployments from your terminal." \
        install_databricks_cli_wsl

    run_step 8 "Artifactory Credentials" "Artifactory is your organization's private package registry." \
        _step_artifactory

    run_step 9 "Databricks Authentication" "Connect your computer to your Databricks workspace." \
        _step_databricks

    run_step 10 "Poetry Project" "We create a starter project with all required Python dependencies." \
        _step_poetry_project

    run_step 11 "VS Code Extensions" "Install VS Code extensions from Windows." \
        info "Skipped on WSL — run setup.ps1 on Windows for extension installation."

    run_step 12 "pre-commit Hooks" "pre-commit runs code quality checks automatically before each commit." \
        _step_precommit

    run_step 13 "databricks-connect Validation" "Verify your machine can reach the configured Databricks cluster." \
        _step_databricks_connect

    run_step 14 "WSL Setup" "You are already running inside WSL/Linux." \
        info "WSL setup complete (running in Linux environment)."

    run_step 15 "Verification" "Final check that everything is installed and configured correctly." \
        _step_verify

    run_step 16 "IT Export (optional)" "Generate files to share with IT or helpdesk." \
        _step_it_export
}

_step_prerequisites() {
    test_preflight_wsl "$CONFIG_PATH"
    invoke_prerequisites_checks "$CONFIG_PATH"
    success "Prerequisites complete."
}

_step_artifactory() {
    local dir="${PROJECT_DIR:-}"
    if [[ -z "$dir" ]]; then
        dir="$(expand_home_path "$(read_config_value "$CONFIG_PATH" "project.directory")")"
    fi
    local verbose_flag="false"
    [[ "$ARTIFACTORY_VERBOSE" == "true" ]] && verbose_flag="true"
    invoke_artifactory_setup "$CONFIG_PATH" "$dir" "" "menu" "$verbose_flag"
}

_step_databricks() {
    local method
    method="$(read_config_value "$CONFIG_PATH" "databricks.auth_method")"
    if [[ "$method" == "pat" ]]; then
        invoke_databricks_setup "$CONFIG_PATH" "pat"
    else
        invoke_databricks_setup "$CONFIG_PATH" "menu"
    fi
}

_step_poetry_project() {
    PROJECT_DIR="$(new_poetry_project "$CONFIG_PATH" "$REPO_ROOT")"
}

_step_precommit() {
    if [[ -n "$PROJECT_DIR" ]]; then
        install_precommit_hooks "$PROJECT_DIR" "$CONFIG_PATH"
    fi
}

_step_databricks_connect() {
    if [[ -n "$PROJECT_DIR" ]]; then
        test_databricks_connect_cluster "$CONFIG_PATH" "$PROJECT_DIR"
    fi
}

_step_it_export() {
    if [[ "$FROM_WINDOWS" != "true" ]]; then
        if confirm_or_skip "Export IT whitelist request file?" true; then
            export_it_whitelist "$CONFIG_PATH" "$REPO_ROOT/it-whitelist-request.txt"
        fi
        if confirm_or_skip "Export support bundle for helpdesk?" true; then
            export_support_bundle "$CONFIG_PATH" "$REPO_ROOT" "${PROJECT_DIR:-}"
        fi
    fi
}

_step_verify() {
    if [[ -z "$PROJECT_DIR" ]]; then
        PROJECT_DIR="$(expand_home_path "$(read_config_value "$CONFIG_PATH" "project.directory")")"
    fi
    local results
    results="$(get_verification_results_wsl "$CONFIG_PATH" "$PROJECT_DIR")"
    echo "$results" | write_summary_table
    if echo "$results" | grep -q $'\tFAIL\t'; then
        echo ""
        warn "Some components need attention. Re-run with --step N to retry."
        info "Log file: $LOG_PATH"
        exit 1
    fi
    echo ""
    success "Setup complete! Your project is at: $PROJECT_DIR"
    info "Activate the environment: cd \"$PROJECT_DIR\" && poetry shell"
}

if ! main; then
    fail "Setup failed."
    info "Log file: $LOG_PATH"
    info "Resume with: ./setup.sh --step <step-number>"
    exit 1
fi