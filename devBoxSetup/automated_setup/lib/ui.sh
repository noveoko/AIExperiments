#!/usr/bin/env bash
# Shared UI helpers for setup.sh

SETUP_LOG_PATH=""
DRY_RUN=false
TOTAL_STEPS=16

init_setup_ui() {
    SETUP_LOG_PATH="${1:-$(dirname "${BASH_SOURCE[0]}")/../setup.log}"
    DRY_RUN="${2:-false}"
}

write_setup_log() {
    local message="$1"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo "[$timestamp] $message" >> "$SETUP_LOG_PATH"
}

step() {
    local number="$1"
    local title="$2"
    local description="${3:-}"
    echo ""
    printf '==============================================\n'
    printf '  Step %s of %s: %s\n' "$number" "$TOTAL_STEPS" "$title"
    printf '==============================================\n'
    echo ""
    if [[ -n "$description" ]]; then
        echo "  $description"
        echo ""
    fi
    write_setup_log "STEP $number: $title"
}

info() {
    echo "  $1"
}

success() {
    echo "  [OK] $1"
    write_setup_log "OK: $1"
}

warn() {
    echo "  [WARN] $1"
    write_setup_log "WARN: $1"
}

fail() {
    echo "  [FAIL] $1"
    write_setup_log "FAIL: $1"
}

confirm_or_skip() {
    local prompt="${1:-Continue?}"
    local default_yes="${2:-false}"
    local suffix="[y/N/skip]"
    if [[ "$default_yes" == "true" ]]; then
        suffix="[Y/n/skip]"
    fi
    local response
    read -r -p "  $prompt $suffix " response
    response="${response,,}"
    if [[ -z "$response" ]]; then
        [[ "$default_yes" == "true" ]] && return 0 || return 1
    fi
    case "$response" in
        y|yes) return 0 ;;
        skip) return 2 ;;
        *) return 1 ;;
    esac
}

read_secret() {
    local prompt="$1"
    local secret
    read -r -s -p "  $prompt " secret
    echo ""
    printf '%s' "$secret"
}

retry() {
    local description="$1"
    shift
    local max_attempts=3
    local attempt
    for ((attempt = 1; attempt <= max_attempts; attempt++)); do
        if [[ "$DRY_RUN" == "true" ]]; then
            info "[dry-run] Would run: $description"
            return 0
        fi
        if "$@"; then
            return 0
        fi
        fail "$description failed (attempt $attempt/$max_attempts)"
        if [[ $attempt -lt $max_attempts ]]; then
            if confirm_or_skip "Retry?" true; then
                continue
            fi
            return 1
        fi
    done
    return 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

expand_home_path() {
    local path="$1"
    if [[ "$path" == ~* ]]; then
        echo "${path/#\~/$HOME}"
    else
        echo "$path"
    fi
}

write_summary_table() {
    echo ""
    echo "Verification Summary"
    printf '%s\n' "------------------------------------------------------------"
    printf '%-22s %-7s %s\n' "Component" "Status" "Detail"
    printf '%s\n' "------------------------------------------------------------"
    while IFS=$'\t' read -r component status detail; do
        printf '%-22s %-7s %s\n' "$component" "$status" "$detail"
    done
    printf '%s\n' "------------------------------------------------------------"
}