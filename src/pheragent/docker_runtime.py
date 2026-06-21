from __future__ import annotations

import contextlib
import queue
import shlex
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import TextIO

from .models import BuildRequest, Checkpoint, CommandResult
from .process import run_command
from .utils import slugify


class DockerRuntime:
    def __init__(self, request: BuildRequest, run_id: str):
        self.request = request.normalized()
        self.run_id = run_id
        self.base_image = (
            f"{slugify(self.request.image_prefix)}:{run_id}-{self._new_image_hash()}-base"
        )
        self.current_container: str | None = None
        self._container_counter = 0
        self._checkpoint_counter = 0
        self._created_images: list[str] = [self.base_image]

    def build_base_image(self) -> CommandResult:
        if self.request.base_dockerfile is None:
            raise ValueError("base_dockerfile is required for Docker build")
        if not self.request.base_dockerfile.is_file():
            raise ValueError(f"base Dockerfile not found: {self.request.base_dockerfile}")
        command = [
            "docker",
            "build",
            "-f",
            str(self.request.base_dockerfile),
            "-t",
            self.base_image,
            str(self.request.repo_path),
        ]
        return self._run_command(command, timeout=self.request.docker_build_timeout)

    def start(self, image_ref: str | None = None, *, seed_repo: bool = False) -> str:
        image = image_ref or self.base_image
        self._container_counter += 1
        name = f"{slugify(self.request.image_prefix)}-{self.run_id}-c{self._container_counter}"
        self._remove_container_by_name(name)
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--entrypoint",
            "sh",
            image,
            "-lc",
            "trap : TERM INT; sleep infinity & wait",
        ]
        result = self._run_command(command, timeout=120)
        if not result.ok:
            raise RuntimeError(f"docker run failed: {result.combined_output}")
        self.current_container = name
        if seed_repo:
            self.copy_repo_into_container()
        return name

    def copy_repo_into_container(self) -> None:
        self._require_container()
        workdir = self.request.container_workdir.rstrip("/")
        if not workdir.startswith("/") or workdir == "/":
            raise ValueError(f"container_workdir must be an absolute non-root path: {workdir}")
        prepare_result = self._run_command(
            [
                "docker",
                "exec",
                self.current_container or "",
                "sh",
                "-lc",
                f"rm -rf {shlex.quote(workdir)} && mkdir -p {shlex.quote(workdir)}",
            ],
            timeout=120,
        )
        if not prepare_result.ok:
            raise RuntimeError(
                f"failed to prepare container workdir: {prepare_result.combined_output}"
            )
        source = f"{self.request.repo_path}/."
        copy_result = self._run_command(
            ["docker", "cp", source, f"{self.current_container}:{workdir}"],
            timeout=max(120.0, min(self.request.command_timeout, 900.0)),
        )
        if not copy_result.ok:
            raise RuntimeError(f"failed to copy repo into container: {copy_result.combined_output}")

    def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
        container_path = f"/tmp/pheragent/blocks/{script_path.name}"
        self._require_container()
        mkdir_result = self.execute_command("mkdir -p /tmp/pheragent/blocks", timeout=30)
        if not mkdir_result.ok:
            return mkdir_result
        copy_result = self._run_command(
            ["docker", "cp", str(script_path), f"{self.current_container}:{container_path}"],
            timeout=60,
        )
        if not copy_result.ok:
            return copy_result
        return self.execute_command(f"sh {container_path}", timeout=timeout)

    def execute_command(self, command: str, *, timeout: float) -> CommandResult:
        self._require_container()
        return self._run_command(
            [
                "docker",
                "exec",
                "--workdir",
                self.request.container_workdir,
                self.current_container or "",
                "sh",
                "-lc",
                command,
            ],
            timeout=timeout,
        )

    def execute_command_sequence(
        self,
        commands: list[str],
        *,
        timeout: float,
    ) -> list[CommandResult]:
        self._require_container()
        if not commands:
            return []
        shell_command = [
            "docker",
            "exec",
            "-i",
            "--workdir",
            self.request.container_workdir,
            self.current_container or "",
            "sh",
        ]
        start = time.monotonic()
        try:
            process = subprocess.Popen(
                shell_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except FileNotFoundError as exc:
            return [
                CommandResult(
                    exit_code=None,
                    stderr=f"command_not_found: {exc}",
                    duration_s=time.monotonic() - start,
                    command=[
                        *shell_command,
                        "pheragent-command-forward-persistent",
                        "1",
                        commands[0],
                    ],
                )
            ]
        except OSError as exc:
            return [
                CommandResult(
                    exit_code=None,
                    stderr=f"os_error: {exc}",
                    duration_s=time.monotonic() - start,
                    command=[
                        *shell_command,
                        "pheragent-command-forward-persistent",
                        "1",
                        commands[0],
                    ],
                )
            ]

        output_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()
        stdout_thread = threading.Thread(
            target=_enqueue_pipe,
            args=("stdout", process.stdout, output_queue),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_enqueue_pipe,
            args=("stderr", process.stderr, output_queue),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        results: list[CommandResult] = []
        try:
            try:
                _write_shell(process, "set -eu\n")
            except BrokenPipeError:
                results.append(
                    CommandResult(
                        exit_code=process.poll(),
                        stderr="persistent shell exited before initialization",
                        duration_s=time.monotonic() - start,
                        command=[
                            *shell_command,
                            "pheragent-command-forward-persistent",
                            "1",
                            commands[0],
                        ],
                    )
                )
                return results
            for index, command in enumerate(commands, start=1):
                result = self._execute_persistent_shell_command(
                    process=process,
                    output_queue=output_queue,
                    command=command,
                    command_index=index,
                    shell_command=shell_command,
                    timeout=timeout,
                )
                results.append(result)
                if not result.ok:
                    break
        finally:
            if process.poll() is None:
                with contextlib.suppress(BrokenPipeError):
                    _write_shell(process, "exit\n")
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
        return results

    def _execute_persistent_shell_command(
        self,
        *,
        process: subprocess.Popen[str],
        output_queue: queue.Queue[tuple[str, str | None]],
        command: str,
        command_index: int,
        shell_command: list[str],
        timeout: float,
    ) -> CommandResult:
        start = time.monotonic()
        sentinel = f"__PHERAGENT_DONE_{uuid.uuid4().hex}__"
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        try:
            _write_shell(
                process,
                (
                    f"\n{command}\n"
                    "_pheragent_status=$?\n"
                    f"printf '\\n{sentinel}:%s\\n' \"$_pheragent_status\"\n"
                ),
            )
        except BrokenPipeError:
            return CommandResult(
                exit_code=process.poll(),
                stderr="persistent shell exited before command could be written",
                duration_s=time.monotonic() - start,
                command=[
                    *shell_command,
                    "pheragent-command-forward-persistent",
                    str(command_index),
                    command,
                ],
            )

        exit_code: int | None = None
        timed_out = False
        while True:
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0:
                timed_out = True
                process.kill()
                exit_code = None
                break
            try:
                stream_name, chunk = output_queue.get(timeout=min(0.1, remaining))
            except queue.Empty:
                if process.poll() is not None:
                    exit_code = process.returncode
                    break
                continue
            if chunk is None:
                if process.poll() is not None:
                    exit_code = process.returncode
                    break
                continue
            if stream_name == "stdout":
                stdout_chunks.append(chunk)
                if self.request.stream_logs:
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                stdout_text = "".join(stdout_chunks)
                marker_index = stdout_text.find(sentinel)
                if marker_index >= 0:
                    marker_tail = stdout_text[marker_index + len(sentinel) :]
                    marker_line = marker_tail.splitlines()[0] if marker_tail else ""
                    if marker_line.startswith(":"):
                        try:
                            exit_code = int(marker_line[1:])
                        except ValueError:
                            exit_code = 1
                        _drain_available_output(
                            output_queue,
                            stdout_chunks=stdout_chunks,
                            stderr_chunks=stderr_chunks,
                            stream_logs=self.request.stream_logs,
                        )
                        break
            else:
                stderr_chunks.append(chunk)
                if self.request.stream_logs:
                    sys.stderr.write(chunk)
                    sys.stderr.flush()

        _drain_available_output(
            output_queue,
            stdout_chunks=stdout_chunks,
            stderr_chunks=stderr_chunks,
            stream_logs=self.request.stream_logs,
        )
        stdout = _strip_sentinel("".join(stdout_chunks), sentinel)
        stderr = "".join(stderr_chunks)
        if timed_out:
            stderr = (stderr + "\n[persistent shell timed out]").strip()
        elif exit_code is None:
            exit_code = process.poll()
            stderr = (stderr + "\n[persistent shell exited without status sentinel]").strip()
        return CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_s=time.monotonic() - start,
            command=[
                *shell_command,
                "pheragent-command-forward-persistent",
                str(command_index),
                command,
            ],
        )

    def commit(
        self,
        *,
        block_id: str | None,
        parent_image_ref: str | None,
        kind: str,
    ) -> Checkpoint:
        self._require_container()
        self._checkpoint_counter += 1
        safe_block = slugify(block_id or "base")
        image_ref = (
            f"{slugify(self.request.image_prefix)}:"
            f"{self.run_id}-{self._new_image_hash()}-"
            f"{self._checkpoint_counter:03d}-{safe_block}-{slugify(kind)}"
        )
        result = self._run_command(
            ["docker", "commit", self.current_container or "", image_ref],
            timeout=600,
        )
        if not result.ok:
            raise RuntimeError(f"docker commit failed: {result.combined_output}")
        self._created_images.append(image_ref)
        return Checkpoint(
            id=f"checkpoint-{self._checkpoint_counter:03d}",
            image_ref=image_ref,
            block_id=block_id,
            parent_image_ref=parent_image_ref,
            kind=kind,
        )

    def recreate_from(self, image_ref: str) -> str:
        self.remove_current_container()
        return self.start(image_ref)

    def remove_current_container(self) -> None:
        if not self.current_container:
            return
        self._run_command(["docker", "rm", "-f", self.current_container], timeout=60)
        self.current_container = None

    def _remove_container_by_name(self, name: str) -> None:
        inspect = run_command(["docker", "inspect", name], timeout=30)
        if inspect.ok:
            run_command(["docker", "rm", "-f", name], timeout=60)

    def _new_image_hash(self) -> str:
        return uuid.uuid4().hex[:12]

    def cleanup(self) -> None:
        if not self.request.keep_container:
            self.remove_current_container()
        if self.request.cleanup_images:
            for image_ref in reversed(self._created_images):
                self._run_command(["docker", "rmi", "-f", image_ref], timeout=120)

    def _require_container(self) -> None:
        if not self.current_container:
            raise RuntimeError("container has not been started")

    def _run_command(self, command: list[str], *, timeout: float) -> CommandResult:
        if self.request.stream_logs:
            return run_command(command, timeout=timeout, stream_output=True)
        return run_command(command, timeout=timeout)


def _write_shell(process: subprocess.Popen[str], text: str) -> None:
    if process.stdin is None:
        raise BrokenPipeError("persistent shell stdin is closed")
    process.stdin.write(text)
    process.stdin.flush()


def _enqueue_pipe(
    stream_name: str,
    pipe: TextIO | None,
    output_queue: queue.Queue[tuple[str, str | None]],
) -> None:
    if pipe is None:
        output_queue.put((stream_name, None))
        return
    try:
        for line in iter(pipe.readline, ""):
            output_queue.put((stream_name, line))
    finally:
        pipe.close()
        output_queue.put((stream_name, None))


def _drain_available_output(
    output_queue: queue.Queue[tuple[str, str | None]],
    *,
    stdout_chunks: list[str],
    stderr_chunks: list[str],
    stream_logs: bool,
) -> None:
    while True:
        try:
            stream_name, chunk = output_queue.get_nowait()
        except queue.Empty:
            return
        if chunk is None:
            continue
        if stream_name == "stdout":
            stdout_chunks.append(chunk)
            if stream_logs:
                sys.stdout.write(chunk)
                sys.stdout.flush()
        else:
            stderr_chunks.append(chunk)
            if stream_logs:
                sys.stderr.write(chunk)
                sys.stderr.flush()


def _strip_sentinel(stdout: str, sentinel: str) -> str:
    marker_index = stdout.find(sentinel)
    if marker_index < 0:
        return stdout
    line_start = stdout.rfind("\n", 0, marker_index) + 1
    line_end = stdout.find("\n", marker_index)
    if line_end < 0:
        line_end = len(stdout)
    else:
        line_end += 1
    prefix = stdout[:line_start]
    if prefix.endswith("\n"):
        prefix = prefix[:-1]
    return prefix + stdout[line_end:]
