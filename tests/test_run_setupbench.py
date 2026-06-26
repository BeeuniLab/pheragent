from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def load_run_setupbench():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_setupbench.py"
    spec = importlib.util.spec_from_file_location("run_setupbench", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_find_manifest_searches_nested_project_state(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    manifest = tmp_path / "state" / "slug" / "repo" / "runs" / "run-id" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"ok": true}\n', encoding="utf-8")

    assert run_setupbench.find_manifest(tmp_path / "state" / "slug") == manifest


def test_prepare_result_files_preserves_existing_files_by_default(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    jsonl_path = tmp_path / "results.jsonl"
    failures_path = tmp_path / "failures.tsv"
    jsonl_path.write_text("old-result\n", encoding="utf-8")
    failures_path.write_text("old-failure\n", encoding="utf-8")

    run_setupbench.prepare_result_files(
        jsonl_path=jsonl_path,
        failures_path=failures_path,
        fresh=False,
    )

    assert jsonl_path.read_text(encoding="utf-8") == "old-result\n"
    assert failures_path.read_text(encoding="utf-8") == "old-failure\n"


def test_prepare_result_files_can_start_fresh(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    jsonl_path = tmp_path / "results.jsonl"
    failures_path = tmp_path / "failures.tsv"
    jsonl_path.write_text("old-result\n", encoding="utf-8")
    failures_path.write_text("old-failure\n", encoding="utf-8")

    run_setupbench.prepare_result_files(
        jsonl_path=jsonl_path,
        failures_path=failures_path,
        fresh=True,
    )

    assert jsonl_path.read_text(encoding="utf-8") == ""
    assert failures_path.read_text(encoding="utf-8") == ""


def test_read_manifest_info_extracts_summary_fields(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "ok": False,
                "error": "block failed: 03-build-test-prep",
                "final_image": "image:tag",
                "llm_usage": {"total": {"requests": 3, "total_tokens": 123}},
            }
        ),
        encoding="utf-8",
    )

    assert run_setupbench.read_manifest_info(manifest) == {
        "ok": False,
        "error": "block failed: 03-build-test-prep",
        "final_image": "image:tag",
        "llm_usage": {"requests": 3, "total_tokens": 123},
    }


def test_select_items_can_filter_previous_failures_before_limit() -> None:
    run_setupbench = load_run_setupbench()
    items = [
        {"owner_repo": "one/ok", "commit_version": "1", "oracle_file": "one.json"},
        {"owner_repo": "two/fail", "commit_version": "2", "oracle_file": "two.json"},
        {"owner_repo": "three/fail", "commit_version": "3", "oracle_file": "three.json"},
    ]

    selected = run_setupbench.select_items(
        items,
        start=0,
        limit=1,
        only=None,
        only_owner_repos={"two/fail", "three/fail"},
    )

    assert [item["owner_repo"] for item in selected] == ["two/fail"]


def test_failure_records_round_trip_and_replace_selected_failures(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    failures_path = tmp_path / "failures.tsv"
    run_setupbench.write_failure_records(
        failures_path,
        [
            {
                "owner_repo": "one/old-fail",
                "commit_version": "abc",
                "returncode": "1",
                "manifest_path": "/m1",
                "oracle_file": "/o1",
                "log_path": "/l1",
            },
            {
                "owner_repo": "two/rerun",
                "commit_version": "def",
                "returncode": "1",
                "manifest_path": "/m2",
                "oracle_file": "/o2",
                "log_path": "/l2",
            },
        ],
    )
    records = run_setupbench.load_failure_records(failures_path)
    retained = [record for record in records if record["owner_repo"] != "two/rerun"]
    run_setupbench.write_failure_records(failures_path, retained)

    assert run_setupbench.load_failure_records(failures_path) == [
        {
            "owner_repo": "one/old-fail",
            "commit_version": "abc",
            "returncode": "1",
            "manifest_path": "/m1",
            "oracle_file": "/o1",
            "log_path": "/l1",
        }
    ]


def test_update_failure_record_is_interruption_safe(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    failures_path = tmp_path / "failures.tsv"
    run_setupbench.write_failure_records(
        failures_path,
        [
            {
                "owner_repo": "one/rerun",
                "commit_version": "abc",
                "returncode": "1",
                "manifest_path": "/old-m1",
                "oracle_file": "/old-o1",
                "log_path": "/old-l1",
            },
            {
                "owner_repo": "two/unprocessed",
                "commit_version": "def",
                "returncode": "1",
                "manifest_path": "/old-m2",
                "oracle_file": "/old-o2",
                "log_path": "/old-l2",
            },
        ],
    )

    run_setupbench.update_failure_record(
        failures_path,
        {
            "owner_repo": "one/rerun",
            "commit_version": "abc",
            "returncode": 0,
            "manifest_path": "/new-m1",
            "oracle_file": "/new-o1",
            "log_path": "/new-l1",
        },
        failed=False,
    )

    assert run_setupbench.load_failure_records(failures_path) == [
        {
            "owner_repo": "two/unprocessed",
            "commit_version": "def",
            "returncode": "1",
            "manifest_path": "/old-m2",
            "oracle_file": "/old-o2",
            "log_path": "/old-l2",
        }
    ]

    run_setupbench.update_failure_record(
        failures_path,
        {
            "owner_repo": "two/unprocessed",
            "commit_version": "def",
            "returncode": 1,
            "manifest_path": "/new-m2",
            "oracle_file": "/new-o2",
            "log_path": "/new-l2",
        },
        failed=True,
    )

    assert run_setupbench.load_failure_records(failures_path) == [
        {
            "owner_repo": "two/unprocessed",
            "commit_version": "def",
            "returncode": "1",
            "manifest_path": "/new-m2",
            "oracle_file": "/new-o2",
            "log_path": "/new-l2",
        }
    ]


def test_reset_selected_failed_workspaces_removes_project_and_state_only(
    tmp_path: Path,
) -> None:
    run_setupbench = load_run_setupbench()
    projects_root = tmp_path / "projects"
    state_root = tmp_path / "state"
    failed_slug = "owner-failed"
    other_slug = "owner-ok"
    (projects_root / failed_slug / "repo").mkdir(parents=True)
    (state_root / failed_slug / "repo" / "runs").mkdir(parents=True)
    (projects_root / other_slug / "repo").mkdir(parents=True)
    (state_root / other_slug / "repo" / "runs").mkdir(parents=True)

    run_setupbench.reset_selected_failed_workspaces(
        [{"owner_repo": "owner/failed"}],
        projects_root=projects_root,
        state_root=state_root,
    )

    assert not (projects_root / failed_slug).exists()
    assert not (state_root / failed_slug).exists()
    assert (projects_root / other_slug / "repo").is_dir()
    assert (state_root / other_slug / "repo" / "runs").is_dir()


def test_load_index_preserves_task_description_field(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "oracles": [
                    {
                        "owner_repo": "openai/whisper",
                        "commit_version": "abc123",
                        "oracle_file": str(tmp_path / "oracle.json"),
                        "task_description": "Install whisper CLI support.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    items = run_setupbench.load_index(index)

    assert items[0]["task_description"] == "Install whisper CLI support."


def test_task_description_prefers_index_text_over_oracle(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    oracle = tmp_path / "oracle.json"
    oracle.write_text(
        json.dumps({"description": "Oracle fallback description."}),
        encoding="utf-8",
    )

    description = run_setupbench.task_description_for_item(
        {"task_description": "Index task description."},
        oracle,
    )

    assert description == "Index task description."


def test_oracle_task_description_uses_original_validation_command() -> None:
    run_setupbench = load_run_setupbench()

    description = run_setupbench.oracle_task_description(
        {
            "fixed_test_commands": [
                {
                    "name": "setupbench validation",
                    "original_command": (
                        "python -m whisper --help | grep -qi 'usage:' && "
                        "echo 'Setup successful'"
                    ),
                    "command": "timeout 60 sh -c 'wrapped oracle command'",
                }
            ]
        }
    )

    assert description == (
        "SetupBench target validation command(s):\n"
        "- python -m whisper --help | grep -qi 'usage:' && echo 'Setup successful'"
    )


def test_build_command_passes_task_description(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    args = run_setupbench.parse_args(["--no-require-uv"])

    command = run_setupbench.build_command(
        args=args,
        runner=["python", "-m", "pheragent"],
        project_file=tmp_path / "project.txt",
        project_slug="openai-whisper",
        oracle_file=tmp_path / "oracle.json",
        task_description="SetupBench target validation command: python -m whisper --help",
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        base_dockerfile=tmp_path / "Dockerfile",
    )

    task_index = command.index("--task-description")
    assert command[task_index + 1] == (
        "SetupBench target validation command: python -m whisper --help"
    )
    jobs_index = command.index("--jobs")
    assert command[jobs_index + 1] == "1"


def test_build_command_accepts_regenerate_ablation(tmp_path: Path) -> None:
    run_setupbench = load_run_setupbench()
    args = run_setupbench.parse_args(
        ["--no-require-uv", "--ablation", "block-rollback-regenerate"]
    )

    command = run_setupbench.build_command(
        args=args,
        runner=["python", "-m", "pheragent"],
        project_file=tmp_path / "project.txt",
        project_slug="openai-whisper",
        oracle_file=tmp_path / "oracle.json",
        task_description=None,
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        base_dockerfile=tmp_path / "Dockerfile",
    )

    ablation_index = command.index("--ablation")
    assert command[ablation_index + 1] == "block-rollback-regenerate"


def test_build_command_accepts_single_command_forward_recovery_ablation(
    tmp_path: Path,
) -> None:
    run_setupbench = load_run_setupbench()
    args = run_setupbench.parse_args(
        ["--no-require-uv", "--ablation", "single-command-forward-recovery"]
    )

    command = run_setupbench.build_command(
        args=args,
        runner=["python", "-m", "pheragent"],
        project_file=tmp_path / "project.txt",
        project_slug="openai-whisper",
        oracle_file=tmp_path / "oracle.json",
        task_description=None,
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        base_dockerfile=tmp_path / "Dockerfile",
    )

    ablation_index = command.index("--ablation")
    assert command[ablation_index + 1] == "single-command-forward-recovery"


def test_run_project_retries_failed_project_and_returns_final_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_setupbench = load_run_setupbench()
    oracle = tmp_path / "oracle.json"
    oracle.write_text(json.dumps({"description": "Run oracle."}), encoding="utf-8")
    projects_root = tmp_path / "projects"
    state_root = tmp_path / "state"
    project_files_root = tmp_path / "project-files"
    logs_root = tmp_path / "logs"
    for path in (projects_root, state_root, project_files_root, logs_root):
        path.mkdir()

    calls = []

    def fake_run_command(command, *, log_path, echo):
        calls.append((command, log_path, echo))
        if len(calls) == 1:
            marker = projects_root / "owner-repo" / "first-marker"
            marker.parent.mkdir(parents=True)
            marker.write_text("stale workspace\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 1)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_setupbench, "run_command", fake_run_command)
    monkeypatch.setattr(
        run_setupbench,
        "find_manifest",
        lambda state_dir: state_dir / "repo" / "runs" / "run" / "manifest.json",
    )
    monkeypatch.setattr(
        run_setupbench,
        "read_manifest_info",
        lambda path: {
            "ok": len(calls) == 2,
            "error": None if len(calls) == 2 else "oracle validation failed",
            "final_image": "image:tag" if len(calls) == 2 else None,
            "llm_usage": {"requests": len(calls)},
        },
    )

    args = run_setupbench.parse_args(
        ["--no-require-uv", "--project-retries", "1", "--runner", "python -m pheragent"]
    )
    payload = run_setupbench.run_project(
        args=args,
        index=1,
        total=1,
        item={
            "owner_repo": "owner/repo",
            "commit_version": "abc123",
            "oracle_file": str(oracle),
        },
        runner=["python", "-m", "pheragent"],
        projects_root=projects_root,
        state_root=state_root,
        project_files_root=project_files_root,
        logs_root=logs_root,
        base_dockerfile=tmp_path / "Dockerfile",
    )

    assert len(calls) == 2
    assert calls[0][1] == logs_root / "001-owner-repo-attempt-1.log"
    assert calls[1][1] == logs_root / "001-owner-repo-attempt-2.log"
    assert not (projects_root / "owner-repo" / "first-marker").exists()
    assert payload["ok"] is True
    assert payload["attempt"] == 2
    assert payload["max_attempts"] == 2
    assert payload["attempts"] == [
        {
            "attempt": 1,
            "ok": False,
            "returncode": 1,
            "manifest_error": "oracle validation failed",
            "log_path": str(logs_root / "001-owner-repo-attempt-1.log"),
        },
        {
            "attempt": 2,
            "ok": True,
            "returncode": 0,
            "manifest_error": None,
            "log_path": str(logs_root / "001-owner-repo-attempt-2.log"),
        },
    ]
