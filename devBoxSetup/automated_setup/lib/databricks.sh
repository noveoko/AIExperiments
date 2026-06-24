#!/usr/bin/env bash
# Databricks auth setup and diagnostics

test_databricks_setup() {
    local config_path="$1"
    local profile host
    profile="$(read_config_value "$config_path" "databricks.profile")"
    host="$(read_config_value "$config_path" "databricks.host")"
    local -a results=() fixes=()

    add_diag() { results+=("$1	$2	$3"); [[ -n "${4:-}" ]] && fixes+=("$4"); }

    if command_exists databricks; then
        add_diag "CLI installed" "OK" "$(databricks -v 2>&1)" ""
    else
        add_diag "CLI installed" "FAIL" "not found" "Re-run step 7"
        printf '%s\n' "${results[@]}"
        printf '---FIXES---\n'
        printf '%s\n' "${fixes[@]}"
        return 0
    fi

    if [[ -f "$HOME/.databrickscfg" ]] && grep -q "\[$profile\]" "$HOME/.databrickscfg"; then
        add_diag "Profile configured" "OK" "$profile" ""
    else
        add_diag "Profile configured" "FAIL" "profile missing" "Run --databricks-setup"
    fi

    if [[ -n "$host" ]] && command -v test_endpoint_connectivity >/dev/null 2>&1; then
        local probe
        probe="$(test_endpoint_connectivity "Workspace" "$host")"
        IFS=$'\t' read -r _ pstatus pdetail _ <<< "$probe"
        add_diag "Host reachable" "$pstatus" "$pdetail" ""
    fi

    if [[ -f "$HOME/.databrickscfg" ]]; then
        if databricks current-user me --profile "$profile" >/dev/null 2>&1; then
            add_diag "Auth valid" "OK" "current-user me succeeded" ""
        else
            add_diag "Auth valid" "FAIL" "auth check failed" "Try PAT if OAuth blocked"
        fi
    fi

    printf '%s\n' "${results[@]}"
    printf '---FIXES---\n'
    printf '%s\n' "${fixes[@]}"
}

write_databricks_diagnostic_report() {
    local output="$1"
    echo ""
    echo "Databricks Diagnostics"
    printf '%s\n' "------------------------------------------------------------"
    while IFS=$'\t' read -r check status detail; do
        [[ "$check" == "---FIXES---" ]] && break
        [[ -z "$check" ]] && continue
        printf '%-24s %-7s %s\n' "$check" "$status" "$detail"
    done <<< "$output"
    printf '%s\n' "------------------------------------------------------------"
}

invoke_databricks_setup() {
    local config_path="$1" mode="${2:-menu}"
    local host profile method

    if [[ "$mode" == "menu" ]]; then
        echo ""
        echo "  How do you want to configure Databricks?"
        echo ""
        echo "    [1] Guided OAuth"
        echo "    [2] PAT / token (recommended in corporates)"
        echo "    [3] Manual entry"
        echo "    [4] Troubleshoot only"
        echo ""
        local choice
        read -r -p "  Choose [1-4]: " choice
        case "$choice" in
            2) mode="pat" ;;
            3) mode="manual" ;;
            4) mode="troubleshoot" ;;
            *) mode="guided" ;;
        esac
    fi

    if [[ "$mode" == "troubleshoot" ]]; then
        write_databricks_diagnostic_report "$(test_databricks_setup "$config_path")"
        ! test_databricks_setup "$config_path" | grep -q $'\tFAIL\t'
        return $?
    fi

    host="$(read_config_value "$config_path" "databricks.host")"
    profile="$(read_config_value "$config_path" "databricks.profile")"
    [[ -z "$host" ]] && { warn "Databricks host not configured."; return 1; }

    case "$mode" in
        guided)
            info "Opening browser for OAuth..."
            databricks auth login --host "$host" --profile "$profile"
            success "Databricks OAuth login completed."
            ;;
        pat)
            local pat
            pat="$(read_secret "Enter Databricks Personal Access Token:")"
            databricks configure --host "$host" --token "$pat" --profile "$profile"
            success "Databricks PAT configured."
            ;;
        manual)
            read -r -p "  Workspace host [$host]: " host
            read -r -p "  Profile [$profile]: " profile
            pat="$(read_secret "Enter Databricks PAT:")"
            databricks configure --host "$host" --token "$pat" --profile "$profile"
            ;;
    esac

    write_databricks_diagnostic_report "$(test_databricks_setup "$config_path")"
    ! test_databricks_setup "$config_path" | grep -q $'\tFAIL\t'
}

test_databricks_connect_cluster() {
    local config_path="$1" project_dir="$2"
    local cluster_id profile runtime
    cluster_id="$(read_config_value "$config_path" "databricks.cluster_id")"
    [[ -z "$cluster_id" ]] && { info "No cluster_id — skipping cluster validation."; return 0; }
    profile="$(read_config_value "$config_path" "databricks.profile")"
    runtime="$(read_config_value "$config_path" "databricks.cluster_runtime")"

    [[ ! -d "$project_dir" ]] && { warn "Project dir not found."; return 1; }

    (
        cd "$project_dir"
        if ! poetry run python -c "import databricks.connect" >/dev/null 2>&1; then
            fail "databricks-connect not importable."
            exit 1
        fi
        success "databricks-connect is importable."
        if command_exists databricks; then
            if databricks clusters get "$cluster_id" --profile "$profile" >/dev/null 2>&1; then
                success "Cluster '$cluster_id' accessible via CLI."
            else
                fail "Cannot access cluster $cluster_id"
                exit 1
            fi
        fi
    )
}