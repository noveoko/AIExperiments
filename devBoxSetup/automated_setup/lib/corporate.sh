#!/usr/bin/env bash
# Corporate network: proxy, SSL, connectivity probes, IT export

get_corporate_config_value() {
    local config_path="$1"
    local key="$2"
    local default="${3:-}"
    python3 - "$config_path" "$key" "$default" <<'PY'
import json, sys
config = json.load(open(sys.argv[1], encoding="utf-8"))
corp = config.get("corporate", {})
val = corp.get(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
if isinstance(val, bool):
    print("true" if val else "false")
else:
    print(val or "")
PY
}

get_url_hostname() {
    python3 - "$1" <<'PY'
from urllib.parse import urlparse
import sys
print(urlparse(sys.argv[1]).hostname or "")
PY
}

get_detected_system_proxy() {
    if [[ -n "${HTTPS_PROXY:-}" ]]; then echo "$HTTPS_PROXY"; return; fi
    if [[ -n "${HTTP_PROXY:-}" ]]; then echo "$HTTP_PROXY"; return; fi
    if [[ -n "${https_proxy:-}" ]]; then echo "$https_proxy"; return; fi
    if [[ -n "${http_proxy:-}" ]]; then echo "$http_proxy"; return; fi
    echo ""
}

set_corporate_proxy() {
    local proxy_url="$1"
    local no_proxy="$2"
    [[ -z "$proxy_url" ]] && return 1
    export HTTP_PROXY="$proxy_url"
    export HTTPS_PROXY="$proxy_url"
    export NO_PROXY="$no_proxy"
    export http_proxy="$proxy_url"
    export https_proxy="$proxy_url"
    export no_proxy="$no_proxy"
    if command_exists git; then
        git config --global http.proxy "$proxy_url" 2>/dev/null || true
        git config --global https.proxy "$proxy_url" 2>/dev/null || true
    fi
    write_setup_log "Corporate: proxy set to $proxy_url"
    success "Proxy configured: $proxy_url"
}

set_corporate_ca_bundle() {
    local ca_path="$1"
    [[ ! -f "$ca_path" ]] && { warn "CA bundle not found: $ca_path"; return 1; }
    export SSL_CERT_FILE="$ca_path"
    export REQUESTS_CA_BUNDLE="$ca_path"
    if command_exists git; then
        git config --global http.sslCAInfo "$ca_path" 2>/dev/null || true
    fi
    write_setup_log "Corporate: CA bundle set to $ca_path"
    success "Corporate CA bundle configured."
}

test_endpoint_connectivity() {
    local label="$1"
    local url="$2"
    [[ -z "$url" ]] && { echo "$label	SKIP	not configured"; return; }
    local hostname
    hostname="$(get_url_hostname "$url")"
    [[ -z "$hostname" ]] && { echo "$label	FAIL	invalid URL	Check URL in setup.config.json"; return; }

    if ! getent hosts "$hostname" >/dev/null 2>&1 && ! python3 -c "import socket; socket.gethostbyname('$hostname')" >/dev/null 2>&1; then
        echo "$label	FAIL	DNS failed	Connect to VPN"
        return
    fi

    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url" 2>/dev/null || echo "000")"
    if [[ "$code" == "200" || "$code" == "401" || "$code" == "407" ]]; then
        echo "$label	OK	HTTP $code"
    elif [[ "$code" == "000" ]]; then
        echo "$label	FAIL	connection failed	Check proxy/VPN (step 2)"
    else
        echo "$label	WARN	HTTP $code	Host reachable, unexpected status"
    fi
}

write_connectivity_report() {
    echo ""
    echo "Connectivity Probes"
    printf '%s\n' "------------------------------------------------------------"
    while IFS=$'\t' read -r label status detail fix; do
        printf '%-22s %-7s %s\n' "$label" "$status" "$detail"
        [[ -n "$fix" && "$fix" != "$detail" ]] && info "  Fix: $fix"
    done
    printf '%s\n' "------------------------------------------------------------"
}

invoke_corporate_network_setup() {
    local config_path="$1"
    local proxy_url no_proxy ca_path detected art_host db_host
    proxy_url="$(get_corporate_config_value "$config_path" "proxy_url")"
    no_proxy="$(get_corporate_config_value "$config_path" "no_proxy" "localhost,127.0.0.1")"
    ca_path="$(get_corporate_config_value "$config_path" "ca_bundle_path")"
    detected="$(get_detected_system_proxy)"

    if [[ -z "$proxy_url" && -n "$detected" ]]; then
        info "Detected proxy: $detected"
        if confirm_or_skip "Use detected proxy?" true; then
            proxy_url="$detected"
        fi
    fi
    if [[ -z "$proxy_url" ]]; then
        read -r -p "  Proxy URL (blank if none): " proxy_url
    fi

    art_host="$(get_url_hostname "$(read_config_value "$config_path" "artifactory.url")")"
    db_host="$(get_url_hostname "$(read_config_value "$config_path" "databricks.host")")"
    [[ -n "$art_host" && "$no_proxy" != *"$art_host"* ]] && no_proxy="$no_proxy,$art_host"
    [[ -n "$db_host" && "$no_proxy" != *"$db_host"* ]] && no_proxy="$no_proxy,$db_host"

    if [[ -n "$proxy_url" ]]; then
        set_corporate_proxy "$proxy_url" "$no_proxy"
    else
        info "No proxy configured."
    fi

    if [[ -z "$ca_path" ]]; then
        read -r -p "  CA bundle path (blank if not needed): " ca_path
    fi
    [[ -n "$ca_path" ]] && set_corporate_ca_bundle "$ca_path"

    local probes=""
    probes+="$(test_endpoint_connectivity "Artifactory" "$(read_config_value "$config_path" "artifactory.url")")"$'\n'
    probes+="$(test_endpoint_connectivity "Databricks" "$(read_config_value "$config_path" "databricks.host")")"$'\n'
    probes+="$(test_endpoint_connectivity "GitHub" "https://github.com")"$'\n'
    probes+="$(test_endpoint_connectivity "Poetry installer" "https://install.python-poetry.org")"$'\n'
    echo "$probes" | write_connectivity_report

    if echo "$probes" | grep -q $'\tFAIL\t'; then
        warn "Some endpoints unreachable. Run --generate-it-whitelist for an IT ticket."
        return 1
    fi
    return 0
}

export_it_whitelist() {
    local config_path="$1"
    local output_path="$2"
    {
        echo "# IT Firewall / Proxy Whitelist Request"
        echo "# Generated: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "# User: $(whoami)"
        echo ""
        echo "Outbound HTTPS (TCP 443) required for:"
        echo "  - $(get_url_hostname "$(read_config_value "$config_path" "artifactory.url")")  (Artifactory)"
        echo "  - $(get_url_hostname "$(read_config_value "$config_path" "databricks.host")")  (Databricks)"
        echo "  - github.com  (pre-commit, pyenv, CLI installers)"
        echo "  - raw.githubusercontent.com"
        echo "  - install.python-poetry.org"
        echo "  - www.python.org"
        echo ""
        echo "Ports: 443 (outbound)"
    } > "$output_path"
    success "IT whitelist written to: $output_path"
}

export_support_bundle() {
    local config_path="$1" repo_root="$2" project_dir="${3:-}"
    local bundle_dir="$repo_root/support-bundle"
    rm -rf "$bundle_dir"
    mkdir -p "$bundle_dir"
    [[ -f "$repo_root/setup.log" ]] && cp "$repo_root/setup.log" "$bundle_dir/"
    {
        echo "Support Bundle Summary"
        echo "Generated: $(date)"
        echo "HTTP_PROXY=${HTTP_PROXY:-}"
        echo "HTTPS_PROXY=${HTTPS_PROXY:-}"
        command_exists python && python --version 2>&1
        command_exists poetry && poetry --version 2>&1
        command_exists databricks && databricks -v 2>&1
    } > "$bundle_dir/environment-summary.txt"
    (cd "$bundle_dir" && zip -qr "$repo_root/support-bundle.zip" .) 2>/dev/null || true
    success "Support bundle: $repo_root/support-bundle.zip"
}

test_github_reachability() {
    test_endpoint_connectivity "github.com" "https://github.com"
}

apply_github_mirror_to_precommit() {
    local precommit_path="$1"
    local mirror="$2"
    [[ ! -f "$precommit_path" || -z "$mirror" ]] && return 1
    mirror="${mirror%/}"
    sed -i "s|https://github.com/|${mirror}/|g" "$precommit_path" 2>/dev/null \
        || sed -i '' "s|https://github.com/|${mirror}/|g" "$precommit_path"
    success "Rewrote pre-commit repos to use mirror: $mirror"
}