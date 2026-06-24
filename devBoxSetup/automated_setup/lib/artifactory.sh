#!/usr/bin/env bash
# Artifactory setup, snippet parsing, and diagnostics

parse_artifactory_snippet() {
    local snippet="$1"
    local source_name="" username="" token="" url=""

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [[ -z "$line" || "$line" == \#* ]] && continue

        if [[ "$line" =~ poetry[[:space:]]+config[[:space:]]+http-basic\.([^[:space:]]+)[[:space:]]+([^[:space:]]+)[[:space:]]+([^[:space:]]+) ]]; then
            source_name="${BASH_REMATCH[1]}"
            username="${BASH_REMATCH[2]}"
            token="${BASH_REMATCH[3]}"
            continue
        fi

        if [[ "$line" =~ poetry[[:space:]]+source[[:space:]]+add[[:space:]]+([^[:space:]]+)[[:space:]]+(https?://[^[:space:]]+) ]]; then
            [[ -z "$source_name" ]] && source_name="${BASH_REMATCH[1]}"
            url="${BASH_REMATCH[2]%/}"
            continue
        fi

        if [[ "$line" =~ poetry[[:space:]]+config[[:space:]]+repositories\.([^[:space:]]+)[[:space:]]+(https?://[^[:space:]]+) ]]; then
            [[ -z "$source_name" ]] && source_name="${BASH_REMATCH[1]}"
            url="${BASH_REMATCH[2]%/}"
            continue
        fi

        if [[ "$line" =~ POETRY_HTTP_BASIC_([A-Z0-9_]+)_USERNAME=(.+) ]]; then
            source_name="$(echo "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
            username="${BASH_REMATCH[2]}"
            username="${username%\"}"; username="${username#\"}"
            username="${username%\'}"; username="${username#\'}"
            continue
        fi

        if [[ "$line" =~ POETRY_HTTP_BASIC_([A-Z0-9_]+)_PASSWORD=(.+) ]]; then
            [[ -z "$source_name" ]] && source_name="$(echo "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
            token="${BASH_REMATCH[2]}"
            token="${token%\"}"; token="${token#\"}"
            token="${token%\'}"; token="${token#\'}"
            continue
        fi

        if [[ "$line" =~ pip[[:space:]]+install.*--index-url[[:space:]]+(https?://[^[:space:]]+) ]]; then
            local index_url="${BASH_REMATCH[1]}"
            if [[ "$index_url" =~ ^https?://([^:]+):([^@]+)@(.+)$ ]]; then
                username="${BASH_REMATCH[1]}"
                token="${BASH_REMATCH[2]}"
                url="https://${BASH_REMATCH[3]%/}"
            else
                url="${index_url%/}"
            fi
        fi
    done <<< "$snippet"

    printf '%s\n%s\n%s\n%s' "$source_name" "$username" "$token" "$url"
}

read_pyproject_artifactory_source() {
    local project_dir="$1"
    local pyproject="$project_dir/pyproject.toml"
    local name="" url=""
    if [[ -f "$pyproject" ]]; then
        name="$(awk '/\[\[tool.poetry.source\]\]/{found=1} found && /^name = /{gsub(/[" ]/, "", $3); print $3; exit}' "$pyproject")"
        url="$(awk '/\[\[tool.poetry.source\]\]/{found=1} found && /^url = /{gsub(/[" ]/, "", $3); print $3; exit}' "$pyproject")"
    fi
    printf '%s\n%s' "$name" "$url"
}

show_artifactory_preview() {
    local source_name="$1" username="$2" token="$3" url="$4"
    local token_len=${#token}
    echo ""
    echo "  Parsed Artifactory settings:"
    echo "    Source name : $source_name"
    echo "    Username    : $username"
    echo "    Token       : ******** ($token_len chars)"
    echo "    URL         : $url"
    echo ""
}

apply_artifactory_config() {
    local source_name="$1" username="$2" token="$3" url="$4" project_dir="${5:-}"

    if [[ -z "$source_name" || -z "$username" || -z "$token" ]]; then
        fail "Incomplete Artifactory settings. Need source name, username, and token."
        return 1
    fi
    if ! command_exists poetry; then
        fail "Poetry is not installed. Run step 4 first."
        return 1
    fi

    poetry config "http-basic.$source_name" "$username" "$token"
    write_setup_log "Artifactory: configured http-basic.$source_name for user $username (token length ${#token})"
    success "Credentials saved for Poetry source '$source_name'."

    if [[ -n "$project_dir" && -d "$project_dir" ]]; then
        local py_name py_url
        py_name="$(read_pyproject_artifactory_source "$project_dir" | sed -n '1p')"
        py_url="$(read_pyproject_artifactory_source "$project_dir" | sed -n '2p')"
        if [[ -n "$py_name" && "$py_name" != "$source_name" ]]; then
            warn "pyproject.toml source name '$py_name' does not match '$source_name'."
            info "Fix: in pyproject.toml, set name = \"$source_name\" under [[tool.poetry.source]]."
        fi
        if [[ -n "$url" && -n "$py_url" && "$py_url" != "$url" ]]; then
            warn "pyproject.toml URL differs from configured URL."
            info "Expected: $url"
            info "Found:    $py_url"
        fi
    fi
}

test_artifactory_setup() {
    local config_path="$1" project_dir="$2" verbose="${3:-false}"
    local source_name username_config url test_package token_env_var
    source_name="$(read_config_value "$config_path" "artifactory.source_name")"
    username_config="$(read_config_value "$config_path" "artifactory.username")"
    url="$(read_config_value "$config_path" "artifactory.url")"
    test_package="$(python3 - "$config_path" <<'PY'
import json, sys
config = json.load(open(sys.argv[1], encoding="utf-8"))
print(config.get("artifactory", {}).get("test_package") or "pip")
PY
)"

    local -a results=()
    local -a fixes=()

    add_diag() {
        results+=("$1	$2	$3")
        if [[ "$2" == "FAIL" || "$2" == "WARN" ]] && [[ -n "${4:-}" ]]; then
            fixes+=("$4")
        fi
    }

    if command_exists poetry; then
        add_diag "Poetry installed" "OK" "$(poetry --version 2>&1)" ""
    else
        add_diag "Poetry installed" "FAIL" "not found" "Re-run step 4: ./setup.sh --step 4"
        printf '%s\n' "${results[@]}"
        printf '---FIXES---\n'
        printf '%s\n' "${fixes[@]}"
        return 0
    fi

    local poetry_config cred_user cred_pass
    poetry_config="$(poetry config --list 2>&1)"
    cred_user="$(echo "$poetry_config" | sed -n "s/.*http-basic\.${source_name}\.username.*['\"]\\([^'\"]*\\)['\"].*/\\1/p" | head -n1)"
    cred_pass="$(echo "$poetry_config" | sed -n "s/.*http-basic\.${source_name}\.password.*['\"]\\([^'\"]*\\)['\"].*/\\1/p" | head -n1)"

    if [[ -n "$cred_user" && -n "$cred_pass" ]]; then
        add_diag "Credentials configured" "OK" "http-basic.$source_name" ""
    else
        add_diag "Credentials configured" "FAIL" "http-basic.$source_name missing" "Run ./setup.sh --artifactory-setup and paste your JFrog snippet"
    fi

    if [[ "$url" =~ ^https:// && "$url" =~ /simple$ ]]; then
        add_diag "URL format" "OK" "valid PyPI simple index" ""
    elif [[ "$url" =~ ^https:// ]]; then
        add_diag "URL format" "WARN" "missing /simple suffix" "Append /simple to URL: ${url}/simple"
    else
        add_diag "URL format" "FAIL" "invalid or missing URL" "Set artifactory.url in setup.config.json"
    fi

    if [[ -n "$project_dir" && -d "$project_dir" ]]; then
        local py_name
        py_name="$(read_pyproject_artifactory_source "$project_dir" | sed -n '1p')"
        if [[ "$py_name" == "$source_name" ]]; then
            add_diag "Source name match" "OK" "$source_name" ""
        elif [[ -n "$py_name" ]]; then
            add_diag "Source name match" "FAIL" "pyproject='$py_name' config='$source_name'" "In pyproject.toml, set name = \"$source_name\""
        else
            add_diag "Source name match" "WARN" "pyproject.toml not found yet" "Run step 9 to create the Poetry project"
        fi
    fi

    local proxy_info="none"
    [[ -n "${HTTP_PROXY:-}" || -n "${HTTPS_PROXY:-}" ]] && proxy_info="HTTP_PROXY=${HTTP_PROXY:-} HTTPS_PROXY=${HTTPS_PROXY:-}"
    add_diag "Proxy detected" "OK" "$proxy_info" ""

    if [[ -n "$url" ]]; then
        local hostname
        hostname="$(python3 -c "from urllib.parse import urlparse; print(urlparse('$url').hostname or '')")"
        if getent hosts "$hostname" >/dev/null 2>&1 || python3 -c "import socket; socket.gethostbyname('$hostname')" >/dev/null 2>&1; then
            add_diag "DNS resolve" "OK" "$hostname" ""
        else
            add_diag "DNS resolve" "FAIL" "cannot resolve $hostname" "Check VPN connection and DNS settings"
        fi

        local http_code
        http_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url" 2>/dev/null || echo "000")"
        if [[ "$http_code" == "200" || "$http_code" == "401" ]]; then
            add_diag "HTTP probe (no auth)" "OK" "HTTP $http_code" ""
        else
            add_diag "HTTP probe (no auth)" "FAIL" "HTTP $http_code" "Verify artifactory.url points to the correct PyPI repository"
        fi

        if [[ -n "$cred_user" && -n "$cred_pass" ]]; then
            local auth_code
            auth_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -u "$cred_user:$cred_pass" "$url" 2>/dev/null || echo "000")"
            if [[ "$auth_code" == "200" ]]; then
                add_diag "Auth probe" "OK" "HTTP $auth_code" ""
            else
                local fix_hint="Verify username and token from Artifactory Set Me Up page"
                [[ "$auth_code" == "401" ]] && fix_hint="Regenerate Artifactory identity token; username/token may be wrong"
                [[ "$auth_code" == "403" ]] && fix_hint="Token may lack read permission on the repository"
                add_diag "Auth probe" "FAIL" "HTTP $auth_code" "$fix_hint"
            fi
        else
            add_diag "Auth probe" "WARN" "skipped (no credentials)" ""
        fi
    fi

    if [[ -n "$cred_user" && -n "$cred_pass" && -n "$url" ]]; then
        local search_out search_status=0
        search_out="$(poetry search "$test_package" --source "$source_name" 2>&1)" || search_status=$?
        if [[ $search_status -eq 0 && "$search_out" != *error* && "$search_out" != *401* ]]; then
            add_diag "Poetry index access" "OK" "search $test_package succeeded" ""
        else
            local detail
            detail="$(echo "$search_out" | head -n1 | sed "s/$cred_pass/***/g")"
            add_diag "Poetry index access" "FAIL" "$detail" "Ensure source name in pyproject.toml matches '$source_name'"
            [[ "$verbose" == "true" ]] && info "[verbose] $search_out"
        fi
    fi

    printf '%s\n' "${results[@]}"
    printf '---FIXES---\n'
    printf '%s\n' "${fixes[@]}"
}

write_artifactory_diagnostic_report() {
    local output="$1"
    local results fixes
    results="$(printf '%s\n' "$output" | sed '/^---FIXES---$/,$d')"
    fixes="$(printf '%s\n' "$output" | sed -n '/^---FIXES---$/,$p' | tail -n +2 | sed '/^$/d')"

    echo ""
    echo "Artifactory Diagnostics"
    printf '%s\n' "------------------------------------------------------------"
    printf '%-24s %-7s %s\n' "Check" "Status" "Detail"
    printf '%s\n' "------------------------------------------------------------"
    while IFS=$'\t' read -r check status detail; do
        [[ -z "$check" ]] && continue
        printf '%-24s %-7s %s\n' "$check" "$status" "$detail"
    done <<< "$results"
    printf '%s\n' "------------------------------------------------------------"

    if [[ -n "$fixes" ]]; then
        echo ""
        echo "Suggested fixes:"
        local i=1
        while IFS= read -r fix; do
            [[ -z "$fix" ]] && continue
            echo "  $i. $fix"
            i=$((i + 1))
        done <<< "$fixes"
    fi
}

get_guided_artifactory_settings() {
    local config_path="$1"
    local source_name username url token token_env_var
    source_name="$(read_config_value "$config_path" "artifactory.source_name")"
    username="$(read_config_value "$config_path" "artifactory.username")"
    url="$(read_config_value "$config_path" "artifactory.url")"
    token_env_var="$(read_config_value "$config_path" "artifactory.token_env_var")"
    if [[ -n "$token_env_var" && -n "${!token_env_var:-}" ]]; then
        token="${!token_env_var}"
    fi
    if [[ -z "$token" ]]; then
        token="$(read_secret "Enter Artifactory token (input hidden):")"
    fi
    printf '%s\n%s\n%s\n%s' "$source_name" "$username" "$token" "$url"
}

get_pasted_artifactory_settings() {
    local config_path="$1" snippet_text="${2:-}"
    if [[ -z "$snippet_text" ]]; then
        info "Paste your Artifactory 'Set Me Up' snippet below."
        info "When finished, press Enter on an empty line:"
        echo ""
        local lines="" line
        while IFS= read -r line; do
            [[ -z "$line" ]] && break
            lines+="$line"$'\n'
        done
        snippet_text="$lines"
    fi

    local parsed source_name username token url
    parsed="$(parse_artifactory_snippet "$snippet_text")"
    source_name="$(printf '%s\n' "$parsed" | sed -n '1p')"
    username="$(printf '%s\n' "$parsed" | sed -n '2p')"
    token="$(printf '%s\n' "$parsed" | sed -n '3p')"
    url="$(printf '%s\n' "$parsed" | sed -n '4p')"

    [[ -z "$source_name" ]] && source_name="$(read_config_value "$config_path" "artifactory.source_name")"
    [[ -z "$url" ]] && url="$(read_config_value "$config_path" "artifactory.url")"
    [[ -z "$username" ]] && username="$(read_config_value "$config_path" "artifactory.username")"
    [[ -z "$token" ]] && token="$(read_secret "Snippet had no token. Enter Artifactory token:")"

    show_artifactory_preview "$source_name" "$username" "$token" "$url"
    if ! confirm_or_skip "Apply these settings?" true; then
        warn "Artifactory setup cancelled."
        return 1
    fi
    printf '%s\n%s\n%s\n%s' "$source_name" "$username" "$token" "$url"
}

get_manual_artifactory_settings() {
    local config_path="$1"
    local default_source default_user default_url
    default_source="$(read_config_value "$config_path" "artifactory.source_name")"
    default_user="$(read_config_value "$config_path" "artifactory.username")"
    default_url="$(read_config_value "$config_path" "artifactory.url")"

    local source_name username url token
    read -r -p "  Source name [$default_source]: " source_name
    [[ -z "$source_name" ]] && source_name="$default_source"
    read -r -p "  Username [$default_user]: " username
    [[ -z "$username" ]] && username="$default_user"
    read -r -p "  Repository URL [$default_url]: " url
    [[ -z "$url" ]] && url="$default_url"
    token="$(read_secret "Enter Artifactory token (input hidden):")"

    show_artifactory_preview "$source_name" "$username" "$token" "$url"
    if ! confirm_or_skip "Apply these settings?" true; then
        return 1
    fi
    printf '%s\n%s\n%s\n%s' "$source_name" "$username" "$token" "$url"
}

invoke_artifactory_setup() {
    local config_path="$1" project_dir="${2:-}" snippet_text="${3:-}" mode="${4:-menu}" verbose="${5:-false}"

    local settings="" source_name username token url diag_output

    if [[ "$mode" == "menu" && -n "$snippet_text" ]]; then
        mode="paste"
    fi

    if [[ "$mode" == "menu" ]]; then
        echo ""
        echo "  How do you want to configure Artifactory?"
        echo ""
        echo "    [1] Guided        - use setup.config.json + ARTIFACTORY_TOKEN"
        echo "    [2] Paste snippet - paste commands from Artifactory Set Me Up"
        echo "    [3] Manual entry  - type source name, username, token, URL"
        echo "    [4] Troubleshoot  - test existing setup without changing anything"
        echo ""
        local choice
        read -r -p "  Choose [1-4]: " choice
        case "$choice" in
            2) mode="paste" ;;
            3) mode="manual" ;;
            4) mode="troubleshoot" ;;
            *) mode="guided" ;;
        esac
    fi

    if [[ "$mode" == "troubleshoot" ]]; then
        diag_output="$(test_artifactory_setup "$config_path" "$project_dir" "$verbose")"
        write_artifactory_diagnostic_report "$diag_output"
        if printf '%s\n' "$diag_output" | grep -q $'\tFAIL\t'; then
            return 1
        fi
        return 0
    fi

    case "$mode" in
        guided)
            settings="$(get_guided_artifactory_settings "$config_path")" || return 1
            ;;
        paste)
            settings="$(get_pasted_artifactory_settings "$config_path" "$snippet_text")" || return 1
            ;;
        manual)
            settings="$(get_manual_artifactory_settings "$config_path")" || return 1
            ;;
    esac

    source_name="$(printf '%s\n' "$settings" | sed -n '1p')"
    username="$(printf '%s\n' "$settings" | sed -n '2p')"
    token="$(printf '%s\n' "$settings" | sed -n '3p')"
    url="$(printf '%s\n' "$settings" | sed -n '4p')"

    if [[ -z "$token" ]]; then
        warn "No Artifactory token provided."
        return 1
    fi

    apply_artifactory_config "$source_name" "$username" "$token" "$url" "$project_dir"

    diag_output="$(test_artifactory_setup "$config_path" "$project_dir" "$verbose")"
    write_artifactory_diagnostic_report "$diag_output"
    if printf '%s\n' "$diag_output" | grep -q $'\tFAIL\t'; then
        return 1
    fi
    return 0
}