from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .models import CommandResult


def run_command(
    command: list[str],
    *,
    timeout: float,
    cwd: str | Path | None = None,
) -> CommandResult:
    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return CommandResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=False,
            duration_s=time.monotonic() - start,
            command=command,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            exit_code=None,
            stdout=_decode(exc.stdout),
            stderr=_decode(exc.stderr),
            timed_out=True,
            duration_s=time.monotonic() - start,
            command=command,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            exit_code=None,
            stderr=f"command_not_found: {exc}",
            duration_s=time.monotonic() - start,
            command=command,
        )
    except OSError as exc:
        return CommandResult(
            exit_code=None,
            stderr=f"os_error: {exc}",
            duration_s=time.monotonic() - start,
            command=command,
        )


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
