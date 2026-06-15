from __future__ import annotations

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

    run_command = commands[0]
    assert "-v" not in run_command
    assert "--entrypoint" in run_command
    assert commands[1][:2] == ["docker", "exec"]
    assert commands[2] == [
        "docker",
        "cp",
        f"{tmp_path.resolve()}/.",
        f"{runtime.current_container}:/workspace/repo",
    ]
