"""Local profile and secrets storage. Nothing leaves the machine."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".config" / "devbox-setup"
PROFILES_DIR = CONFIG_DIR / "profiles"
SECRETS_FILE = CONFIG_DIR / "secrets.local.json"
GENERATED_DIR = CONFIG_DIR / "generated"

SECRET_FIELDS = frozenset({"ado_pat", "databricks_token"})


class SetupConfig(BaseModel):
    """Non-secret configuration fields."""

    profile_name: str = "default"

    # Identity
    git_user_name: str = ""
    git_user_email: str = ""

    # Azure DevOps
    ado_org: str = ""
    ado_project: str = ""
    ado_auth_method: str = "gcm"  # gcm | ssh | pat

    # Host
    environment: str = "corporate_devbox"  # corporate_devbox | local_wsl
    wsl_distro: str = "Ubuntu-24.04"
    wsl_memory_gb: int = 8
    wsl_processors: int = 4
    wsl_swap_gb: int = 4
    ide: str = "cursor"  # cursor | vscode | both
    devbox_setup_path: str = r"C:\src\devBoxSetup"

    # Python
    python_default: str = "3.12.8"
    python_versions: list[str] = Field(default_factory=lambda: ["3.12.8", "3.11.11"])
    package_manager_default: str = "uv"  # uv | poetry | per_project
    install_ruff: bool = True
    install_pytest: bool = True
    install_pre_commit: bool = True

    # Databricks
    databricks_host: str = ""
    databricks_auth: str = "cli"  # cli | token
    databricks_runtime: str = "15.4.x-scala2.12"
    databricks_connect_version: str = "15.4.*"
    uc_catalog_dev: str = "dev_catalog"
    uc_catalog_prod: str = "prod_catalog"
    uc_schema: str = "etl"
    node_type_id: str = "Standard_DS3_v2"
    num_workers: int = 2

    # CI/CD
    ci_package_manager: str = "uv"
    ci_python_versions: list[str] = Field(default_factory=lambda: ["3.12", "3.11"])
    deploy_target: str = "none"  # none | databricks
    service_connection_name: str = ""

    # Project
    bundle_name: str = "etl_project"
    package_name: str = "etl_project"


class SecretsConfig(BaseModel):
    ado_pat: str = ""
    databricks_token: str = ""


def _safe_profile_name(name: str) -> str:
    if not re.fullmatch(r"[\w.-]+", name):
        raise ValueError("Profile name may only contain letters, numbers, dots, hyphens, underscores")
    return name


def ensure_dirs() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if not SECRETS_FILE.exists():
        SECRETS_FILE.write_text("{}")
        os.chmod(SECRETS_FILE, 0o600)


def list_profiles() -> list[str]:
    ensure_dirs()
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile(name: str) -> SetupConfig:
    ensure_dirs()
    safe = _safe_profile_name(name)
    path = PROFILES_DIR / f"{safe}.json"
    if not path.exists():
        return SetupConfig(profile_name=safe)
    data = json.loads(path.read_text())
    data["profile_name"] = safe
    return SetupConfig.model_validate(data)


def save_profile(config: SetupConfig) -> None:
    ensure_dirs()
    safe = _safe_profile_name(config.profile_name)
    path = PROFILES_DIR / f"{safe}.json"
    data = config.model_dump()
    data["profile_name"] = safe
    path.write_text(json.dumps(data, indent=2))
    os.chmod(path, 0o600)


def load_secrets(profile_name: str) -> SecretsConfig:
    ensure_dirs()
    safe = _safe_profile_name(profile_name)
    if not SECRETS_FILE.exists():
        return SecretsConfig()
    store = json.loads(SECRETS_FILE.read_text())
    return SecretsConfig.model_validate(store.get(safe, {}))


def save_secrets(profile_name: str, secrets: SecretsConfig) -> None:
    ensure_dirs()
    safe = _safe_profile_name(profile_name)
    store: dict[str, Any] = {}
    if SECRETS_FILE.exists():
        store = json.loads(SECRETS_FILE.read_text())
    store[safe] = secrets.model_dump()
    SECRETS_FILE.write_text(json.dumps(store, indent=2))
    os.chmod(SECRETS_FILE, 0o600)


def merge_config(config: SetupConfig, secrets: SecretsConfig | None = None) -> dict[str, Any]:
    """Full context for template rendering. Secrets included for .env only."""
    ctx = config.model_dump()
    if secrets:
        ctx.update(secrets.model_dump())
    ctx["ado_org_url"] = f"https://dev.azure.com/{config.ado_org}" if config.ado_org else ""
    ctx["ado_clone_url"] = (
        f"https://dev.azure.com/{config.ado_org}/{config.ado_project}/_git/devBoxSetup"
        if config.ado_org and config.ado_project
        else ""
    )
    ctx["wsl_distro_slug"] = config.wsl_distro.lower().replace(" ", "-")
    return ctx


def strip_secrets(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in SECRET_FIELDS}