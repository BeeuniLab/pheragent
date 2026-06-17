from __future__ import annotations

from pathlib import Path

import pytest

from pheragent.cli import _batch_base_request_from_args, _build_parser, _request_from_args


def test_build_resume_from_does_not_require_base_dockerfile(tmp_path: Path) -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "build",
            "--repo",
            str(tmp_path),
            "--resume-from",
            "pheragent:previous-checkpoint",
            "--start-at-block",
            "02-tests",
        ]
    )

    request = _request_from_args(args, require_dockerfile=True)

    assert request.base_dockerfile is None
    assert request.resume_from == "pheragent:previous-checkpoint"
    assert request.start_at_block == "02-tests"


def test_build_accepts_chat_completions_llm_api(tmp_path: Path) -> None:
    parser = _build_parser()
    args = parser.parse_args(
        [
            "build",
            "--repo",
            str(tmp_path),
            "--base-dockerfile",
            str(tmp_path / "Dockerfile"),
            "--llm-api",
            "chat-completions",
        ]
    )

    request = _request_from_args(args, require_dockerfile=True)

    assert request.llm_api == "chat-completions"


def test_build_accepts_task_description_and_task_file(tmp_path: Path) -> None:
    task_file = tmp_path / "task.txt"
    task_file.write_text("Install speech CLI support\n", encoding="utf-8")
    parser = _build_parser()
    args = parser.parse_args(
        [
            "build",
            "--repo",
            str(tmp_path),
            "--base-dockerfile",
            str(tmp_path / "Dockerfile"),
            "--task-file",
            str(task_file),
            "--task-description",
            "Validate python -m whisper --help.",
        ]
    )

    request = _request_from_args(args, require_dockerfile=True)

    assert request.task_description == (
        "Install speech CLI support\n\nValidate python -m whisper --help."
    )


def test_build_projects_accepts_task_description(tmp_path: Path) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("owner/repo abc123\n", encoding="utf-8")
    parser = _build_parser()
    args = parser.parse_args(
        [
            "build-projects",
            "--projects-file",
            str(projects_file),
            "--base-dockerfile",
            str(tmp_path / "Dockerfile"),
            "--task-description",
            "Setup repo for its SetupBench validation.",
        ]
    )

    request = _batch_base_request_from_args(args)

    assert request.task_description == "Setup repo for its SetupBench validation."


def test_build_without_resume_requires_base_dockerfile(tmp_path: Path) -> None:
    parser = _build_parser()
    args = parser.parse_args(["build", "--repo", str(tmp_path)])

    with pytest.raises(SystemExit, match="--base-dockerfile is required"):
        _request_from_args(args, require_dockerfile=True)
