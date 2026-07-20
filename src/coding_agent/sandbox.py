from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .models import CommandResult


class DockerSandbox:
    """Runs commands in an unprivileged, network-isolated disposable container."""

    def __init__(self, image: str | None = None, timeout_seconds: int = 120) -> None:
        self.image = image or os.getenv("SANDBOX_IMAGE", "code-agent-sandbox:latest")
        self.timeout_seconds = timeout_seconds

    def run(self, repo: Path, command: str) -> CommandResult:
        args = [
            "docker", "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "512m",
            "--pids-limit", "128", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "-v", f"{repo.resolve()}:/workspace:rw", "-w", "/workspace", self.image,
            "sh", "-lc", command,
        ]
        started = time.monotonic()
        try:
            done = subprocess.run(args, text=True, capture_output=True, timeout=self.timeout_seconds)
            return CommandResult(command=command, exit_code=done.returncode, stdout=done.stdout,
                                 stderr=done.stderr, duration_ms=int((time.monotonic() - started) * 1000))
        except subprocess.TimeoutExpired as error:
            return CommandResult(command=command, exit_code=124, stdout=error.stdout or "",
                                 stderr=error.stderr or "", timed_out=True,
                                 duration_ms=int((time.monotonic() - started) * 1000))
