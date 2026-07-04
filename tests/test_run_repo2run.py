from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any


def load_run_repo2run():
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    module_path = scripts_dir / "run_repo2run.py"
    spec = importlib.util.spec_from_file_location("run_repo2run", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def repo2run_item(index: int) -> dict[str, Any]:
    return {
        "owner_repo": f"owner/repo{index}",
        "commit": f"abc{index}",
        "project_slug": f"owner-repo{index}",
        "oracle_file": Path(f"oracle{index}.json"),
        "oracle_command_count": 1,
    }


def repo2run_payload(index: int, item: dict[str, Any], *, ok: bool) -> dict[str, Any]:
    return {
        "ok": ok,
        "index": index,
        "owner_repo": item["owner_repo"],
        "commit_version": item["commit"],
        "project_slug": item["project_slug"],
        "project_file": f"/tmp/{item['project_slug']}.txt",
        "oracle_file": str(item["oracle_file"]),
        "oracle_command_count": item["oracle_command_count"],
        "log_path": f"/tmp/{item['project_slug']}.log",
        "returncode": 0 if ok else 1,
        "manifest_path": None,
        "manifest_ok": ok,
        "manifest_error": None if ok else "failed",
        "final_image": "image:tag" if ok else None,
        "llm_usage": None,
        "command": ["true"] if ok else ["false"],
        "attempt": 1,
        "max_attempts": 1,
        "project_retries": 0,
    }


def test_build_command_keeps_inner_build_projects_single_job(tmp_path: Path) -> None:
    run_repo2run = load_run_repo2run()
    args = run_repo2run.parse_args(["--jobs", "3", "--no-require-runner"])

    command = run_repo2run.build_command(
        args=args,
        runner=["python", "-m", "pheragent"],
        item=repo2run_item(1),
        project_file=tmp_path / "project.txt",
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        base_dockerfile=tmp_path / "Dockerfile",
    )

    jobs_index = command.index("--jobs")
    assert command[jobs_index + 1] == "1"


def test_run_projects_uses_outer_jobs_for_repo_parallelism(tmp_path: Path, monkeypatch) -> None:
    run_repo2run = load_run_repo2run()
    args = run_repo2run.parse_args(["--jobs", "3", "--no-require-runner"])
    runnable = [repo2run_item(index) for index in range(1, 6)]
    jsonl_path = tmp_path / "results.jsonl"
    failures_path = tmp_path / "failures.tsv"

    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_run_project(*, index, item, **kwargs):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return repo2run_payload(index, item, ok=True)

    monkeypatch.setattr(run_repo2run, "run_project", fake_run_project)

    results, failure_count = run_repo2run.run_projects(
        args=args,
        runnable=runnable,
        runner=["python", "-m", "pheragent"],
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        project_files_root=tmp_path / "project-files",
        logs_root=tmp_path / "logs",
        base_dockerfile=tmp_path / "Dockerfile",
        jsonl_path=jsonl_path,
        failures_path=failures_path,
    )

    assert failure_count == 0
    assert len(results) == 5
    assert max_active > 1
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 5
    assert not failures_path.exists()


def test_run_projects_stop_on_failure_stops_submitting_new_projects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_repo2run = load_run_repo2run()
    args = run_repo2run.parse_args(
        ["--jobs", "2", "--stop-on-failure", "--no-require-runner"]
    )
    runnable = [repo2run_item(index) for index in range(1, 5)]
    jsonl_path = tmp_path / "results.jsonl"
    failures_path = tmp_path / "failures.tsv"
    started: list[int] = []

    def fake_run_project(*, index, item, **kwargs):
        started.append(index)
        if index == 2:
            time.sleep(0.1)
        return repo2run_payload(index, item, ok=index != 1)

    monkeypatch.setattr(run_repo2run, "run_project", fake_run_project)

    results, failure_count = run_repo2run.run_projects(
        args=args,
        runnable=runnable,
        runner=["python", "-m", "pheragent"],
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        project_files_root=tmp_path / "project-files",
        logs_root=tmp_path / "logs",
        base_dockerfile=tmp_path / "Dockerfile",
        jsonl_path=jsonl_path,
        failures_path=failures_path,
    )

    assert failure_count == 1
    assert sorted(payload["index"] for payload in results) == [1, 2]
    assert sorted(started) == [1, 2]
    failures = failures_path.read_text(encoding="utf-8").splitlines()
    assert len(failures) == 1
    assert failures[0].startswith("owner/repo1\tabc1\t1\t")
    jsonl_records = [
        json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert sorted(record["index"] for record in jsonl_records) == [1, 2]
