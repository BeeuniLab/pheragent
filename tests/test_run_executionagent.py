from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def load_run_executionagent():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_executionagent.py"
    spec = importlib.util.spec_from_file_location("run_executionagent", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_command_omits_oracle_when_skip_oracle(tmp_path: Path) -> None:
    run_executionagent = load_run_executionagent()
    args = run_executionagent.parse_args(["--skip-oracle"])
    item = run_executionagent.runnable_without_oracles(
        [{"owner_repo": "owner/repo", "commit": "abc", "line_no": "1", "raw_line": ""}]
    )[0]

    command = run_executionagent.build_command(
        args=args,
        runner=["pheragent"],
        item=item,
        project_file=tmp_path / "repo.txt",
        projects_root=tmp_path / "projects",
        state_root=tmp_path / "state",
        base_dockerfile=tmp_path / "Dockerfile",
    )

    assert "--oracle-file" not in command
    assert "--oracle-timeout" not in command


def test_filter_existing_results_skips_completed_owner_repo() -> None:
    run_executionagent = load_run_executionagent()
    items = run_executionagent.runnable_without_oracles(
        [
            {"owner_repo": "owner/done", "commit": "abc", "line_no": "1", "raw_line": ""},
            {"owner_repo": "owner/todo", "commit": "def", "line_no": "2", "raw_line": ""},
        ]
    )

    runnable, skipped = run_executionagent.filter_existing_results(
        items,
        completed_owner_repos={"owner/done"},
    )

    assert [item["owner_repo"] for item in runnable] == ["owner/todo"]
    assert skipped == [
        {
            "owner_repo": "owner/done",
            "commit": "abc",
            "project_slug": "owner-done",
            "reason": "existing_result",
        }
    ]


def test_filter_existing_success_finds_nested_manifest(tmp_path: Path) -> None:
    run_executionagent = load_run_executionagent()
    manifest = tmp_path / "state" / "owner-repo" / "repo" / "runs" / "run-id" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"ok": True, "final_image": "image:tag"}) + "\n",
        encoding="utf-8",
    )
    items = run_executionagent.runnable_without_oracles(
        [{"owner_repo": "owner/repo", "commit": "abc", "line_no": "1", "raw_line": ""}]
    )

    runnable, skipped = run_executionagent.filter_existing_success(
        items,
        state_root=tmp_path / "state",
    )

    assert runnable == []
    assert skipped[0]["owner_repo"] == "owner/repo"
    assert skipped[0]["reason"] == "existing_success"
    assert skipped[0]["manifest_path"] == str(manifest)
