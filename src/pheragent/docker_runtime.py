from __future__ import annotations

import shlex
from pathlib import Path

from .models import BuildRequest, Checkpoint, CommandResult
from .process import run_command
from .utils import slugify


class DockerRuntime:
    def __init__(self, request: BuildRequest, run_id: str):
        self.request = request.normalized()
        self.run_id = run_id
        self.base_image = f"{slugify(self.request.image_prefix)}:{run_id}-base"
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
        return run_command(command, timeout=self.request.docker_build_timeout)

    def start(self, image_ref: str | None = None, *, seed_repo: bool = False) -> str:
        image = image_ref or self.base_image
        self._container_counter += 1
        name = f"{slugify(self.request.image_prefix)}-{self.run_id}-c{self._container_counter}"
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
        result = run_command(command, timeout=120)
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
        prepare_result = run_command(
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
        copy_result = run_command(
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
        copy_result = run_command(
            ["docker", "cp", str(script_path), f"{self.current_container}:{container_path}"],
            timeout=60,
        )
        if not copy_result.ok:
            return copy_result
        return self.execute_command(f"sh {container_path}", timeout=timeout)

    def execute_command(self, command: str, *, timeout: float) -> CommandResult:
        self._require_container()
        return run_command(
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
            f"{self.run_id}-{self._checkpoint_counter:03d}-{safe_block}-{slugify(kind)}"
        )
        result = run_command(
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
        run_command(["docker", "rm", "-f", self.current_container], timeout=60)
        self.current_container = None

    def cleanup(self) -> None:
        if not self.request.keep_container:
            self.remove_current_container()
        if self.request.cleanup_images:
            for image_ref in reversed(self._created_images):
                run_command(["docker", "rmi", "-f", image_ref], timeout=120)

    def _require_container(self) -> None:
        if not self.current_container:
            raise RuntimeError("container has not been started")
