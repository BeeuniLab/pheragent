from __future__ import annotations

import argparse
import json
from pathlib import Path

from .env import load_dotenv
from .models import BuildRequest, to_jsonable
from .orchestrator import EnvironmentBuilder
from .project_batch import ProjectBatchBuilder


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "plan":
        request = _request_from_args(args, require_dockerfile=False)
        result = EnvironmentBuilder(request).plan_only()
        _print_result(result, as_json=args.json)
        return 0

    if args.command == "build":
        request = _request_from_args(args, require_dockerfile=True)
        result = EnvironmentBuilder(request).build()
        _print_result(result, as_json=args.json)
        return 0 if result.ok else 1

    if args.command == "build-projects":
        request = _batch_base_request_from_args(args)
        result = ProjectBatchBuilder(
            projects_file=args.projects_file,
            projects_dir=args.projects_dir,
            oracles_dir=args.oracles_dir,
            base_request=request,
            clone_timeout=args.clone_timeout,
            run_id_prefix=args.run_id_prefix,
            limit=args.limit,
            stop_on_failure=args.stop_on_failure,
        ).build_all()
        _print_batch_result(result, as_json=args.json)
        return 0 if result.ok else 1

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pheragent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="Analyze a repo and write setup block scripts.")
    _add_common_args(plan, include_dockerfile=False)

    build = subparsers.add_parser("build", help="Run a checkpointed Docker environment build.")
    _add_common_args(build, include_dockerfile=True)
    build.add_argument(
        "--resume-from",
        default=None,
        help="Resume from an existing checkpoint image instead of rebuilding the base image.",
    )
    build.add_argument(
        "--start-at-block",
        default=None,
        help="When resuming, start execution at this block id.",
    )
    build.add_argument("--keep-container", action="store_true")
    build.add_argument("--cleanup-images", action="store_true")
    build.add_argument(
        "--stream-logs",
        action="store_true",
        help="Stream command output to the terminal while still saving full logs.",
    )

    build_projects = subparsers.add_parser(
        "build-projects",
        help="Clone projects from an owner/repo commit file and build each environment.",
    )
    _add_batch_args(build_projects)

    return parser


def _add_common_args(parser: argparse.ArgumentParser, *, include_dockerfile: bool) -> None:
    parser.add_argument("--repo", required=True, type=Path, help="Target repository path.")
    if include_dockerfile:
        parser.add_argument(
            "--base-dockerfile",
            required=False,
            type=Path,
            help="Base Dockerfile used to build the initial image.",
        )
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--container-workdir", default="/workspace/repo")
    parser.add_argument("--image-prefix", default="pheragent")
    parser.add_argument("--max-repair-attempts", type=int, default=2)
    parser.add_argument("--command-timeout", type=float, default=900.0)
    parser.add_argument("--docker-build-timeout", type=float, default=1800.0)
    parser.add_argument(
        "--planner",
        choices=("auto", "rules", "llm"),
        default="auto",
        help="Block planner. auto uses LLM when an API key is present, otherwise rules.",
    )
    parser.add_argument("--model", default=None, help="LLM model name, for example gpt-5.5.")
    parser.add_argument("--openai-base-url", default=None, help="OpenAI-compatible API base URL.")
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--openai-base-url-env", default="OPENAI_BASE_URL")
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--llm-max-tokens", type=int, default=4096)
    parser.add_argument("--llm-retries", type=int, default=3)
    parser.add_argument("--llm-retry-delay", type=float, default=1.0)
    parser.add_argument("--oracle-file", type=Path, default=None)
    parser.add_argument("--oracle-timeout", type=float, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")


def _add_batch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--projects-file",
        required=True,
        type=Path,
        help="File containing 'owner/repo commit' entries.",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=Path("projects"),
        help="Directory where repositories will be cloned.",
    )
    parser.add_argument(
        "--oracles-dir",
        type=Path,
        default=Path("oracles"),
        help="Directory where .github oracle data is moved before building.",
    )
    parser.add_argument(
        "--base-dockerfile",
        required=True,
        type=Path,
        help="Base Dockerfile used to build each initial image.",
    )
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--run-id-prefix", default=None)
    parser.add_argument("--container-workdir", default="/workspace/repo")
    parser.add_argument("--image-prefix", default="pheragent")
    parser.add_argument("--max-repair-attempts", type=int, default=2)
    parser.add_argument("--command-timeout", type=float, default=900.0)
    parser.add_argument("--docker-build-timeout", type=float, default=1800.0)
    parser.add_argument("--clone-timeout", type=float, default=900.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument(
        "--planner",
        choices=("auto", "rules", "llm"),
        default="auto",
        help="Block planner. auto uses LLM when an API key is present, otherwise rules.",
    )
    parser.add_argument("--model", default=None, help="LLM model name, for example gpt-5.5.")
    parser.add_argument("--openai-base-url", default=None, help="OpenAI-compatible API base URL.")
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--openai-base-url-env", default="OPENAI_BASE_URL")
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--llm-max-tokens", type=int, default=4096)
    parser.add_argument("--llm-retries", type=int, default=3)
    parser.add_argument("--llm-retry-delay", type=float, default=1.0)
    parser.add_argument("--oracle-file", type=Path, default=None)
    parser.add_argument("--oracle-timeout", type=float, default=None)
    parser.add_argument("--keep-container", action="store_true")
    parser.add_argument("--cleanup-images", action="store_true")
    parser.add_argument(
        "--stream-logs",
        action="store_true",
        help="Stream command output to the terminal while still saving full logs.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")


def _request_from_args(args: argparse.Namespace, *, require_dockerfile: bool) -> BuildRequest:
    base_dockerfile = getattr(args, "base_dockerfile", None)
    resume_from = getattr(args, "resume_from", None)
    if require_dockerfile and base_dockerfile is None and not resume_from:
        raise SystemExit("--base-dockerfile is required unless --resume-from is set")
    return BuildRequest(
        repo_path=args.repo,
        base_dockerfile=base_dockerfile,
        state_dir=args.state_dir,
        run_id=args.run_id,
        container_workdir=args.container_workdir,
        image_prefix=args.image_prefix,
        max_repair_attempts=args.max_repair_attempts,
        command_timeout=args.command_timeout,
        docker_build_timeout=args.docker_build_timeout,
        keep_container=bool(getattr(args, "keep_container", False)),
        cleanup_images=bool(getattr(args, "cleanup_images", False)),
        stream_logs=bool(getattr(args, "stream_logs", False)),
        planner_mode=args.planner,
        llm_model=args.model,
        openai_base_url=args.openai_base_url,
        openai_api_key_env=args.openai_api_key_env,
        openai_base_url_env=args.openai_base_url_env,
        llm_timeout=args.llm_timeout,
        llm_max_tokens=args.llm_max_tokens,
        llm_retries=args.llm_retries,
        llm_retry_delay=args.llm_retry_delay,
        oracle_file=args.oracle_file,
        oracle_timeout=args.oracle_timeout,
        resume_from=resume_from,
        start_at_block=getattr(args, "start_at_block", None),
    )


def _batch_base_request_from_args(args: argparse.Namespace) -> BuildRequest:
    return BuildRequest(
        repo_path=Path("."),
        base_dockerfile=args.base_dockerfile,
        state_dir=args.state_dir,
        run_id=None,
        container_workdir=args.container_workdir,
        image_prefix=args.image_prefix,
        max_repair_attempts=args.max_repair_attempts,
        command_timeout=args.command_timeout,
        docker_build_timeout=args.docker_build_timeout,
        keep_container=bool(getattr(args, "keep_container", False)),
        cleanup_images=bool(getattr(args, "cleanup_images", False)),
        stream_logs=bool(getattr(args, "stream_logs", False)),
        planner_mode=args.planner,
        llm_model=args.model,
        openai_base_url=args.openai_base_url,
        openai_api_key_env=args.openai_api_key_env,
        openai_base_url_env=args.openai_base_url_env,
        llm_timeout=args.llm_timeout,
        llm_max_tokens=args.llm_max_tokens,
        llm_retries=args.llm_retries,
        llm_retry_delay=args.llm_retry_delay,
        oracle_file=args.oracle_file,
        oracle_timeout=args.oracle_timeout,
    )


def _print_result(result, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(to_jsonable(result), indent=2, ensure_ascii=False))
        return
    status = "ok" if result.ok else "failed"
    print(f"pheragent run {result.run_id}: {status}")
    print(f"state: {result.state_dir}")
    print(f"scripts: {result.scripts_dir}")
    print(f"manifest: {result.manifest_path}")
    if result.final_image:
        print(f"final image: {result.final_image}")
    if result.error:
        print(f"error: {result.error}")


def _print_batch_result(result, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(to_jsonable(result), indent=2, ensure_ascii=False))
        return
    status = "ok" if result.ok else "failed"
    print(f"pheragent project batch: {status}")
    print(f"projects: {result.projects_dir}")
    print(f"oracles: {result.oracles_dir}")
    if result.failures_log_path:
        print(f"failures: {result.failures_log_path}")
    for project_result in result.results:
        project_status = "ok" if project_result.ok else "failed"
        print(
            f"- {project_result.project.owner_repo}@{project_result.project.commit}: "
            f"{project_status}"
        )
        print(f"  repo: {project_result.repo_path}")
        if project_result.run_id:
            print(f"  run: {project_result.run_id}")
        if project_result.final_image:
            print(f"  final image: {project_result.final_image}")
        if project_result.manifest_path:
            print(f"  manifest: {project_result.manifest_path}")
        if project_result.oracle_path:
            print(f"  oracle: {project_result.oracle_path}")
        if project_result.error:
            print(f"  error: {project_result.error}")
