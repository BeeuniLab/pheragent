from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .models import BuildRequest, CommandResult
from .orchestrator import EnvironmentBuilder
from .process import run_command
from .utils import slugify

CommandRunner = Callable[[list[str], Path | None], CommandResult]
BuilderFactory = Callable[[BuildRequest], EnvironmentBuilder]


@dataclass(slots=True)
class ProjectSpec:
    owner_repo: str
    commit: str
    line_no: int
    checkout_dir_name: str

    @property
    def repo_name(self) -> str:
        return self.owner_repo.rsplit("/", 1)[-1]

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.owner_repo}.git"


@dataclass(slots=True)
class ProjectRunResult:
    project: ProjectSpec
    repo_path: Path
    ok: bool
    run_id: str | None = None
    final_image: str | None = None
    manifest_path: Path | None = None
    error: str | None = None


@dataclass(slots=True)
class BatchBuildResult:
    ok: bool
    projects_dir: Path
    results: list[ProjectRunResult]


def parse_projects_file(path: Path) -> list[ProjectSpec]:
    raw: list[tuple[str, str, int]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            raise ValueError(f"invalid projects file line {line_no}: expected 'owner/repo commit'")
        owner_repo, commit = parts[0], parts[1]
        if "/" not in owner_repo:
            raise ValueError(f"invalid projects file line {line_no}: repository must be owner/repo")
        raw.append((owner_repo, commit, line_no))

    repo_name_counts = Counter(owner_repo.rsplit("/", 1)[-1] for owner_repo, _, _ in raw)
    specs: list[ProjectSpec] = []
    for owner_repo, commit, line_no in raw:
        repo_name = owner_repo.rsplit("/", 1)[-1]
        checkout_dir_name = repo_name
        if repo_name_counts[repo_name] > 1:
            checkout_dir_name = slugify(owner_repo)
        specs.append(
            ProjectSpec(
                owner_repo=owner_repo,
                commit=commit,
                line_no=line_no,
                checkout_dir_name=checkout_dir_name,
            )
        )
    return specs


def prepare_project(
    spec: ProjectSpec,
    *,
    projects_dir: Path,
    clone_timeout: float,
    command_runner: CommandRunner | None = None,
) -> Path:
    runner = command_runner or (
        lambda command, cwd=None: run_command(command, timeout=clone_timeout, cwd=cwd)
    )
    projects_dir.mkdir(parents=True, exist_ok=True)
    repo_path = projects_dir / spec.checkout_dir_name

    if not repo_path.exists():
        _run_or_raise(
            runner,
            [
                "git",
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                spec.repo_url,
                str(repo_path),
            ],
            f"clone failed for {spec.owner_repo}",
            cwd=None,
        )
    elif not (repo_path / ".git").exists():
        raise RuntimeError(f"project path exists but is not a git repository: {repo_path}")
    else:
        _run_or_raise(
            runner,
            ["git", "remote", "set-url", "origin", spec.repo_url],
            f"failed to update remote for {spec.owner_repo}",
            cwd=repo_path,
        )

    fetch_result = runner(["git", "fetch", "--depth", "1", "origin", spec.commit], repo_path)
    if not fetch_result.ok:
        fetch_result = runner(["git", "fetch", "origin", spec.commit], repo_path)
    if not fetch_result.ok:
        raise RuntimeError(
            f"fetch failed for {spec.owner_repo}@{spec.commit}: "
            f"{fetch_result.combined_output}"
        )

    _run_or_raise(
        runner,
        ["git", "checkout", "--detach", spec.commit],
        f"checkout failed for {spec.owner_repo}@{spec.commit}",
        cwd=repo_path,
    )
    return repo_path


class ProjectBatchBuilder:
    def __init__(
        self,
        *,
        projects_file: Path,
        projects_dir: Path,
        base_request: BuildRequest,
        clone_timeout: float = 900.0,
        run_id_prefix: str | None = None,
        limit: int | None = None,
        stop_on_failure: bool = False,
        command_runner: CommandRunner | None = None,
        builder_factory: BuilderFactory = EnvironmentBuilder,
    ):
        self.projects_file = projects_file.expanduser().resolve()
        self.projects_dir = projects_dir.expanduser().resolve()
        self.base_request = base_request
        self.clone_timeout = clone_timeout
        self.run_id_prefix = run_id_prefix
        self.limit = limit
        self.stop_on_failure = stop_on_failure
        self.command_runner = command_runner
        self.builder_factory = builder_factory

    def build_all(self) -> BatchBuildResult:
        specs = parse_projects_file(self.projects_file)
        if self.limit is not None:
            specs = specs[: self.limit]

        results: list[ProjectRunResult] = []
        for spec in specs:
            repo_path = self.projects_dir / spec.checkout_dir_name
            try:
                repo_path = prepare_project(
                    spec,
                    projects_dir=self.projects_dir,
                    clone_timeout=self.clone_timeout,
                    command_runner=self.command_runner,
                )
                build_result = self.builder_factory(self._request_for(spec, repo_path)).build()
                result = ProjectRunResult(
                    project=spec,
                    repo_path=repo_path,
                    ok=build_result.ok,
                    run_id=build_result.run_id,
                    final_image=build_result.final_image,
                    manifest_path=build_result.manifest_path,
                    error=build_result.error,
                )
            except Exception as exc:
                result = ProjectRunResult(
                    project=spec,
                    repo_path=repo_path,
                    ok=False,
                    error=str(exc),
                )
            results.append(result)
            if self.stop_on_failure and not result.ok:
                break

        return BatchBuildResult(
            ok=all(result.ok for result in results),
            projects_dir=self.projects_dir,
            results=results,
        )

    def _request_for(self, spec: ProjectSpec, repo_path: Path) -> BuildRequest:
        run_id = None
        if self.run_id_prefix:
            run_id = f"{slugify(self.run_id_prefix)}-{slugify(spec.checkout_dir_name)}"

        state_dir = self.base_request.state_dir
        if state_dir is not None:
            state_dir = state_dir / spec.checkout_dir_name

        return BuildRequest(
            repo_path=repo_path,
            base_dockerfile=self.base_request.base_dockerfile,
            state_dir=state_dir,
            run_id=run_id,
            container_workdir=self.base_request.container_workdir,
            image_prefix=self.base_request.image_prefix,
            max_repair_attempts=self.base_request.max_repair_attempts,
            command_timeout=self.base_request.command_timeout,
            docker_build_timeout=self.base_request.docker_build_timeout,
            keep_container=self.base_request.keep_container,
            cleanup_images=self.base_request.cleanup_images,
            planner_mode=self.base_request.planner_mode,
            llm_model=self.base_request.llm_model,
            openai_base_url=self.base_request.openai_base_url,
            openai_api_key_env=self.base_request.openai_api_key_env,
            openai_base_url_env=self.base_request.openai_base_url_env,
            llm_timeout=self.base_request.llm_timeout,
            llm_max_tokens=self.base_request.llm_max_tokens,
            llm_retries=self.base_request.llm_retries,
            llm_retry_delay=self.base_request.llm_retry_delay,
            oracle_file=self.base_request.oracle_file,
            oracle_timeout=self.base_request.oracle_timeout,
            resume_from=self.base_request.resume_from,
            start_at_block=self.base_request.start_at_block,
        )


def _run_or_raise(
    runner: CommandRunner,
    command: list[str],
    message: str,
    *,
    cwd: Path | None,
) -> None:
    result = runner(command, cwd)
    if not result.ok:
        raise RuntimeError(f"{message}: {result.combined_output}")
