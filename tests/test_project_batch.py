from __future__ import annotations

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

    repo_path = prepare_project(
        spec,
        projects_dir=projects_dir,
        clone_timeout=30,
        command_runner=fake_runner,
    )

    assert repo_path == projects_dir / "flask"
    assert calls[0][0][:2] == ["git", "clone"]
    assert calls[0][1] is None
    assert calls[1] == (["git", "fetch", "--depth", "1", "origin", "2579ce9"], repo_path)
    assert calls[2] == (["git", "checkout", "--detach", "2579ce9"], repo_path)


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
        ),
        run_id_prefix="batch",
        command_runner=fake_runner,
        builder_factory=FakeBuilder,
    ).build_all()

    assert result.ok
    assert requests[0].repo_path == tmp_path / "projects" / "flask"
    assert not (requests[0].repo_path / ".github").exists()
    assert requests[0].run_id == "batch-flask"
    assert result.results[0].final_image == "pheragent:batch-flask-final"
    assert result.results[0].oracle_path == tmp_path / "oracles" / "flask" / ".github"
    assert (result.results[0].oracle_path / "workflows" / "ci.yml").is_file()
