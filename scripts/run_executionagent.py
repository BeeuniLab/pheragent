#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.project_retries < 0:
        raise SystemExit("--project-retries must be >= 0")
    run_root = resolve_path(args.run_root)
    projects_root = run_root / "projects"
    state_root = run_root / "state"
    project_files_root = run_root / "project-files"
    logs_root = run_root / "logs"
    results_root = run_root / "results"
    for path in (projects_root, state_root, project_files_root, logs_root, results_root):
        path.mkdir(parents=True, exist_ok=True)

    base_dockerfile = resolve_path(args.base_dockerfile)
    if not base_dockerfile.is_file():
        raise SystemExit(f"base Dockerfile not found: {base_dockerfile}")

    runner = shlex.split(args.runner)
    if not runner:
        raise SystemExit("--runner must not be empty")
    if args.require_runner and shutil.which(runner[0]) is None:
        raise SystemExit(f"runner executable not found: {runner[0]!r}")

    projects = select_projects(
        load_projects_file(resolve_path(args.projects_file)),
        start=args.start,
        limit=args.limit,
        only=args.only,
    )
    summary_path = results_root / "summary.json"
    jsonl_path = results_root / "results.jsonl"
    failures_path = results_root / "failures.tsv"
    skipped_path = results_root / "skipped.json"
    if args.fresh_results:
        jsonl_path.write_text("", encoding="utf-8")
        failures_path.write_text("", encoding="utf-8")
    else:
        jsonl_path.touch()
        failures_path.touch()

    if args.skip_oracle:
        runnable = runnable_without_oracles(projects)
        skipped: list[dict[str, Any]] = []
    else:
        oracle_index = build_oracle_index(resolve_path(args.oracle_root))
        runnable, skipped = attach_oracles(
            projects,
            oracle_index=oracle_index,
            fail_missing_oracle=args.fail_missing_oracle,
            include_empty_oracles=args.include_empty_oracles,
            include_invalid_shell_oracles=args.include_invalid_shell_oracles,
        )

    skipped_existing_results: list[dict[str, Any]] = []
    if args.skip_existing_results:
        completed_owner_repos = load_completed_owner_repos(jsonl_path)
        runnable, skipped_existing_results = filter_existing_results(
            runnable,
            completed_owner_repos=completed_owner_repos,
        )

    skipped_existing_success: list[dict[str, Any]] = []
    if args.skip_existing_success:
        runnable, skipped_existing_success = filter_existing_success(
            runnable,
            state_root=state_root,
        )

    skipped_path.write_text(json.dumps(skipped, indent=2, ensure_ascii=True) + "\n")

    print(f"executionagent projects selected: {len(projects)}")
    if args.skip_oracle:
        print(f"runnable without oracle: {len(runnable)}")
    else:
        print(f"runnable with oracle: {len(runnable)}")
        print(f"skipped without usable oracle: {len(skipped)}")
        print(f"oracle root: {resolve_path(args.oracle_root)}")
    if skipped_existing_results:
        print(f"skipped existing result records: {len(skipped_existing_results)}")
    if skipped_existing_success:
        print(f"skipped existing successful manifests: {len(skipped_existing_success)}")
    print(f"run root: {run_root}")
    print(f"summary: {summary_path}")

    if args.validate_oracles:
        if args.skip_oracle:
            raise SystemExit("--validate-oracles cannot be used with --skip-oracle")
        validate_oracles(runnable)
        print(f"validated {len(runnable)} oracle files")
        return 0

    if args.dry_run:
        for index, item in enumerate(runnable, start=1):
            command = build_command(
                args=args,
                runner=runner,
                item=item,
                project_file=project_files_root / f"{item['project_slug']}.txt",
                projects_root=projects_root,
                state_root=state_root,
                base_dockerfile=base_dockerfile,
            )
            print(f"[dry-run {index}/{len(runnable)}] {item['owner_repo']}@{item['commit']}")
            print("  " + " ".join(shlex.quote(part) for part in command))
        return 0

    results: list[dict[str, Any]] = []
    failure_count = 0
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
        append_jsonl(jsonl_path, payload)
        results.append(payload)
        if payload["ok"]:
            print(f"[executionagent] ok: {payload['owner_repo']}", flush=True)
            continue
        failure_count += 1
        append_failure(failures_path, payload)
        print(
            f"[executionagent] failed: {payload['owner_repo']} rc={payload['returncode']}",
            flush=True,
        )
        if args.stop_on_failure:
            break

    summary = {
        "ok": failure_count == 0,
        "selected": len(projects),
        "runnable": len(runnable),
        "skipped": len(skipped),
        "skipped_existing_results": len(skipped_existing_results),
        "skipped_existing_success": len(skipped_existing_success),
        "completed": len(results),
        "failures": failure_count,
        "run_root": str(run_root),
        "oracle_root": None if args.skip_oracle else str(resolve_path(args.oracle_root)),
        "results_jsonl": str(jsonl_path),
        "failures_tsv": str(failures_path),
        "skipped_json": str(skipped_path),
        "existing_result_skips": skipped_existing_results,
        "existing_success_skips": skipped_existing_success,
        "results": results,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n")

    print(
        "\nexecutionagent complete: "
        f"{len(results) - failure_count} ok, {failure_count} failed, {len(skipped)} skipped"
    )
    print(f"summary: {summary_path}")
    if skipped:
        print(f"skipped: {skipped_path}")
    if failure_count:
        print(f"failures: {failures_path}")
        return 1
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run ExecutionAgent projects one by one through pheragent, using "
            "per-project oracle files from success_output_multi-oracles-fixed."
        )
    )
    parser.add_argument(
        "--runner",
        default="uv run python -m pheragent",
        help="Command prefix used to invoke pheragent.",
    )
    parser.add_argument(
        "--projects-file",
        type=Path,
        default=Path("tests/projects/executionAgent.txt"),
    )
    parser.add_argument(
        "--oracle-root",
        type=Path,
        default=Path("tests/projects/success_output_multi-oracles-fixed"),
    )
    parser.add_argument(
        "--base-dockerfile",
        type=Path,
        default=Path("tests/dockerfile/Dockerfile.heragent-thin"),
    )
    parser.add_argument("--run-root", type=Path, default=Path("executionagent-runs"))
    parser.add_argument("--run-id-prefix", default="executionagent")
    parser.add_argument("--image-prefix", default="pheragent-executionagent")
    parser.add_argument("--container-workdir", default="/workspace/repo")
    parser.add_argument("--planner", choices=("auto", "rules", "llm"), default="auto")
    parser.add_argument("--llm-api", choices=("responses", "chat-completions"), default="responses")
    parser.add_argument("--model", default=None)
    parser.add_argument("--openai-base-url", default=None)
    parser.add_argument("--openai-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--openai-base-url-env", default="OPENAI_BASE_URL")
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--llm-max-tokens", type=int, default=4096)
    parser.add_argument("--llm-retries", type=int, default=3)
    parser.add_argument("--llm-retry-delay", type=float, default=1.0)
    parser.add_argument("--max-repair-attempts", type=int, default=2)
    parser.add_argument("--max-probe-failures", type=int, default=5)
    parser.add_argument(
        "--project-retries",
        type=int,
        default=0,
        help=(
            "Number of extra whole-project attempts after a failed run. "
            "Retries reset that project's workspace/state before rerunning."
        ),
    )
    parser.add_argument("--command-timeout", type=float, default=1800.0)
    parser.add_argument("--oracle-timeout", type=float, default=1800.0)
    parser.add_argument("--docker-build-timeout", type=float, default=7200.0)
    parser.add_argument("--clone-timeout", type=float, default=1800.0)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", default=None, help="Regex matched against owner/repo.")
    parser.add_argument(
        "--stream-logs",
        dest="stream_logs",
        action="store_true",
        help="Stream pheragent command output to the terminal while saving it to the project log.",
    )
    parser.add_argument(
        "--no-stream-logs",
        dest="stream_logs",
        action="store_false",
        help="Do not stream pheragent command output to the terminal.",
    )
    parser.add_argument("--keep-container", action="store_true")
    parser.add_argument("--cleanup-images", action="store_true")
    parser.add_argument("--json", action="store_true", help="Pass --json through to pheragent.")
    parser.add_argument("--fresh-results", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-oracles", action="store_true")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument(
        "--skip-oracle",
        action="store_true",
        help="Run setup builds only; do not load or pass per-project oracle files.",
    )
    parser.add_argument(
        "--skip-existing-results",
        action="store_true",
        help="Skip owner/repo entries already present in this run-root's results.jsonl.",
    )
    parser.add_argument(
        "--skip-existing-success",
        action="store_true",
        help="Skip projects with an existing ok manifest under this run-root's state directory.",
    )
    parser.add_argument(
        "--fail-missing-oracle",
        action="store_true",
        help="Fail before running if any selected project has no matching usable oracle.",
    )
    parser.add_argument(
        "--include-empty-oracles",
        action="store_true",
        help="Pass empty oracle files through to pheragent instead of skipping them.",
    )
    parser.add_argument(
        "--include-invalid-shell-oracles",
        action="store_true",
        help=(
            "Pass oracle files with commands that fail 'sh -n -c' validation. "
            "By default these are skipped because pheragent executes oracle commands with sh -lc."
        ),
    )
    parser.add_argument(
        "--no-require-runner",
        dest="require_runner",
        action="store_false",
        help="Do not check that the first --runner executable is on PATH.",
    )
    parser.set_defaults(require_runner=True, stream_logs=True)
    return parser.parse_args(argv)


def load_projects_file(path: Path) -> list[dict[str, str]]:
    projects: list[dict[str, str]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            raise SystemExit(f"invalid projects file line {line_no}: {line!r}")
        projects.append(
            {
                "owner_repo": parts[0],
                "commit": parts[1],
                "line_no": str(line_no),
                "raw_line": line,
            }
        )
    return projects


def select_projects(
    projects: list[dict[str, str]],
    *,
    start: int,
    limit: int | None,
    only: str | None,
) -> list[dict[str, str]]:
    if start < 0:
        raise SystemExit("--start must be >= 0")
    selected = projects
    if only:
        pattern = re.compile(only)
        selected = [project for project in selected if pattern.search(project["owner_repo"])]
    selected = selected[start:]
    if limit is not None:
        if limit < 0:
            raise SystemExit("--limit must be >= 0")
        selected = selected[:limit]
    return selected


def build_oracle_index(oracle_root: Path) -> dict[str, dict[str, Any]]:
    if not oracle_root.is_dir():
        raise SystemExit(f"oracle root not found: {oracle_root}")
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(oracle_root.glob("*/*.test-only.heragent.oracle.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        commands = oracle_commands(payload)
        shell_errors = shell_syntax_errors(commands)
        metadata = payload.get("repository_metadata")
        repository = metadata.get("repository") if isinstance(metadata, dict) else None
        keys = {path.parent.name.lower()}
        if isinstance(repository, str) and repository.strip():
            keys.add(repository.strip().lower())
        for key in keys:
            index[key] = {
                "path": path,
                "repository": repository,
                "command_count": len(commands),
                "shell_syntax_error_count": len(shell_errors),
                "shell_syntax_errors": shell_errors[:10],
            }
    return index


def attach_oracles(
    projects: list[dict[str, str]],
    *,
    oracle_index: dict[str, dict[str, Any]],
    fail_missing_oracle: bool,
    include_empty_oracles: bool,
    include_invalid_shell_oracles: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runnable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for project in projects:
        oracle = oracle_index.get(project["owner_repo"].lower())
        reason = None
        if oracle is None:
            reason = "missing_oracle"
        elif oracle["command_count"] == 0 and not include_empty_oracles:
            reason = "empty_oracle"
        elif oracle["shell_syntax_error_count"] and not include_invalid_shell_oracles:
            reason = "invalid_shell_oracle"
        if reason is not None:
            skipped.append(
                {
                    **project,
                    "reason": reason,
                    "oracle_file": str(oracle["path"]) if oracle else None,
                    "oracle_command_count": oracle["command_count"] if oracle else None,
                    "shell_syntax_error_count": (
                        oracle["shell_syntax_error_count"] if oracle else None
                    ),
                    "shell_syntax_errors": oracle["shell_syntax_errors"] if oracle else [],
                }
            )
            continue
        assert oracle is not None
        runnable.append(
            {
                **project,
                "project_slug": slug(project["owner_repo"]),
                "oracle_file": oracle["path"],
                "oracle_repository": oracle["repository"],
                "oracle_command_count": oracle["command_count"],
                "shell_syntax_error_count": oracle["shell_syntax_error_count"],
            }
        )
    if skipped and fail_missing_oracle:
        details = "\n".join(
            f"{item['owner_repo']}: {item['reason']} (line {item['line_no']})"
            for item in skipped
        )
        raise SystemExit(f"selected projects without usable oracle:\n{details}")
    return runnable, skipped


def runnable_without_oracles(projects: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            **project,
            "project_slug": slug(project["owner_repo"]),
            "oracle_file": None,
            "oracle_repository": None,
            "oracle_command_count": 0,
            "shell_syntax_error_count": 0,
        }
        for project in projects
    ]


def load_completed_owner_repos(path: Path) -> set[str]:
    completed: set[str] = set()
    if not path.is_file():
        return completed
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        owner_repo = payload.get("owner_repo")
        if isinstance(owner_repo, str) and owner_repo:
            completed.add(owner_repo)
    return completed


def filter_existing_results(
    items: list[dict[str, Any]],
    *,
    completed_owner_repos: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runnable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in items:
        if item["owner_repo"] in completed_owner_repos:
            skipped.append(
                {
                    "owner_repo": item["owner_repo"],
                    "commit": item["commit"],
                    "project_slug": item["project_slug"],
                    "reason": "existing_result",
                }
            )
        else:
            runnable.append(item)
    return runnable, skipped


def filter_existing_success(
    items: list[dict[str, Any]],
    *,
    state_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runnable: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in items:
        manifest_path = find_manifest(state_root / item["project_slug"])
        manifest_info = read_manifest_info(manifest_path)
        if manifest_info.get("ok") is True and manifest_info.get("final_image"):
            skipped.append(
                {
                    "owner_repo": item["owner_repo"],
                    "commit": item["commit"],
                    "project_slug": item["project_slug"],
                    "reason": "existing_success",
                    "manifest_path": str(manifest_path) if manifest_path else None,
                    "final_image": manifest_info.get("final_image"),
                }
            )
        else:
            runnable.append(item)
    return runnable, skipped


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
            reset_project_workspace(
                item["project_slug"],
                projects_root=projects_root,
                state_root=state_root,
            )

        log_path = project_log_path(
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
        result = run_command(command, log_path=log_path, echo=args.stream_logs)
        manifest_path = find_manifest(state_root / item["project_slug"])
        manifest_info = read_manifest_info(manifest_path)
        payload = {
            "ok": result.returncode == 0,
            "index": index,
            "owner_repo": item["owner_repo"],
            "commit_version": item["commit"],
            "project_slug": item["project_slug"],
            "project_file": str(project_file),
            "oracle_file": str(item["oracle_file"]) if item.get("oracle_file") else None,
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
                f"[executionagent] retrying: {item['owner_repo']} "
                f"rc={result.returncode} next_attempt={attempt + 1}/{max_attempts}",
                flush=True,
            )

    final_payload = attempt_payloads[-1]
    if len(attempt_payloads) > 1:
        final_payload["attempts"] = summarize_attempts(attempt_payloads)
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
        str(args.jobs),
    ]
    if not args.skip_oracle and item.get("oracle_file"):
        command.extend(
            [
                "--oracle-file",
                str(item["oracle_file"]),
                "--oracle-timeout",
                str(args.oracle_timeout),
            ]
        )
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


def run_command(
    command: list[str],
    *,
    log_path: Path,
    echo: bool,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(shlex.quote(part) for part in command) + "\n\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            if echo:
                print(line, end="", flush=True)
        returncode = process.wait()
    return subprocess.CompletedProcess(command, returncode)


def validate_oracles(items: list[dict[str, Any]]) -> None:
    failures: list[str] = []
    for item in items:
        path = Path(item["oracle_file"])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            commands = oracle_commands(payload)
        except Exception as exc:
            failures.append(f"{path}: invalid oracle JSON: {exc}")
            continue
        if not commands:
            failures.append(f"{path}: no fixed_test_commands commands found")
            continue
        for error in shell_syntax_errors(commands):
            failures.append(
                f"{path}: command {error['command_index']} shell syntax failed: "
                f"{error['stderr']}"
            )
    if failures:
        raise SystemExit("\n".join(failures))


def oracle_commands(payload: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    fixed = payload.get("fixed_test_commands")
    if not isinstance(fixed, list):
        return commands
    for item in fixed:
        if not isinstance(item, dict):
            continue
        raw_commands = item.get("commands")
        if isinstance(raw_commands, list):
            commands.extend(str(command).strip() for command in raw_commands)
        elif isinstance(item.get("command"), str):
            commands.append(item["command"].strip())
    return [command for command in commands if command]


def shell_syntax_errors(commands: list[str]) -> list[dict[str, str | int]]:
    errors: list[dict[str, str | int]] = []
    for command_index, command in enumerate(commands, start=1):
        result = subprocess.run(
            ["sh", "-n", "-c", command],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(
                {
                    "command_index": command_index,
                    "stderr": result.stderr.strip(),
                    "command_excerpt": command[:200],
                }
            )
    return errors


def find_manifest(state_dir: Path) -> Path | None:
    candidates = sorted(
        [
            *state_dir.glob("runs/*/manifest.json"),
            *state_dir.glob("*/runs/*/manifest.json"),
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def read_manifest_info(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"failed to read manifest: {exc}"}
    usage = payload.get("llm_usage")
    if isinstance(usage, dict):
        usage = usage.get("total", usage)
    return {
        "ok": payload.get("ok"),
        "error": payload.get("error"),
        "final_image": payload.get("final_image"),
        "llm_usage": usage,
    }


def reset_project_workspace(
    project_slug: str,
    *,
    projects_root: Path,
    state_root: Path,
) -> None:
    for path in (projects_root / project_slug, state_root / project_slug):
        if path.exists():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()


def project_log_path(
    logs_root: Path,
    *,
    index: int,
    project_slug: str,
    attempt: int,
    max_attempts: int,
) -> Path:
    if max_attempts == 1:
        return logs_root / f"{index:03d}-{project_slug}.log"
    return logs_root / f"{index:03d}-{project_slug}-attempt-{attempt}.log"


def summarize_attempts(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "attempt": payload["attempt"],
            "ok": payload["ok"],
            "returncode": payload["returncode"],
            "manifest_error": payload.get("manifest_error"),
            "log_path": payload["log_path"],
        }
        for payload in payloads
    ]


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def append_failure(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\t".join(
                [
                    str(payload["owner_repo"]),
                    str(payload["commit_version"]),
                    str(payload.get("returncode", "")),
                    str(payload.get("manifest_path") or ""),
                    str(payload.get("oracle_file") or ""),
                    str(payload.get("log_path") or ""),
                ]
            )
            + "\n"
        )


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "project"


if __name__ == "__main__":
    raise SystemExit(main())
