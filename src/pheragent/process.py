from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TextIO

from .models import CommandResult


def run_command(
    command: list[str],
    *,
    timeout: float,
    cwd: str | Path | None = None,
    stream_output: bool = False,
) -> CommandResult:
    if stream_output:
        return _run_command_streaming(command, timeout=timeout, cwd=cwd)

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


def _run_command_streaming(
    command: list[str],
    *,
    timeout: float,
    cwd: str | Path | None,
) -> CommandResult:
    start = time.monotonic()
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
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

    stdout_thread = threading.Thread(
        target=_tee_pipe,
        args=(process.stdout, stdout_chunks, sys.stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tee_pipe,
        args=(process.stderr, stderr_chunks, sys.stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        exit_code = None
        process.wait()

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    return CommandResult(
        exit_code=exit_code,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
        timed_out=timed_out,
        duration_s=time.monotonic() - start,
        command=command,
    )


def _tee_pipe(pipe, chunks: list[str], stream: TextIO) -> None:
    if pipe is None:
        return
    try:
        for chunk in iter(pipe.readline, ""):
            chunks.append(chunk)
            stream.write(chunk)
            stream.flush()
    finally:
        pipe.close()
