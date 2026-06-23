from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import sys
from collections import Counter
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    DEFAULT_ABLATION_MODE,
    BuildRequest,
    CommandResult,
    progress_control_for_ablation,
    to_jsonable,
)
from .orchestrator import EnvironmentBuilder
from .process import run_command
from .utils import slugify

CommandRunner = Callable[[list[str], Path | None], CommandResult]
BuilderFactory = Callable[[BuildRequest], EnvironmentBuilder]
ProjectLogKey = tuple[str, str, str]
LEGACY_MANIFEST_ABLATION_MODE = "without-final-clean-replay"


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
    skipped: bool = False
    version_mismatch: bool = False
    run_id: str | None = None
    final_image: str | None = None
    manifest_path: Path | None = None
    oracle_path: Path | None = None
    actual_commit: str | None = None
    failure_stage: str | None = None
    error: str | None = None
    llm_usage: dict[str, dict[str, int]] = field(default_factory=dict)
    ablation_mode: str = DEFAULT_ABLATION_MODE
    progress_control: dict[str, object] | None = None
    final_clean_replay_enabled: bool = False
    final_clean_replay_ok: bool | None = None
    final_clean_replay_image: str | None = None
    final_clean_replay_failure_stage: str | None = None


@dataclass(slots=True)
class BatchBuildResult:
    ok: bool
    projects_dir: Path
    oracles_dir: Path | None
    results: list[ProjectRunResult]
    failures_log_path: Path | None = None
    no_repo_log_path: Path | None = None
    version_mismatch_log_path: Path | None = None
    llm_usage_log_path: Path | None = None
    ablation_mode: str = DEFAULT_ABLATION_MODE
    progress_control: dict[str, object] | None = None


@dataclass(slots=True)
class PreparedProject:
    repo_path: Path
    requested_commit: str
    checkout_ref: str
    actual_commit: str | None = None
    version_mismatch: bool = False


@contextlib.contextmanager
def _project_dir_lock(projects_dir: Path):
    projects_dir.mkdir(parents=True, exist_ok=True)
    lock_path = projects_dir / ".pheragent-build.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"another pheragent build-projects process is already using {projects_dir}"
            ) from exc
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
    used_checkout_dir_names: set[str] = set()
    for owner_repo, commit, line_no in raw:
        repo_name = owner_repo.rsplit("/", 1)[-1]
        base_checkout_dir_name = repo_name
        if repo_name_counts[repo_name] > 1:
            base_checkout_dir_name = slugify(owner_repo)
        checkout_dir_name = base_checkout_dir_name
        suffix = 2
        while checkout_dir_name in used_checkout_dir_names:
            checkout_dir_name = f"{base_checkout_dir_name}-{suffix}"
            suffix += 1
        used_checkout_dir_names.add(checkout_dir_name)
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
) -> PreparedProject:
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
    version_mismatch = False
    if checkout_ref is None:
        checkout_ref, fallback_result = _fetch_default_head(repo_path=repo_path, runner=runner)
        if checkout_ref is None:
            raise RuntimeError(
                f"repository unavailable for {spec.owner_repo}: "
                f"requested {spec.commit!r} could not be fetched and default HEAD "
                f"could not be checked out: "
                f"{fetch_result.combined_output}\n{fallback_result.combined_output}".strip()
            )
        version_mismatch = True

    checkout_target = checkout_ref
    _run_or_raise(
        runner,
        ["git", "checkout", "--detach", checkout_target],
        f"checkout failed for {spec.owner_repo}@{checkout_target}",
        cwd=repo_path,
    )
    actual_commit = _current_head(repo_path=repo_path, runner=runner)
    return PreparedProject(
        repo_path=repo_path,
        requested_commit=spec.commit,
        checkout_ref=checkout_ref,
        actual_commit=actual_commit,
        version_mismatch=version_mismatch,
    )


def _fetch_default_head(
    *,
    repo_path: Path,
    runner: CommandRunner,
) -> tuple[str | None, CommandResult]:
    fetch_head_result = runner(["git", "fetch", "--depth", "1", "origin", "HEAD"], repo_path)
    if fetch_head_result.ok:
        return "FETCH_HEAD", fetch_head_result

    symbolic_head_result = runner(
        ["git", "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"],
        repo_path,
    )
    if symbolic_head_result.ok and symbolic_head_result.stdout.strip():
        return symbolic_head_result.stdout.strip().splitlines()[0], symbolic_head_result

    for fallback_ref in ("origin/main", "origin/master"):
        verify_result = runner(
            ["git", "rev-parse", "--verify", "--quiet", f"{fallback_ref}^{{commit}}"],
            repo_path,
        )
        if verify_result.ok and verify_result.stdout.strip():
            return fallback_ref, verify_result

    return None, fetch_head_result


def _current_head(
    *,
    repo_path: Path,
    runner: CommandRunner,
) -> str | None:
    result = runner(["git", "rev-parse", "--verify", "HEAD"], repo_path)
    if not result.ok:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return output.splitlines()[0]


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
        oracles_dir: Path | None = None,
        base_request: BuildRequest,
        clone_timeout: float = 900.0,
        run_id_prefix: str | None = None,
        limit: int | None = None,
        stop_on_failure: bool = False,
        jobs: int = 1,
        command_runner: CommandRunner | None = None,
        builder_factory: BuilderFactory = EnvironmentBuilder,
    ):
        if jobs < 1:
            raise ValueError("jobs must be >= 1")
        self.projects_file = projects_file.expanduser().resolve()
        self.projects_dir = projects_dir.expanduser().resolve()
        self.oracles_dir = None if oracles_dir is None else oracles_dir.expanduser().resolve()
        self.base_request = base_request
        self.clone_timeout = clone_timeout
        self.run_id_prefix = run_id_prefix
        self.limit = limit
        self.stop_on_failure = stop_on_failure
        self.jobs = jobs
        self.command_runner = command_runner
        self.builder_factory = builder_factory

    def build_all(self) -> BatchBuildResult:
        with _project_dir_lock(self.projects_dir):
            specs = parse_projects_file(self.projects_file)
            if self.limit is not None:
                specs = specs[: self.limit]

            failures_log_path = self.projects_dir / "failed-projects.log"
            if failures_log_path.exists():
                failures_log_path.unlink()
            llm_usage_log_path = self.projects_dir / "llm-usage-projects.jsonl"
            if llm_usage_log_path.exists():
                llm_usage_log_path.unlink()
            no_repo_log_path = self.projects_dir / "no-repo-projects.log"
            known_no_repo_keys = _read_no_repo_log_keys(no_repo_log_path)
            version_mismatch_log_path = self.projects_dir / "version-mismatch-projects.log"

            results = self._build_specs(
                specs,
                known_no_repo_keys=known_no_repo_keys,
                failures_log_path=failures_log_path,
                no_repo_log_path=no_repo_log_path,
                version_mismatch_log_path=version_mismatch_log_path,
                llm_usage_log_path=llm_usage_log_path,
            )

            return BatchBuildResult(
                ok=all(result.ok or result.skipped for result in results),
                projects_dir=self.projects_dir,
                oracles_dir=self.oracles_dir,
                results=results,
                failures_log_path=failures_log_path if failures_log_path.exists() else None,
                no_repo_log_path=no_repo_log_path if no_repo_log_path.exists() else None,
                version_mismatch_log_path=(
                    version_mismatch_log_path if version_mismatch_log_path.exists() else None
                ),
                llm_usage_log_path=llm_usage_log_path if llm_usage_log_path.exists() else None,
                ablation_mode=self.base_request.ablation_mode,
                progress_control=_progress_control_json(self.base_request.ablation_mode),
            )

    def _build_specs(
        self,
        specs: list[ProjectSpec],
        *,
        known_no_repo_keys: set[ProjectLogKey],
        failures_log_path: Path,
        no_repo_log_path: Path,
        version_mismatch_log_path: Path,
        llm_usage_log_path: Path,
    ) -> list[ProjectRunResult]:
        if self.jobs == 1:
            results: list[ProjectRunResult] = []
            for spec in specs:
                result = self._build_one_project(spec, known_no_repo_keys)
                results.append(result)
                self._record_project_result(
                    result,
                    known_no_repo_keys=known_no_repo_keys,
                    failures_log_path=failures_log_path,
                    no_repo_log_path=no_repo_log_path,
                    version_mismatch_log_path=version_mismatch_log_path,
                    llm_usage_log_path=llm_usage_log_path,
                )
                if self.stop_on_failure and not result.ok and not result.skipped:
                    break
            return results

        completed: list[tuple[int, ProjectRunResult]] = []
        next_index = 0
        stop_scheduling = False
        futures: dict[Future[ProjectRunResult], tuple[int, ProjectSpec]] = {}
        with ThreadPoolExecutor(max_workers=self.jobs) as executor:
            while futures or (next_index < len(specs) and not stop_scheduling):
                while (
                    not stop_scheduling
                    and next_index < len(specs)
                    and len(futures) < self.jobs
                ):
                    spec = specs[next_index]
                    future = executor.submit(
                        self._build_one_project,
                        spec,
                        frozenset(known_no_repo_keys),
                    )
                    futures[future] = (next_index, spec)
                    next_index += 1

                if not futures:
                    break

                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    index, spec = futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = ProjectRunResult(
                            project=spec,
                            repo_path=self.projects_dir / spec.checkout_dir_name,
                            ok=False,
                            failure_stage="build_failed",
                            error=str(exc),
                        )
                    completed.append((index, result))
                    self._record_project_result(
                        result,
                        known_no_repo_keys=known_no_repo_keys,
                        failures_log_path=failures_log_path,
                        no_repo_log_path=no_repo_log_path,
                        version_mismatch_log_path=version_mismatch_log_path,
                        llm_usage_log_path=llm_usage_log_path,
                    )
                    if self.stop_on_failure and not result.ok and not result.skipped:
                        stop_scheduling = True
                        if futures:
                            self._emit(
                                "stop-on-failure triggered; waiting for "
                                f"{len(futures)} in-flight project(s)"
                            )

        return [result for _, result in sorted(completed, key=lambda item: item[0])]

    def _build_one_project(
        self,
        spec: ProjectSpec,
        known_no_repo_keys: set[ProjectLogKey] | frozenset[ProjectLogKey],
    ) -> ProjectRunResult:
        repo_path = self.projects_dir / spec.checkout_dir_name
        oracle_path: Path | None = None
        actual_commit: str | None = None
        version_mismatch = False
        failure_stage = "prepare_failed"
        try:
            existing_result = self._existing_successful_result(spec, repo_path)
            if existing_result is not None:
                self._emit(
                    f"project {spec.owner_repo}: skip existing successful run "
                    f"{existing_result.run_id}"
                )
                return existing_result
            if _project_log_key(spec) in known_no_repo_keys:
                self._emit(
                    f"project {spec.owner_repo}: skip previously unavailable repository"
                )
                return ProjectRunResult(
                    project=spec,
                    repo_path=repo_path,
                    ok=False,
                    skipped=True,
                    failure_stage="unavailable_project",
                    error="previously marked unavailable in no-repo-projects.log",
                )
            if repo_path.exists():
                self._emit(
                    f"project {spec.owner_repo}: reset existing incomplete project at "
                    f"{repo_path}"
                )
                if repo_path.is_dir() and not repo_path.is_symlink():
                    shutil.rmtree(repo_path)
                else:
                    repo_path.unlink()

            self._emit(f"project {spec.owner_repo}@{spec.commit}: prepare")
            prepared_project = prepare_project(
                spec,
                projects_dir=self.projects_dir,
                clone_timeout=self.clone_timeout,
                stream_logs=self.base_request.stream_logs,
                command_runner=self.command_runner,
            )
            repo_path = prepared_project.repo_path
            actual_commit = prepared_project.actual_commit
            version_mismatch = prepared_project.version_mismatch
            if version_mismatch:
                self._emit(
                    f"project {spec.owner_repo}: requested {spec.commit} not found; "
                    f"using {actual_commit or prepared_project.checkout_ref}"
                )
            if self.oracles_dir is not None:
                oracle_path = isolate_project_oracles(
                    spec,
                    repo_path=repo_path,
                    oracles_dir=self.oracles_dir,
                )
                if oracle_path is not None:
                    self._emit(
                        f"project {spec.owner_repo}: isolated oracle data at {oracle_path}"
                    )
            self._emit(f"project {spec.owner_repo}: build")
            failure_stage = "build_failed"
            build_result = self.builder_factory(self._request_for(spec, repo_path)).build()
            return ProjectRunResult(
                project=spec,
                repo_path=repo_path,
                ok=build_result.ok,
                version_mismatch=version_mismatch,
                run_id=build_result.run_id,
                final_image=build_result.final_image,
                manifest_path=build_result.manifest_path,
                oracle_path=oracle_path,
                actual_commit=actual_commit,
                failure_stage=None if build_result.ok else failure_stage,
                error=build_result.error,
                llm_usage=build_result.llm_usage,
                ablation_mode=build_result.ablation_mode,
                progress_control=to_jsonable(build_result.progress_control),
                final_clean_replay_enabled=build_result.final_clean_replay_enabled,
                final_clean_replay_ok=build_result.final_clean_replay_ok,
                final_clean_replay_image=build_result.final_clean_replay_image,
                final_clean_replay_failure_stage=build_result.final_clean_replay_failure_stage,
            )
        except Exception as exc:
            error = str(exc)
            if failure_stage == "prepare_failed" and _is_unavailable_project_error(error):
                return ProjectRunResult(
                    project=spec,
                    repo_path=repo_path,
                    ok=False,
                    skipped=True,
                    version_mismatch=version_mismatch,
                    oracle_path=oracle_path,
                    actual_commit=actual_commit,
                    failure_stage="unavailable_project",
                    error=error,
                )
            return ProjectRunResult(
                project=spec,
                repo_path=repo_path,
                ok=False,
                version_mismatch=version_mismatch,
                oracle_path=oracle_path,
                actual_commit=actual_commit,
                failure_stage=failure_stage,
                error=error,
            )

    def _record_project_result(
        self,
        result: ProjectRunResult,
        *,
        known_no_repo_keys: set[ProjectLogKey],
        failures_log_path: Path,
        no_repo_log_path: Path,
        version_mismatch_log_path: Path,
        llm_usage_log_path: Path,
    ) -> None:
        if result.progress_control is None:
            result.ablation_mode = self.base_request.ablation_mode
            result.progress_control = _progress_control_json(result.ablation_mode)
        if (
            result.progress_control.get("final_clean_replay") is True
            and not result.final_clean_replay_enabled
        ):
            result.final_clean_replay_enabled = True
        if result.version_mismatch:
            self._upsert_version_mismatch_log(result, version_mismatch_log_path)
        if result.skipped:
            self._append_no_repo_log(result, no_repo_log_path, known_no_repo_keys)
        elif not result.ok:
            self._append_failure_log(result, failures_log_path)
        self._append_llm_usage_log(result, llm_usage_log_path)
        status = "skipped" if result.skipped else "ok" if result.ok else "failed"
        self._emit(f"project {result.project.owner_repo}: {status}")

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
            task_description=self.base_request.task_description,
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
            llm_api=self.base_request.llm_api,
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
            ablation_mode=self.base_request.ablation_mode,
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
        if _manifest_ablation_mode(manifest) != self.base_request.ablation_mode:
            return None
        oracle_path = None
        if self.oracles_dir is not None:
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
            llm_usage=_manifest_llm_usage(manifest),
            ablation_mode=_manifest_ablation_mode(manifest),
            progress_control=_manifest_progress_control(manifest),
            final_clean_replay_enabled=_manifest_bool(
                manifest,
                "final_clean_replay_enabled",
                default=False,
            ),
            final_clean_replay_ok=_manifest_optional_bool(manifest, "final_clean_replay_ok"),
            final_clean_replay_image=_manifest_optional_str(
                manifest,
                "final_clean_replay_image",
            ),
            final_clean_replay_failure_stage=_manifest_optional_str(
                manifest,
                "final_clean_replay_failure_stage",
            ),
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

    def _append_no_repo_log(
        self,
        result: ProjectRunResult,
        no_repo_log_path: Path,
        known_no_repo_keys: set[ProjectLogKey],
    ) -> None:
        key = _project_log_key(result.project)
        if key in known_no_repo_keys:
            return
        no_repo_log_path.parent.mkdir(parents=True, exist_ok=True)
        with no_repo_log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                "\t".join(
                    [
                        result.project.owner_repo,
                        result.project.commit,
                        result.project.checkout_dir_name,
                        str(result.repo_path),
                        result.failure_stage or "unavailable_project",
                    ]
                )
                + "\n"
            )
        known_no_repo_keys.add(key)

    def _append_llm_usage_log(
        self,
        result: ProjectRunResult,
        llm_usage_log_path: Path,
    ) -> None:
        llm_usage_log_path.parent.mkdir(parents=True, exist_ok=True)
        usage_total = result.llm_usage.get("total", {})
        record = {
            "owner_repo": result.project.owner_repo,
            "commit": result.project.commit,
            "checkout_dir_name": result.project.checkout_dir_name,
            "repo_path": str(result.repo_path),
            "ok": result.ok,
            "skipped": result.skipped,
            "version_mismatch": result.version_mismatch,
            "actual_commit": result.actual_commit,
            "run_id": result.run_id,
            "final_image": result.final_image,
            "manifest_path": str(result.manifest_path) if result.manifest_path else None,
            "oracle_path": str(result.oracle_path) if result.oracle_path else None,
            "failure_stage": result.failure_stage,
            "error": result.error,
            "ablation_mode": result.ablation_mode,
            "progress_control": result.progress_control,
            "final_clean_replay_enabled": result.final_clean_replay_enabled,
            "final_clean_replay_ok": result.final_clean_replay_ok,
            "final_clean_replay_image": result.final_clean_replay_image,
            "final_clean_replay_failure_stage": result.final_clean_replay_failure_stage,
            "requests": int(usage_total.get("requests", 0)),
            "input_tokens": int(usage_total.get("input_tokens", 0)),
            "output_tokens": int(usage_total.get("output_tokens", 0)),
            "reasoning_tokens": int(usage_total.get("reasoning_tokens", 0)),
            "total_tokens": int(usage_total.get("total_tokens", 0)),
            "llm_usage": result.llm_usage,
        }
        with llm_usage_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _upsert_version_mismatch_log(
        self,
        result: ProjectRunResult,
        version_mismatch_log_path: Path,
    ) -> None:
        version_mismatch_log_path.parent.mkdir(parents=True, exist_ok=True)
        spec = result.project
        key = _project_log_key(spec)
        new_line = "\t".join(
            [
                spec.owner_repo,
                spec.commit,
                result.actual_commit or "",
                spec.checkout_dir_name,
                str(result.repo_path),
            ]
        )
        lines: list[str] = []
        replaced = False
        if version_mismatch_log_path.exists():
            for line in version_mismatch_log_path.read_text(encoding="utf-8").splitlines():
                if _version_mismatch_log_key(line) == key:
                    if not replaced:
                        lines.append(new_line)
                        replaced = True
                    continue
                lines.append(line)
        if not replaced:
            lines.append(new_line)
        version_mismatch_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _project_log_key(spec: ProjectSpec) -> ProjectLogKey:
    return (spec.owner_repo, spec.commit, spec.checkout_dir_name)


def _read_no_repo_log_keys(path: Path) -> set[ProjectLogKey]:
    keys: set[ProjectLogKey] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            keys.add((parts[0], parts[1], parts[2]))
    return keys


def _version_mismatch_log_key(line: str) -> ProjectLogKey | None:
    parts = line.split("\t")
    if len(parts) < 4:
        return None
    return (parts[0], parts[1], parts[3])


def _manifest_llm_usage(manifest: object) -> dict[str, dict[str, int]]:
    if not isinstance(manifest, dict):
        return {}
    raw_usage = manifest.get("llm_usage")
    if not isinstance(raw_usage, dict):
        return {}
    usage: dict[str, dict[str, int]] = {}
    for phase, raw_phase_usage in raw_usage.items():
        if not isinstance(raw_phase_usage, dict):
            continue
        phase_usage: dict[str, int] = {}
        for key in (
            "requests",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "total_tokens",
        ):
            value = raw_phase_usage.get(key, 0)
            try:
                phase_usage[key] = int(value)
            except (TypeError, ValueError):
                phase_usage[key] = 0
        usage[str(phase)] = phase_usage
    return usage


def _manifest_ablation_mode(manifest: object) -> str:
    if not isinstance(manifest, dict):
        return DEFAULT_ABLATION_MODE
    value = manifest.get("ablation_mode")
    if isinstance(value, str) and value:
        return value
    return LEGACY_MANIFEST_ABLATION_MODE


def _progress_control_json(ablation_mode: str) -> dict[str, object]:
    try:
        progress_control = progress_control_for_ablation(ablation_mode)
    except ValueError:
        progress_control = progress_control_for_ablation(DEFAULT_ABLATION_MODE)
    value = to_jsonable(progress_control)
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _manifest_progress_control(manifest: object) -> dict[str, object]:
    if isinstance(manifest, dict):
        value = manifest.get("progress_control")
        if isinstance(value, dict):
            return {str(key): item for key, item in value.items()}
    return _progress_control_json(_manifest_ablation_mode(manifest))


def _manifest_bool(manifest: object, key: str, *, default: bool) -> bool:
    if not isinstance(manifest, dict):
        return default
    value = manifest.get(key)
    if isinstance(value, bool):
        return value
    return default


def _manifest_optional_bool(manifest: object, key: str) -> bool | None:
    if not isinstance(manifest, dict):
        return None
    value = manifest.get(key)
    if isinstance(value, bool):
        return value
    return None


def _manifest_optional_str(manifest: object, key: str) -> str | None:
    if not isinstance(manifest, dict):
        return None
    value = manifest.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _is_unavailable_project_error(error: str) -> bool:
    return error.startswith(
        (
            "clone failed for ",
            "repository unavailable for ",
        )
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
