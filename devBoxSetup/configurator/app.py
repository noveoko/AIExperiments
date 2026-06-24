"""FastAPI app — binds localhost only. No outbound data collection."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from configurator import __version__
from configurator.generator import generate_artifacts, write_artifacts
from configurator.profiles import (
    GENERATED_DIR,
    SetupConfig,
    SecretsConfig,
    ensure_dirs,
    list_profiles,
    load_profile,
    load_secrets,
    save_profile,
    save_secrets,
    strip_secrets,
)
from configurator.runner import run_sync

STATIC_DIR = Path(__file__).parent / "static"
SCHEMA_PATH = Path(__file__).parent / "schema.json"

app = FastAPI(
    title="DevBox Setup Configurator",
    description="Local-only environment builder. No data leaves this machine.",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SaveProfileRequest(BaseModel):
    config: SetupConfig
    secrets: SecretsConfig | None = None


class GenerateRequest(BaseModel):
    config: SetupConfig
    secrets: SecretsConfig | None = None
    include_secrets_in_preview: bool = False


class RunRequest(BaseModel):
    script: str  # doctor | bootstrap
    config: SetupConfig | None = None


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/schema")
async def get_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@app.get("/api/meta")
async def get_meta() -> dict:
    return {
        "version": __version__,
        "config_dir": str(GENERATED_DIR.parent),
        "generated_dir": str(GENERATED_DIR),
        "local_only": True,
    }


@app.get("/api/profiles")
async def get_profiles() -> list[str]:
    return list_profiles()


@app.get("/api/profiles/{name}")
async def get_profile(name: str) -> dict:
    config = load_profile(name)
    return {
        "config": config.model_dump(),
        "has_secrets": bool(
            load_secrets(name).ado_pat or load_secrets(name).databricks_token
        ),
    }


SECRET_PLACEHOLDER = "********"


@app.post("/api/profiles/{name}")
async def post_profile(name: str, body: SaveProfileRequest) -> dict:
    body.config.profile_name = name
    save_profile(body.config)
    if body.secrets is not None:
        existing = load_secrets(name)
        merged = body.secrets.model_dump()
        for field in ("ado_pat", "databricks_token"):
            val = merged.get(field, "")
            if not val or val == SECRET_PLACEHOLDER:
                merged[field] = getattr(existing, field, "")
        save_secrets(name, SecretsConfig.model_validate(merged))
    return {"saved": name}


@app.delete("/api/profiles/{name}")
async def delete_profile(name: str) -> dict:
    from configurator.profiles import PROFILES_DIR, SECRETS_FILE

    path = PROFILES_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
    if SECRETS_FILE.exists():
        store = json.loads(SECRETS_FILE.read_text())
        store.pop(name, None)
        SECRETS_FILE.write_text(json.dumps(store, indent=2))
    gen = GENERATED_DIR / name
    if gen.exists():
        shutil.rmtree(gen)
    return {"deleted": name}


@app.post("/api/generate")
async def post_generate(body: GenerateRequest) -> dict:
    artifacts = generate_artifacts(
        body.config,
        body.secrets,
        include_secrets=body.include_secrets_in_preview,
    )
    return {"artifacts": artifacts}


@app.post("/api/generate/write")
async def post_generate_write(body: GenerateRequest) -> dict:
    ensure_dirs()
    out_dir = write_artifacts(body.config, body.secrets)
    return {
        "written_to": str(out_dir),
        "files": [f.name for f in sorted(out_dir.iterdir())],
    }


@app.post("/api/run")
async def post_run(body: RunRequest) -> dict:
    if body.script not in ("doctor", "bootstrap"):
        raise HTTPException(400, "script must be 'doctor' or 'bootstrap'")
    return run_sync(body.script, body.config)


def main() -> None:
    import uvicorn

    ensure_dirs()
    uvicorn.run(
        "configurator.app:app",
        host="127.0.0.1",
        port=9477,
        reload=False,
        log_level="info",
    )