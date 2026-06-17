from __future__ import annotations

import json
from pathlib import Path

from pheragent.models import BuildRequest, BuildResult, CommandResult
from pheragent.project_batch import (
    ProjectBatchBuilder,
    ProjectSpec,
    isolate_project_oracles,
    parse_projects_file,
    prepare_project,
)


def test_parse_projects_file_uses_repo_name_unless_duplicate(tmp_path: Path) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text(
        "\n".join(
            [
                "# comment",
                "pallets/flask 1111111",
                "example/flask 2222222",
                "numpy/numpy 3333333",
            ]
        ),
        encoding="utf-8",
    )

    specs = parse_projects_file(projects_file)

    assert [spec.checkout_dir_name for spec in specs] == [
        "pallets-flask",
        "example-flask",
        "numpy",
    ]
    assert specs[0].line_no == 2


def test_prepare_project_clones_fetches_and_checks_out_in_repo_dir(tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    spec = ProjectSpec(
        owner_repo="pallets/flask",
        commit="2579ce9",
        line_no=1,
        checkout_dir_name="flask",
    )
    calls: list[tuple[list[str], Path | None]] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        calls.append((command, cwd))
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
        return CommandResult(exit_code=0, stdout="ok")

    prepared_project = prepare_project(
        spec,
        projects_dir=projects_dir,
        clone_timeout=30,
        command_runner=fake_runner,
    )
    repo_path = prepared_project.repo_path

    assert repo_path == projects_dir / "flask"
    assert not prepared_project.version_mismatch
    assert calls[0][0][:2] == ["git", "clone"]
    assert calls[0][1] is None
    assert calls[1] == (["git", "fetch", "--depth", "1", "origin", "2579ce9"], repo_path)
    assert calls[2] == (["git", "checkout", "--detach", "2579ce9"], repo_path)


def test_prepare_project_resolves_short_hash_after_ref_fetch_fails(tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    full_hash = "9ba7b8" + ("0" * 34)
    spec = ProjectSpec(
        owner_repo="271374667/VideoFusion",
        commit="9ba7b8",
        line_no=1,
        checkout_dir_name="VideoFusion",
    )
    calls: list[tuple[list[str], Path | None]] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        calls.append((command, cwd))
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
            return CommandResult(exit_code=0, stdout="ok")
        if command == ["git", "fetch", "--depth", "1", "origin", "9ba7b8"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref 9ba7b8")
        if command == ["git", "fetch", "origin", "9ba7b8"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref 9ba7b8")
        if command[:3] == ["git", "fetch", "--filter=blob:none"]:
            return CommandResult(exit_code=0, stdout="refs fetched")
        if command[:3] == ["git", "rev-parse", "--verify"]:
            return CommandResult(exit_code=0, stdout=f"{full_hash}\n")
        return CommandResult(exit_code=0, stdout="ok")

    prepared_project = prepare_project(
        spec,
        projects_dir=projects_dir,
        clone_timeout=30,
        command_runner=fake_runner,
    )
    repo_path = prepared_project.repo_path

    assert repo_path == projects_dir / "VideoFusion"
    assert not prepared_project.version_mismatch
    assert (
        [
            "git",
            "fetch",
            "--filter=blob:none",
            "origin",
            "+refs/heads/*:refs/remotes/origin/*",
            "+refs/tags/*:refs/tags/*",
        ],
        repo_path,
    ) in calls
    assert (["git", "checkout", "--detach", full_hash], repo_path) in calls


def test_prepare_project_falls_back_to_default_head_when_requested_ref_is_missing(
    tmp_path: Path,
) -> None:
    projects_dir = tmp_path / "projects"
    actual_hash = "a" * 40
    spec = ProjectSpec(
        owner_repo="example/repo",
        commit="missingref",
        line_no=1,
        checkout_dir_name="repo",
    )
    calls: list[tuple[list[str], Path | None]] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        calls.append((command, cwd))
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
            return CommandResult(exit_code=0, stdout="ok")
        if command == ["git", "fetch", "--depth", "1", "origin", "missingref"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref")
        if command == ["git", "fetch", "origin", "missingref"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref")
        if command == ["git", "fetch", "--depth", "1", "origin", "HEAD"]:
            return CommandResult(exit_code=0, stdout="default fetched")
        if command == ["git", "rev-parse", "--verify", "HEAD"]:
            return CommandResult(exit_code=0, stdout=f"{actual_hash}\n")
        return CommandResult(exit_code=0, stdout="ok")

    prepared_project = prepare_project(
        spec,
        projects_dir=projects_dir,
        clone_timeout=30,
        command_runner=fake_runner,
    )
    repo_path = projects_dir / "repo"

    assert prepared_project.repo_path == repo_path
    assert prepared_project.version_mismatch
    assert prepared_project.actual_commit == actual_hash
    assert (["git", "fetch", "--depth", "1", "origin", "HEAD"], repo_path) in calls
    assert (["git", "checkout", "--detach", "FETCH_HEAD"], repo_path) in calls


def test_isolate_project_oracles_moves_github_out_of_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "projects" / "flask"
    github_dir = repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True)
    (github_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    spec = ProjectSpec(
        owner_repo="pallets/flask",
        commit="2579ce9",
        line_no=1,
        checkout_dir_name="flask",
    )

    oracle_path = isolate_project_oracles(
        spec,
        repo_path=repo_path,
        oracles_dir=tmp_path / "oracles",
    )

    assert oracle_path == tmp_path / "oracles" / "flask" / ".github"
    assert not (repo_path / ".github").exists()
    assert (oracle_path / "workflows" / "ci.yml").read_text(encoding="utf-8") == "name: ci\n"


def test_project_batch_builder_builds_each_prepared_project(tmp_path: Path) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")
    requests: list[BuildRequest] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
        if command[:2] == ["git", "checkout"] and cwd is not None:
            github_dir = cwd / ".github" / "workflows"
            github_dir.mkdir(parents=True)
            (github_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request
            requests.append(request)

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-final",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        oracles_dir=tmp_path / "oracles",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
            task_description="Setup target: run flask import smoke test.",
            llm_api="chat-completions",
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert requests[0].repo_path == tmp_path / "projects" / "flask"
    assert requests[0].task_description == "Setup target: run flask import smoke test."
    assert not (requests[0].repo_path / ".github").exists()
    assert requests[0].run_id == "batch-flask"
    assert requests[0].llm_api == "chat-completions"
    assert result.results[0].final_image == "pheragent:batch-flask-final"
    assert result.results[0].oracle_path == tmp_path / "oracles" / "flask" / ".github"
    assert (result.results[0].oracle_path / "workflows" / "ci.yml").is_file()


def test_project_batch_builder_keeps_github_when_oracles_dir_is_not_set(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")
    requests: list[BuildRequest] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
        if command[:2] == ["git", "checkout"] and cwd is not None:
            github_dir = cwd / ".github" / "workflows"
            github_dir.mkdir(parents=True)
            (github_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request
            requests.append(request)

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-final",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert result.oracles_dir is None
    assert result.results[0].oracle_path is None
    assert (requests[0].repo_path / ".github" / "workflows" / "ci.yml").is_file()
    assert not (tmp_path / "oracles").exists()


def test_project_batch_builder_skips_existing_successful_project(tmp_path: Path) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")
    repo_path = tmp_path / "projects" / "flask"
    repo_path.mkdir(parents=True)
    github_dir = repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True)
    (github_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    run_dir = repo_path / ".pheragent" / "runs" / "batch-flask"
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "ok": True,
                "run_id": "batch-flask",
                "final_image": "pheragent:batch-flask-final",
            }
        ),
        encoding="utf-8",
    )
    runner_calls: list[list[str]] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        del cwd
        runner_calls.append(command)
        return CommandResult(exit_code=0, stdout="unexpected")

    class UnexpectedBuilder:
        def __init__(self, request: BuildRequest):
            del request
            raise AssertionError("builder should not be created for successful existing run")

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        oracles_dir=tmp_path / "oracles",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=UnexpectedBuilder,
    ).build_all()

    assert result.ok
    assert runner_calls == []
    assert result.results[0].ok
    assert result.results[0].run_id == "batch-flask"
    assert result.results[0].final_image == "pheragent:batch-flask-final"
    assert result.results[0].manifest_path == manifest_path
    assert result.results[0].oracle_path == tmp_path / "oracles" / "flask" / ".github"
    assert not (repo_path / ".github").exists()


def test_project_batch_builder_keeps_github_for_existing_success_without_oracles_dir(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")
    repo_path = tmp_path / "projects" / "flask"
    github_dir = repo_path / ".github" / "workflows"
    github_dir.mkdir(parents=True)
    (github_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    run_dir = repo_path / ".pheragent" / "runs" / "batch-flask"
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "ok": True,
                "run_id": "batch-flask",
                "final_image": "pheragent:batch-flask-final",
            }
        ),
        encoding="utf-8",
    )

    class UnexpectedBuilder:
        def __init__(self, request: BuildRequest):
            del request
            raise AssertionError("builder should not be created for successful existing run")

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        builder_factory=UnexpectedBuilder,
    ).build_all()

    assert result.ok
    assert result.oracles_dir is None
    assert result.results[0].manifest_path == manifest_path
    assert result.results[0].oracle_path is None
    assert (repo_path / ".github" / "workflows" / "ci.yml").is_file()


def test_project_batch_builder_reruns_existing_failed_project_and_clears_failure_log(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")
    projects_dir = tmp_path / "projects"
    repo_path = projects_dir / "flask"
    (repo_path / ".git").mkdir(parents=True)
    run_dir = repo_path / ".pheragent" / "runs" / "batch-flask"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps({"ok": False, "run_id": "batch-flask", "error": "old failure"}),
        encoding="utf-8",
    )
    stale_failure_log = projects_dir / "failed-projects.log"
    stale_failure_log.write_text("old\tfailure\n", encoding="utf-8")
    requests: list[BuildRequest] = []
    clone_calls = 0

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        nonlocal clone_calls
        del cwd
        if command[:2] == ["git", "clone"]:
            clone_calls += 1
            cloned_repo_path = Path(command[-1])
            assert not cloned_repo_path.exists()
            (cloned_repo_path / ".git").mkdir(parents=True)
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request
            requests.append(request)

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-rebuilt",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=projects_dir,
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert clone_calls == 1
    assert requests
    assert requests[0].repo_path == repo_path
    assert result.results[0].final_image == "pheragent:batch-flask-rebuilt"
    assert result.failures_log_path is None
    assert not stale_failure_log.exists()


def test_project_batch_builder_resets_unrecognized_existing_project_state(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")
    projects_dir = tmp_path / "projects"
    repo_path = projects_dir / "flask"
    run_dir = repo_path / ".pheragent" / "runs" / "batch-flask"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{not-json", encoding="utf-8")
    (repo_path / "stale.log").write_text("old log\n", encoding="utf-8")
    clone_calls = 0

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        nonlocal clone_calls
        del cwd
        if command[:2] == ["git", "clone"]:
            clone_calls += 1
            cloned_repo_path = Path(command[-1])
            assert not cloned_repo_path.exists()
            (cloned_repo_path / ".git").mkdir(parents=True)
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-rebuilt",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=projects_dir,
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert clone_calls == 1
    assert not (repo_path / "stale.log").exists()
    assert result.results[0].final_image == "pheragent:batch-flask-rebuilt"


def test_project_batch_builder_writes_no_repo_log_for_unavailable_projects(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("example/missing missingref\n", encoding="utf-8")

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        del cwd
        if command[:2] == ["git", "clone"]:
            return CommandResult(exit_code=128, stderr="fatal: repository not found")
        return CommandResult(exit_code=0, stdout="unexpected")

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        command_runner=fake_runner,
    ).build_all()

    assert result.ok
    assert result.failures_log_path is None
    assert result.no_repo_log_path == tmp_path / "projects" / "no-repo-projects.log"
    assert result.results[0].skipped
    assert result.results[0].failure_stage == "unavailable_project"
    no_repo_log = result.no_repo_log_path.read_text(encoding="utf-8")
    assert "example/missing" in no_repo_log
    assert "missingref" in no_repo_log
    assert "unavailable_project" in no_repo_log
    assert "fatal: couldn't find remote ref" not in no_repo_log


def test_project_batch_builder_skips_projects_recorded_in_no_repo_log(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text(
        "example/missing missingref\npallets/flask 2579ce9\n",
        encoding="utf-8",
    )
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    no_repo_log_path = projects_dir / "no-repo-projects.log"
    no_repo_log_path.write_text(
        "\t".join(
            [
                "example/missing",
                "missingref",
                "missing",
                str(projects_dir / "missing"),
                "unavailable_project",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    built_repos: list[Path] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        del cwd
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            assert repo_path.name != "missing"
            (repo_path / ".git").mkdir(parents=True)
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request

        def build(self) -> BuildResult:
            built_repos.append(self.request.repo_path)
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-final",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=projects_dir,
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        stop_on_failure=True,
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert [project_result.skipped for project_result in result.results] == [True, False]
    assert built_repos == [projects_dir / "flask"]
    assert no_repo_log_path.read_text(encoding="utf-8").count("example/missing") == 1


def test_project_batch_builder_logs_version_mismatch_and_builds_default_checkout(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("example/repo missingref\n", encoding="utf-8")
    actual_hash = "b" * 40
    requests: list[BuildRequest] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
            return CommandResult(exit_code=0, stdout="ok")
        if command == ["git", "fetch", "--depth", "1", "origin", "missingref"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref")
        if command == ["git", "fetch", "origin", "missingref"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref")
        if command == ["git", "fetch", "--depth", "1", "origin", "HEAD"]:
            return CommandResult(exit_code=0, stdout="default fetched")
        if command == ["git", "rev-parse", "--verify", "HEAD"]:
            return CommandResult(exit_code=0, stdout=f"{actual_hash}\n")
        if command == ["git", "checkout", "--detach", "FETCH_HEAD"] and cwd is not None:
            github_dir = cwd / ".github" / "workflows"
            github_dir.mkdir(parents=True)
            (github_dir / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request
            requests.append(request)

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-repo"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-repo",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-repo-final",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        oracles_dir=tmp_path / "oracles",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert result.no_repo_log_path is None
    assert result.version_mismatch_log_path == (
        tmp_path / "projects" / "version-mismatch-projects.log"
    )
    assert result.results[0].ok
    assert not result.results[0].skipped
    assert result.results[0].version_mismatch
    assert result.results[0].actual_commit == actual_hash
    assert requests[0].repo_path == tmp_path / "projects" / "repo"
    mismatch_log = result.version_mismatch_log_path.read_text(encoding="utf-8")
    assert "example/repo" in mismatch_log
    assert "missingref" in mismatch_log
    assert actual_hash in mismatch_log


def test_project_batch_builder_preserves_and_updates_version_mismatch_log(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("example/repo missingref\n", encoding="utf-8")
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    old_hash = "c" * 40
    actual_hash = "d" * 40
    version_mismatch_log_path = projects_dir / "version-mismatch-projects.log"
    version_mismatch_log_path.write_text(
        "\n".join(
            [
                "\t".join(
                    [
                        "example/repo",
                        "missingref",
                        old_hash,
                        "repo",
                        str(projects_dir / "repo"),
                    ]
                ),
                "\t".join(
                    [
                        "other/repo",
                        "oldref",
                        "e" * 40,
                        "other",
                        str(projects_dir / "other"),
                    ]
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
            return CommandResult(exit_code=0, stdout="ok")
        if command == ["git", "fetch", "--depth", "1", "origin", "missingref"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref")
        if command == ["git", "fetch", "origin", "missingref"]:
            return CommandResult(exit_code=128, stderr="fatal: couldn't find remote ref")
        if command == ["git", "fetch", "--depth", "1", "origin", "HEAD"]:
            return CommandResult(exit_code=0, stdout="default fetched")
        if command == ["git", "rev-parse", "--verify", "HEAD"]:
            return CommandResult(exit_code=0, stdout=f"{actual_hash}\n")
        del cwd
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-repo"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-repo",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-repo-final",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=projects_dir,
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    mismatch_log = version_mismatch_log_path.read_text(encoding="utf-8")
    assert old_hash not in mismatch_log
    assert actual_hash in mismatch_log
    assert mismatch_log.count("example/repo") == 1
    assert "other/repo" in mismatch_log


def test_project_batch_builder_continues_after_unavailable_project_with_stop_on_failure(
    tmp_path: Path,
) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text(
        "example/missing missingref\npallets/flask 2579ce9\n",
        encoding="utf-8",
    )
    built_repos: list[Path] = []

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            if repo_path.name == "missing":
                return CommandResult(exit_code=128, stderr="fatal: repository not found")
            (repo_path / ".git").mkdir(parents=True)
            return CommandResult(exit_code=0, stdout="ok")
        return CommandResult(exit_code=0, stdout="ok")

    class FakeBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request

        def build(self) -> BuildResult:
            built_repos.append(self.request.repo_path)
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-final",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        stop_on_failure=True,
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert [project_result.skipped for project_result in result.results] == [True, False]
    assert built_repos == [tmp_path / "projects" / "flask"]
    assert result.no_repo_log_path is not None
    assert result.failures_log_path is None


def test_project_batch_builder_logs_build_failures_concisely(tmp_path: Path) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
        return CommandResult(exit_code=0, stdout="ok")

    class FailingBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=False,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                error="block failed: 20-python-deps",
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        command_runner=fake_runner,
        builder_factory=FailingBuilder,
    ).build_all()

    assert not result.ok
    assert result.results[0].failure_stage == "build_failed"
    failure_log = result.failures_log_path.read_text(encoding="utf-8")
    assert "pallets/flask" in failure_log
    assert "build_failed" in failure_log
    assert "20-python-deps" not in failure_log


def test_project_batch_builder_writes_llm_usage_jsonl(tmp_path: Path) -> None:
    projects_file = tmp_path / "projects.txt"
    projects_file.write_text("pallets/flask 2579ce9\n", encoding="utf-8")

    def fake_runner(command: list[str], cwd: Path | None) -> CommandResult:
        del cwd
        if command[:2] == ["git", "clone"]:
            repo_path = Path(command[-1])
            (repo_path / ".git").mkdir(parents=True)
        return CommandResult(exit_code=0, stdout="ok")

    class UsageBuilder:
        def __init__(self, request: BuildRequest):
            self.request = request

        def build(self) -> BuildResult:
            state_dir = self.request.repo_path / ".pheragent" / "runs" / "batch-flask"
            return BuildResult(
                ok=True,
                run_id=self.request.run_id or "batch-flask",
                state_dir=state_dir,
                scripts_dir=state_dir / "scripts",
                manifest_path=state_dir / "manifest.json",
                final_image="pheragent:batch-flask-final",
                llm_usage={
                    "planner": {
                        "requests": 1,
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "reasoning_tokens": 2,
                        "total_tokens": 15,
                    },
                    "total": {
                        "requests": 1,
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "reasoning_tokens": 2,
                        "total_tokens": 15,
                    },
                },
            )

    result = ProjectBatchBuilder(
        projects_file=projects_file,
        projects_dir=tmp_path / "projects",
        base_request=BuildRequest(
            repo_path=tmp_path,
            base_dockerfile=tmp_path / "Dockerfile",
            run_id=None,
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=UsageBuilder,
    ).build_all()

    assert result.ok
    assert result.llm_usage_log_path == tmp_path / "projects" / "llm-usage-projects.jsonl"
    expected_manifest_path = (
        tmp_path / "projects" / "flask" / ".pheragent" / "runs" / "batch-flask" / "manifest.json"
    )
    records = [
        json.loads(line)
        for line in result.llm_usage_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert records == [
        {
            "owner_repo": "pallets/flask",
            "commit": "2579ce9",
            "checkout_dir_name": "flask",
            "repo_path": str(tmp_path / "projects" / "flask"),
            "ok": True,
            "skipped": False,
            "version_mismatch": False,
            "actual_commit": "ok",
            "run_id": "batch-flask",
            "final_image": "pheragent:batch-flask-final",
            "manifest_path": str(expected_manifest_path),
            "oracle_path": None,
            "failure_stage": None,
            "error": None,
            "requests": 1,
            "input_tokens": 10,
            "output_tokens": 5,
            "reasoning_tokens": 2,
            "total_tokens": 15,
            "llm_usage": {
                "planner": {
                    "requests": 1,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "reasoning_tokens": 2,
                    "total_tokens": 15,
                },
                "total": {
                    "requests": 1,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "reasoning_tokens": 2,
                    "total_tokens": 15,
                },
            },
        }
    ]
