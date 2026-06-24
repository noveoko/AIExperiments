"""Render configuration artifacts from Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from configurator.profiles import GENERATED_DIR, SetupConfig, SecretsConfig, merge_config

TEMPLATES_DIR = Path(__file__).parent / "templates"

ARTIFACT_MAP = {
    "user-customization.yaml": "user-customization.yaml.j2",
    "team-customization.yaml": "team-customization.yaml.j2",
    "databricks.yml": "databricks.yml.j2",
    "azure-pipelines.yml": "azure-pipelines-python.yml.j2",
    ".env": "dotenv.j2",
    ".wslconfig": "wslconfig.j2",
    "profile-summary.md": "profile-summary.md.j2",
}


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def generate_artifacts(
    config: SetupConfig,
    secrets: SecretsConfig | None = None,
    include_secrets: bool = False,
) -> dict[str, str]:
    """Render all artifacts. Secrets only included when include_secrets=True (.env)."""
    env = _environment()
    ctx = merge_config(config, secrets if include_secrets else None)
    ctx["include_deploy_stage"] = config.deploy_target == "databricks"
    ctx["install_cursor"] = config.ide in ("cursor", "both")
    ctx["install_vscode"] = config.ide in ("vscode", "both")

    artifacts: dict[str, str] = {}
    for output_name, template_name in ARTIFACT_MAP.items():
        template = env.get_template(template_name)
        content = template.render(**ctx)
        if output_name == ".env" and not include_secrets:
            # Redact secret values in preview
            content = _redact_env(content)
        artifacts[output_name] = content
    return artifacts


def _redact_env(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if any(
            line.startswith(prefix)
            for prefix in ("ADO_PAT=", "DATABRICKS_TOKEN=", "AZURE_DEVOPS_EXT_PAT=")
        ):
            key = line.split("=", 1)[0]
            lines.append(f"{key}=***REDACTED***")
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def write_artifacts(
    config: SetupConfig,
    secrets: SecretsConfig | None = None,
    subdirectory: str | None = None,
) -> Path:
    """Write generated artifacts to ~/.config/devbox-setup/generated/."""
    out_dir = GENERATED_DIR / (subdirectory or config.profile_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = generate_artifacts(config, secrets, include_secrets=True)
    for name, content in artifacts.items():
        (out_dir / name).write_text(content)

    return out_dir