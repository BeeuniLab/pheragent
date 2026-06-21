from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pheragent.docker_runtime import DockerRuntime
from pheragent.models import BuildRequest, CommandResult


def test_start_seeds_repo_with_docker_cp_and_no_bind_mount(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run_command(command: list[str], *, timeout: float, cwd=None) -> CommandResult:
        del timeout, cwd
        commands.append(command)
        if command[:2] == ["docker", "inspect"]:
            return CommandResult(exit_code=1, stderr="not found")
        if command[:2] == ["docker", "run"]:
            return CommandResult(exit_code=0, stdout="container-id")
        if command[:2] == ["docker", "exec"]:
            return CommandResult(exit_code=0)
        if command[:2] == ["docker", "cp"]:
            return CommandResult(exit_code=0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("pheragent.docker_runtime.run_command", fake_run_command)
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        run_id="test",
    )
    runtime = DockerRuntime(request, "test")

    runtime.start(seed_repo=True)

    run_command = commands[1]
    assert "-v" not in run_command
    assert "--entrypoint" in run_command
    assert commands[2][:2] == ["docker", "exec"]
    assert commands[3] == [
        "docker",
        "cp",
        f"{tmp_path.resolve()}/.",
        f"{runtime.current_container}:/workspace/repo",
    ]


def test_start_removes_stale_named_container_before_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run_command(command: list[str], *, timeout: float, cwd=None) -> CommandResult:
        del timeout, cwd
        commands.append(command)
        if command[:2] == ["docker", "inspect"]:
            return CommandResult(exit_code=0, stdout="stale")
        if command[:3] == ["docker", "rm", "-f"]:
            return CommandResult(exit_code=0)
        if command[:2] == ["docker", "run"]:
            return CommandResult(exit_code=0, stdout="container-id")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("pheragent.docker_runtime.run_command", fake_run_command)
    request = BuildRequest(repo_path=tmp_path, base_dockerfile=tmp_path / "Dockerfile")
    runtime = DockerRuntime(request, "test")

    runtime.start()

    assert commands[0][:2] == ["docker", "inspect"]
    assert commands[1][:3] == ["docker", "rm", "-f"]
    assert commands[2][:2] == ["docker", "run"]


def test_generated_images_include_unique_hashes_with_same_run_id(tmp_path: Path) -> None:
    request = BuildRequest(repo_path=tmp_path, base_dockerfile=tmp_path / "Dockerfile")

    first = DockerRuntime(request, "test")
    second = DockerRuntime(request, "test")

    assert first.base_image != second.base_image
    assert re.fullmatch(r"pheragent:test-[0-9a-f]{12}-base", first.base_image)
    assert re.fullmatch(r"pheragent:test-[0-9a-f]{12}-base", second.base_image)


def test_commit_images_include_unique_hash_and_keep_resume_suffix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run_command(command: list[str], *, timeout: float, cwd=None) -> CommandResult:
        del timeout, cwd
        commands.append(command)
        if command[:2] == ["docker", "commit"]:
            return CommandResult(exit_code=0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("pheragent.docker_runtime.run_command", fake_run_command)
    request = BuildRequest(repo_path=tmp_path, base_dockerfile=tmp_path / "Dockerfile")
    runtime = DockerRuntime(request, "test")
    runtime.current_container = "container"

    checkpoint = runtime.commit(
        block_id="01-python-deps",
        parent_image_ref=runtime.base_image,
        kind="success",
    )

    assert checkpoint.image_ref == commands[0][-1]
    assert re.fullmatch(
        r"pheragent:test-[0-9a-f]{12}-001-01-python-deps-success",
        checkpoint.image_ref,
    )
    assert checkpoint.image_ref.endswith("-01-python-deps-success")


def test_execute_command_sequence_keeps_shell_state_between_commands(
    tmp_path: Path,
    monkeypatch,
) -> None:
    started_commands: list[list[str]] = []
    real_popen = subprocess.Popen

    def fake_popen(command: list[str], **kwargs):
        started_commands.append(command)
        return real_popen(["sh"], **kwargs)

    monkeypatch.setattr("pheragent.docker_runtime.subprocess.Popen", fake_popen)
    request = BuildRequest(repo_path=tmp_path, base_dockerfile=tmp_path / "Dockerfile")
    runtime = DockerRuntime(request, "test")
    runtime.current_container = "container"

    results = runtime.execute_command_sequence(
        ["VALUE=persistent", 'echo "$VALUE"'],
        timeout=5,
    )

    assert [result.exit_code for result in results] == [0, 0]
    assert results[0].stdout == ""
    assert results[1].stdout == "persistent\n"
    assert results[0].command[-1] == "VALUE=persistent"
    assert results[1].command[-1] == 'echo "$VALUE"'
    assert started_commands == [
        [
            "docker",
            "exec",
            "-i",
            "--workdir",
            "/workspace/repo",
            "container",
            "sh",
        ]
    ]
