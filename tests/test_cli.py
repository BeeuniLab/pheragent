from __future__ import annotations

from pathlib import Path

import pytest

from pheragent.cli import _build_parser, _request_from_args


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


def test_build_without_resume_requires_base_dockerfile(tmp_path: Path) -> None:
    parser = _build_parser()
    args = parser.parse_args(["build", "--repo", str(tmp_path)])

    with pytest.raises(SystemExit, match="--base-dockerfile is required"):
        _request_from_args(args, require_dockerfile=True)
