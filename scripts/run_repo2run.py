#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import shutil
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import run_executionagent as batch

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.project_retries < 0:
        raise SystemExit("--project-retries must be >= 0")
    if args.jobs < 1:
        raise SystemExit("--jobs must be >= 1")

    run_root = batch.resolve_path(args.run_root)
    projects_root = run_root / "projects"
    state_root = run_root / "state"
    project_files_root = run_root / "project-files"
    logs_root = run_root / "logs"
    results_root = run_root / "results"
    for path in (projects_root, state_root, project_files_root, logs_root, results_root):
        path.mkdir(parents=True, exist_ok=True)

    base_dockerfile = batch.resolve_path(args.base_dockerfile)
    if not base_dockerfile.is_file():
        raise SystemExit(f"base Dockerfile not found: {base_dockerfile}")

    oracle_file = batch.resolve_path(args.oracle_file)
    oracle_command_count = validate_oracle_file(oracle_file)

    runner = shlex.split(args.runner)
    if not runner:
        raise SystemExit("--runner must not be empty")
    if args.require_runner and shutil.which(runner[0]) is None:
        raise SystemExit(f"runner executable not found: {runner[0]!r}")

    projects = batch.select_projects(
        batch.load_projects_file(batch.resolve_path(args.projects_file)),
        start=args.start,
        limit=args.limit,
        only=args.only,
    )
    runnable = [
        {
            **project,
            "project_slug": batch.slug(project["owner_repo"]),
            "oracle_file": oracle_file,
            "oracle_command_count": oracle_command_count,
        }
        for project in projects
    ]

    summary_path = results_root / "summary.json"
    jsonl_path = results_root / "results.jsonl"
    failures_path = results_root / "failures.tsv"
    if args.fresh_results:
        jsonl_path.write_text("", encoding="utf-8")
        failures_path.write_text("", encoding="utf-8")
    else:
        jsonl_path.touch()
        failures_path.touch()

    if args.skip_existing_results:
        completed_owner_repos = batch.load_completed_owner_repos(jsonl_path)
        runnable, skipped_existing_results = batch.filter_existing_results(
            runnable,
            completed_owner_repos=completed_owner_repos,
        )
    else:
        skipped_existing_results = []

    if args.skip_existing_success:
        runnable, skipped_existing_success = batch.filter_existing_success(
            runnable,
            state_root=state_root,
        )
    else:
        skipped_existing_success = []

    print(f"repo2run projects selected: {len(projects)}")
    print(f"repo2run projects runnable: {len(runnable)}")
    print(f"oracle: {oracle_file}")
    print(f"oracle commands: {oracle_command_count}")
    print(f"model: {args.model}")
    print(f"max repair attempts: {args.max_repair_attempts}")
    print(f"repo2run jobs: {args.jobs}")
    print(
        "project retries: "
        f"{args.project_retries} extra, {args.project_retries + 1} total attempts"
    )
    if skipped_existing_results:
        print(f"skipped existing result records: {len(skipped_existing_results)}")
    if skipped_existing_success:
        print(f"skipped existing successful manifests: {len(skipped_existing_success)}")
    print(f"run root: {run_root}")
    print(f"summary: {summary_path}")

    if args.dry_run:
        for index, item in enumerate(runnable, start=1):
            project_file = project_files_root / f"{item['project_slug']}.txt"
            command = build_command(
                args=args,
                runner=runner,
                item=item,
                project_file=project_file,
                projects_root=projects_root,
                state_root=state_root,
                base_dockerfile=base_dockerfile,
            )
            print(f"[dry-run {index}/{len(runnable)}] {item['owner_repo']}@{item['commit']}")
            print("  " + " ".join(shlex.quote(part) for part in command))
        return 0

    results, failure_count = run_projects(
        args=args,
        runnable=runnable,
        runner=runner,
        projects_root=projects_root,
        state_root=state_root,
        project_files_root=project_files_root,
        logs_root=logs_root,
        base_dockerfile=base_dockerfile,
        jsonl_path=jsonl_path,
        failures_path=failures_path,
    )

    summary = {
        "ok": failure_count == 0,
        "selected": len(projects),
        "runnable": len(runnable),
        "completed": len(results),
        "failures": failure_count,
        "run_root": str(run_root),
        "oracle_file": str(oracle_file),
        "oracle_command_count": oracle_command_count,
        "results_jsonl": str(jsonl_path),
        "failures_tsv": str(failures_path),
        "skipped_existing_results": len(skipped_existing_results),
        "skipped_existing_success": len(skipped_existing_success),
        "existing_result_skips": skipped_existing_results,
        "existing_success_skips": skipped_existing_success,
        "results": sorted(results, key=lambda payload: payload["index"]),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    print(
        "\nrepo2run complete: "
        f"{len(results) - failure_count} ok, {failure_count} failed"
    )
    print(f"summary: {summary_path}")
    if failure_count:
        print(f"failures: {failures_path}")
        return 1
    return 0


def run_projects(
    *,
    args: argparse.Namespace,
    runnable: list[dict[str, Any]],
    runner: list[str],
    projects_root: Path,
    state_root: Path,
    project_files_root: Path,
    logs_root: Path,
    base_dockerfile: Path,
    jsonl_path: Path,
    failures_path: Path,
) -> tuple[list[dict[str, Any]], int]:
    results: list[dict[str, Any]] = []
    failure_count = 0
    if args.jobs == 1:
        for index, item in enumerate(runnable, start=1):
            payload = run_project(
                args=args,
                index=index,
                total=len(runnable),
                item=item,
                runner=runner,
                projects_root=projects_root,
                state_root=state_root,
                project_files_root=project_files_root,
                logs_root=logs_root,
                base_dockerfile=base_dockerfile,
            )
            failed = record_project_result(
                payload,
                jsonl_path=jsonl_path,
                failures_path=failures_path,
                results=results,
            )
            if failed:
                failure_count += 1
                if args.stop_on_failure:
                    break
        return results, failure_count

    indexed_items = list(enumerate(runnable, start=1))
    next_item = 0
    stop_submitting = False
    stop_notice_printed = False
    futures: dict[Future[dict[str, Any]], tuple[int, dict[str, Any]]] = {}

    def submit_until_full(executor: ThreadPoolExecutor) -> None:
        nonlocal next_item
        while (
            not stop_submitting
            and next_item < len(indexed_items)
            and len(futures) < args.jobs
        ):
            index, item = indexed_items[next_item]
            next_item += 1
            future = executor.submit(
                run_project,
                args=args,
                index=index,
                total=len(runnable),
                item=item,
                runner=runner,
                projects_root=projects_root,
                state_root=state_root,
                project_files_root=project_files_root,
                logs_root=logs_root,
                base_dockerfile=base_dockerfile,
            )
            futures[future] = (index, item)

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        submit_until_full(executor)
        while futures:
            completed, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in completed:
                futures.pop(future)
                payload = future.result()
                failed = record_project_result(
                    payload,
                    jsonl_path=jsonl_path,
                    failures_path=failures_path,
                    results=results,
                )
                if not failed:
                    continue
                failure_count += 1
                if args.stop_on_failure:
                    stop_submitting = True
                    if not stop_notice_printed and futures:
                        print(
                            "[repo2run] stop-on-failure: waiting for running jobs, "
                            "no new projects will be submitted",
                            flush=True,
                        )
                        stop_notice_printed = True
            submit_until_full(executor)
    return results, failure_count


def record_project_result(
    payload: dict[str, Any],
    *,
    jsonl_path: Path,
    failures_path: Path,
    results: list[dict[str, Any]],
) -> bool:
    batch.append_jsonl(jsonl_path, payload)
    results.append(payload)
    if payload["ok"]:
        print(f"[repo2run] ok: {payload['owner_repo']}", flush=True)
        return False

    batch.append_failure(failures_path, payload)
    print(
        f"[repo2run] failed: {payload['owner_repo']} rc={payload['returncode']}",
        flush=True,
    )
    return True


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run repo2run projects through pheragent with a shared pytest "
            "collect-only oracle."
        )
    )
    parser.add_argument(
        "--runner",
        default="uv run python -m pheragent",
        help="Command prefix used to invoke pheragent.",
    )
    parser.add_argument("--projects-file", type=Path, default=Path("tests/projects/repo2run.txt"))
    parser.add_argument(
        "--oracle-file",
        type=Path,
        default=Path("tests/projects/repo2run-pytest.oracle.json"),
    )
    parser.add_argument(
        "--base-dockerfile",
        type=Path,
        default=Path("tests/dockerfile/Dockerfile.heragent-thin"),
    )
    parser.add_argument("--run-root", type=Path, default=Path("repo2run-runs-gpt-4o-20241120-r30"))
    parser.add_argument("--run-id-prefix", default="repo2run-gpt-4o-20241120-r30")
    parser.add_argument("--image-prefix", default="pheragent-repo2run-gpt-4o-20241120-r30")
    parser.add_argument("--container-workdir", default="/workspace/repo")
    parser.add_argument("--planner", choices=("auto", "rules", "llm"), default="llm")
    parser.add_argument("--llm-api", choices=("responses", "chat-completions"), default="responses")
    parser.add_argument("--model", default="gpt-4o-20241120")
    parser.add_argument("--openai-base-url", default=None)
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--openai-base-url-env", default="OPENAI_BASE_URL")
    parser.add_argument("--llm-timeout", type=float, default=180.0)
    parser.add_argument("--llm-max-tokens", type=int, default=4096)
    parser.add_argument("--llm-retries", type=int, default=3)
    parser.add_argument("--llm-retry-delay", type=float, default=5.0)
    parser.add_argument("--max-repair-attempts", type=int, default=30)
    parser.add_argument("--max-probe-failures", type=int, default=5)
    parser.add_argument(
        "--project-retries",
        type=int,
        default=3,
        help=(
            "Number of extra whole-project attempts after a failed run. "
            "Default 3 means up to 4 total attempts per project."
        ),
    )
    parser.add_argument("--command-timeout", type=float, default=1800.0)
    parser.add_argument("--oracle-timeout", type=float, default=1800.0)
    parser.add_argument("--docker-build-timeout", type=float, default=7200.0)
    parser.add_argument("--clone-timeout", type=float, default=1800.0)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of repo2run projects to run concurrently.",
    )
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", default=None, help="Regex matched against owner/repo.")
    parser.add_argument("--stream-logs", action="store_true", default=True)
    parser.add_argument("--no-stream-logs", dest="stream_logs", action="store_false")
    parser.add_argument("--keep-container", action="store_true")
    parser.add_argument("--cleanup-images", action="store_true")
    parser.add_argument("--json", action="store_true", help="Pass --json through to pheragent.")
    parser.add_argument("--fresh-results", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--skip-existing-results", action="store_true")
    parser.add_argument("--skip-existing-success", action="store_true")
    parser.add_argument("--no-require-runner", dest="require_runner", action="store_false")
    parser.set_defaults(require_runner=True)
    return parser.parse_args(argv)


def validate_oracle_file(path: Path) -> int:
    if not path.is_file():
        raise SystemExit(f"oracle file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        commands = batch.oracle_commands(payload)
    except Exception as exc:
        raise SystemExit(f"invalid oracle JSON {path}: {exc}") from exc
    if not commands:
        raise SystemExit(f"oracle file did not contain commands: {path}")
    shell_errors = batch.shell_syntax_errors(commands)
    if shell_errors:
        details = "\n".join(
            f"command {error['command_index']}: {error['stderr']}"
            for error in shell_errors
        )
        raise SystemExit(f"oracle shell syntax failed: {path}\n{details}")
    return len(commands)


def run_project(
    *,
    args: argparse.Namespace,
    index: int,
    total: int,
    item: dict[str, Any],
    runner: list[str],
    projects_root: Path,
    state_root: Path,
    project_files_root: Path,
    logs_root: Path,
    base_dockerfile: Path,
) -> dict[str, Any]:
    project_file = project_files_root / f"{item['project_slug']}.txt"
    project_file.write_text(f"{item['owner_repo']} {item['commit']}\n", encoding="utf-8")
    max_attempts = args.project_retries + 1
    attempt_payloads: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            batch.reset_project_workspace(
                item["project_slug"],
                projects_root=projects_root,
                state_root=state_root,
            )

        log_path = batch.project_log_path(
            logs_root,
            index=index,
            project_slug=item["project_slug"],
            attempt=attempt,
            max_attempts=max_attempts,
        )
        command = build_command(
            args=args,
            runner=runner,
            item=item,
            project_file=project_file,
            projects_root=projects_root,
            state_root=state_root,
            base_dockerfile=base_dockerfile,
        )
        if attempt == 1:
            print(
                f"\n===== [{index}/{total}] {item['owner_repo']}@{item['commit']} "
                f"oracle_commands={item.get('oracle_command_count', 0)} =====",
                flush=True,
            )
        else:
            print(
                f"\n===== [{index}/{total}] retry {attempt}/{max_attempts} "
                f"{item['owner_repo']}@{item['commit']} "
                f"oracle_commands={item.get('oracle_command_count', 0)} =====",
                flush=True,
            )
        print(f"log: {log_path}", flush=True)

        result = batch.run_command(command, log_path=log_path, echo=args.stream_logs)
        manifest_path = batch.find_manifest(state_root / item["project_slug"])
        manifest_info = batch.read_manifest_info(manifest_path)
        payload = {
            "ok": result.returncode == 0,
            "index": index,
            "owner_repo": item["owner_repo"],
            "commit_version": item["commit"],
            "project_slug": item["project_slug"],
            "project_file": str(project_file),
            "oracle_file": str(item["oracle_file"]),
            "oracle_command_count": item.get("oracle_command_count", 0),
            "log_path": str(log_path),
            "returncode": result.returncode,
            "manifest_path": str(manifest_path) if manifest_path else None,
            "manifest_ok": manifest_info.get("ok"),
            "manifest_error": manifest_info.get("error"),
            "final_image": manifest_info.get("final_image"),
            "llm_usage": manifest_info.get("llm_usage"),
            "command": command,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "project_retries": args.project_retries,
        }
        attempt_payloads.append(payload)

        if result.returncode == 0:
            break
        if attempt < max_attempts:
            print(
                f"[repo2run] retrying: {item['owner_repo']} "
                f"rc={result.returncode} next_attempt={attempt + 1}/{max_attempts}",
                flush=True,
            )

    final_payload = attempt_payloads[-1]
    if len(attempt_payloads) > 1:
        final_payload["attempts"] = batch.summarize_attempts(attempt_payloads)
    return final_payload


def build_command(
    *,
    args: argparse.Namespace,
    runner: list[str],
    item: dict[str, Any],
    project_file: Path,
    projects_root: Path,
    state_root: Path,
    base_dockerfile: Path,
) -> list[str]:
    command = [
        *runner,
        "build-projects",
        "--projects-file",
        str(project_file),
        "--projects-dir",
        str(projects_root / item["project_slug"]),
        "--state-dir",
        str(state_root / item["project_slug"]),
        "--run-id-prefix",
        args.run_id_prefix,
        "--base-dockerfile",
        str(base_dockerfile),
        "--oracle-file",
        str(item["oracle_file"]),
        "--oracle-timeout",
        str(args.oracle_timeout),
        "--command-timeout",
        str(args.command_timeout),
        "--docker-build-timeout",
        str(args.docker_build_timeout),
        "--clone-timeout",
        str(args.clone_timeout),
        "--container-workdir",
        args.container_workdir,
        "--image-prefix",
        args.image_prefix,
        "--planner",
        args.planner,
        "--llm-api",
        args.llm_api,
        "--openai-api-key-env",
        args.openai_api_key_env,
        "--openai-base-url-env",
        args.openai_base_url_env,
        "--llm-timeout",
        str(args.llm_timeout),
        "--llm-max-tokens",
        str(args.llm_max_tokens),
        "--llm-retries",
        str(args.llm_retries),
        "--llm-retry-delay",
        str(args.llm_retry_delay),
        "--max-repair-attempts",
        str(args.max_repair_attempts),
        "--max-probe-failures",
        str(args.max_probe_failures),
        "--jobs",
        "1",
    ]
    if args.model:
        command.extend(["--model", args.model])
    if args.openai_base_url:
        command.extend(["--openai-base-url", args.openai_base_url])
    if args.stream_logs:
        command.append("--stream-logs")
    if args.keep_container:
        command.append("--keep-container")
    if args.cleanup_images:
        command.append("--cleanup-images")
    if args.json:
        command.append("--json")
    return command


if __name__ == "__main__":
    raise SystemExit(main())
