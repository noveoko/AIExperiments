"""Run bootstrap and doctor scripts with streamed output."""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from configurator.profiles import SetupConfig

SETUP_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Job:
    id: str
    command: list[str]
    cwd: str
    env: dict[str, str]
    status: str = "running"  # running | completed | failed
    output: str = ""
    exit_code: int | None = None


_jobs: dict[str, Job] = {}
_lock = Lock()


def _setup_root() -> Path:
    return Path(os.environ.get("DEVBOX_SETUP_HOME", SETUP_ROOT))


def start_job(script_name: str, config: SetupConfig | None = None) -> str:
    root = _setup_root()
    if script_name == "doctor":
        cmd = ["bash", str(root / "scripts" / "doctor.sh")]
        cwd = str(root)
        env = os.environ.copy()
    elif script_name == "bootstrap":
        cmd = ["bash", str(root / "wsl" / "bootstrap.sh")]
        cwd = str(root)
        env = os.environ.copy()
        if config:
            if config.git_user_name:
                env["GIT_USER_NAME"] = config.git_user_name
            if config.git_user_email:
                env["GIT_USER_EMAIL"] = config.git_user_email
    else:
        raise ValueError(f"Unknown script: {script_name}")

    job_id = str(uuid.uuid4())
    job = Job(id=job_id, command=cmd, cwd=cwd, env=env)

    with _lock:
        _jobs[job_id] = job

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None
    lines: list[str] = []
    for line in proc.stdout:
        lines.append(line)
        job.output = "".join(lines)

    proc.wait()
    job.exit_code = proc.returncode
    job.status = "completed" if proc.returncode == 0 else "failed"
    job.output = "".join(lines)
    return job_id


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def run_sync(script_name: str, config: SetupConfig | None = None) -> dict:
    job_id = start_job(script_name, config)
    job = get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    return {
        "job_id": job_id,
        "status": job.status,
        "exit_code": job.exit_code,
        "output": job.output,
    }