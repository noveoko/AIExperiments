#!/usr/bin/env bash
# Prerequisites wizard and corporate preflight checks

show_token_help() {
    echo ""
    echo "  Token how-to:"
    echo "    Artifactory : JFrog > User Profile > Identity Token > Generate"
    echo "    Databricks  : Workspace > User Settings > Developer > Access Tokens"
    echo "    Or use OAuth at step 9 if your org allows browser login"
    echo ""
}

invoke_prerequisites_wizard() {
    echo ""
    echo "  Before we install anything, confirm you have:"
    echo ""
    echo "    [ ] Connected to corporate VPN (if required)"
    echo "    [ ] Artifactory identity token (or will paste snippet at step 8)"
    echo "    [ ] Databricks workspace access approved by IT"
    echo "    [ ] Databricks PAT ready (only if OAuth is blocked)"
    echo "    [ ] Admin rights OR pre-approved software via Software Center"
    echo ""
    local response
    read -r -p "  Press Enter when ready, or type 'help' for token links: " response
    if [[ "$response" == "help" ]]; then
        show_token_help
        read -r -p "  Press Enter when ready to continue: "
    fi
}

invoke_prerequisites_checks() {
    local config_path="$1"
    invoke_prerequisites_wizard
    if command_exists winget 2>/dev/null; then
        info "winget check: skipped on WSL/bash"
    fi
    if command -v test_endpoint_connectivity >/dev/null 2>&1; then
        local art_url db_url
        art_url="$(read_config_value "$config_path" "artifactory.url")"
        db_url="$(read_config_value "$config_path" "databricks.host")"
        [[ -n "$art_url" ]] && test_endpoint_connectivity "Artifactory (preflight)" "$art_url" || true
        [[ -n "$db_url" ]] && test_endpoint_connectivity "Databricks (preflight)" "$db_url" || true
    fi
    return 0
}