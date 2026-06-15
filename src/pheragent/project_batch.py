from __future__ import annotations

import json
import shutil
import sys
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
    oracle_path: Path | None = None
    failure_stage: str | None = None
    error: str | None = None


@dataclass(slots=True)
class BatchBuildResult:
    ok: bool
    projects_dir: Path
    oracles_dir: Path
    results: list[ProjectRunResult]
    failures_log_path: Path | None = None


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
    stream_logs: bool = False,
    command_runner: CommandRunner | None = None,
) -> Path:
    runner = command_runner or (
        lambda command, cwd=None: run_command(
            command,
            timeout=clone_timeout,
            cwd=cwd,
            stream_output=stream_logs,
        )
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

    checkout_ref, fetch_result = _fetch_checkout_ref(spec, repo_path=repo_path, runner=runner)
    if checkout_ref is None:
        raise RuntimeError(
            f"fetch failed for {spec.owner_repo}@{spec.commit}: "
            f"{fetch_result.combined_output}"
        )

    _run_or_raise(
        runner,
        ["git", "checkout", "--detach", checkout_ref],
        f"checkout failed for {spec.owner_repo}@{checkout_ref}",
        cwd=repo_path,
    )
    return repo_path


def _fetch_checkout_ref(
    spec: ProjectSpec,
    *,
    repo_path: Path,
    runner: CommandRunner,
) -> tuple[str | None, CommandResult]:
    fetch_result = runner(["git", "fetch", "--depth", "1", "origin", spec.commit], repo_path)
    if fetch_result.ok:
        return spec.commit, fetch_result

    direct_fetch_result = runner(["git", "fetch", "origin", spec.commit], repo_path)
    if direct_fetch_result.ok:
        return spec.commit, direct_fetch_result

    if not _looks_like_short_sha(spec.commit):
        return None, direct_fetch_result

    refs_fetch_result = runner(
        [
            "git",
            "fetch",
            "--filter=blob:none",
            "origin",
            "+refs/heads/*:refs/remotes/origin/*",
            "+refs/tags/*:refs/tags/*",
        ],
        repo_path,
    )
    if not refs_fetch_result.ok:
        return None, refs_fetch_result

    resolve_result = runner(
        ["git", "rev-parse", "--verify", "--quiet", f"{spec.commit}^{{commit}}"],
        repo_path,
    )
    if resolve_result.ok and resolve_result.stdout.strip():
        return resolve_result.stdout.strip().splitlines()[0], resolve_result

    return None, CommandResult(
        exit_code=1,
        stdout=refs_fetch_result.stdout,
        stderr=(
            f"could not resolve short commit {spec.commit!r} after fetching remote refs\n"
            f"{resolve_result.combined_output}"
        ).strip(),
        command=resolve_result.command,
    )


def _looks_like_short_sha(value: str) -> bool:
    return 4 <= len(value) < 40 and all(char in "0123456789abcdefABCDEF" for char in value)


def isolate_project_oracles(
    spec: ProjectSpec,
    *,
    repo_path: Path,
    oracles_dir: Path,
) -> Path | None:
    source = repo_path / ".github"
    destination = oracles_dir / spec.checkout_dir_name / ".github"
    if not source.exists():
        return destination if destination.exists() else None

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.move(str(source), str(destination))
    return destination


class ProjectBatchBuilder:
    def __init__(
        self,
        *,
        projects_file: Path,
        projects_dir: Path,
        oracles_dir: Path = Path("oracles"),
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
        self.oracles_dir = oracles_dir.expanduser().resolve()
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

        failures_log_path = self.projects_dir / "failed-projects.log"
        if failures_log_path.exists():
            failures_log_path.unlink()

        results: list[ProjectRunResult] = []
        for spec in specs:
            repo_path = self.projects_dir / spec.checkout_dir_name
            oracle_path: Path | None = None
            failure_stage = "prepare_failed"
            try:
                existing_result = self._existing_successful_result(spec, repo_path)
                if existing_result is not None:
                    self._emit(
                        f"project {spec.owner_repo}: skip existing successful run "
                        f"{existing_result.run_id}"
                    )
                    results.append(existing_result)
                    continue

                self._emit(f"project {spec.owner_repo}@{spec.commit}: prepare")
                repo_path = prepare_project(
                    spec,
                    projects_dir=self.projects_dir,
                    clone_timeout=self.clone_timeout,
                    stream_logs=self.base_request.stream_logs,
                    command_runner=self.command_runner,
                )
                oracle_path = isolate_project_oracles(
                    spec,
                    repo_path=repo_path,
                    oracles_dir=self.oracles_dir,
                )
                if oracle_path is not None:
                    self._emit(f"project {spec.owner_repo}: isolated oracle data at {oracle_path}")
                self._emit(f"project {spec.owner_repo}: build")
                failure_stage = "build_failed"
                build_result = self.builder_factory(self._request_for(spec, repo_path)).build()
                result = ProjectRunResult(
                    project=spec,
                    repo_path=repo_path,
                    ok=build_result.ok,
                    run_id=build_result.run_id,
                    final_image=build_result.final_image,
                    manifest_path=build_result.manifest_path,
                    oracle_path=oracle_path,
                    failure_stage=None if build_result.ok else failure_stage,
                    error=build_result.error,
                )
            except Exception as exc:
                result = ProjectRunResult(
                    project=spec,
                    repo_path=repo_path,
                    ok=False,
                    oracle_path=oracle_path,
                    failure_stage=failure_stage,
                    error=str(exc),
                )
            results.append(result)
            if not result.ok:
                self._append_failure_log(result, failures_log_path)
            self._emit(f"project {spec.owner_repo}: {'ok' if result.ok else 'failed'}")
            if self.stop_on_failure and not result.ok:
                break

        return BatchBuildResult(
            ok=all(result.ok for result in results),
            projects_dir=self.projects_dir,
            oracles_dir=self.oracles_dir,
            results=results,
            failures_log_path=failures_log_path if failures_log_path.exists() else None,
        )

    def _request_for(self, spec: ProjectSpec, repo_path: Path) -> BuildRequest:
        run_id = self._run_id_for(spec)

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
            max_probe_failures=self.base_request.max_probe_failures,
            command_timeout=self.base_request.command_timeout,
            docker_build_timeout=self.base_request.docker_build_timeout,
            keep_container=self.base_request.keep_container,
            cleanup_images=self.base_request.cleanup_images,
            stream_logs=self.base_request.stream_logs,
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

    def _emit(self, message: str) -> None:
        if self.base_request.stream_logs:
            print(f"[pheragent] {message}", file=sys.stderr, flush=True)

    def _existing_successful_result(
        self,
        spec: ProjectSpec,
        repo_path: Path,
    ) -> ProjectRunResult | None:
        if not repo_path.exists():
            return None
        manifest_path = self._expected_manifest_path(spec, repo_path)
        if manifest_path is None or not manifest_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        final_image = manifest.get("final_image")
        if manifest.get("ok") is not True or not isinstance(final_image, str) or not final_image:
            return None
        oracle_path = isolate_project_oracles(
            spec,
            repo_path=repo_path,
            oracles_dir=self.oracles_dir,
        )
        return ProjectRunResult(
            project=spec,
            repo_path=repo_path,
            ok=True,
            run_id=str(manifest.get("run_id") or self._run_id_for(spec)),
            final_image=final_image,
            manifest_path=manifest_path,
            oracle_path=oracle_path,
        )

    def _expected_manifest_path(self, spec: ProjectSpec, repo_path: Path) -> Path | None:
        run_id = self._run_id_for(spec)
        if run_id is None:
            return None
        state_dir = self.base_request.state_dir
        if state_dir is not None:
            state_dir = state_dir.expanduser().resolve() / spec.checkout_dir_name
        else:
            state_dir = repo_path / ".pheragent"
        return state_dir / "runs" / run_id / "manifest.json"

    def _run_id_for(self, spec: ProjectSpec) -> str | None:
        if not self.run_id_prefix:
            return None
        return f"{slugify(self.run_id_prefix)}-{slugify(spec.checkout_dir_name)}"

    def _append_failure_log(self, result: ProjectRunResult, failures_log_path: Path) -> None:
        failures_log_path.parent.mkdir(parents=True, exist_ok=True)
        with failures_log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\t".join(
                    [
                        result.project.owner_repo,
                        result.project.commit,
                        result.project.checkout_dir_name,
                        str(result.repo_path),
                        result.failure_stage or "failed",
                    ]
                )
                + "\n"
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
