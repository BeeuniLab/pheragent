#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DESCRIPTION_KEYS = (
    "task_description",
    "setup_task",
    "setup_description",
    "description",
    "instruction",
    "instructions",
    "prompt",
    "task",
)
ABLATION_MODES = (
    "full",
    "without-local-repair",
    "without-checkpoint-rollback",
    "without-final-clean-replay",
    "single-command-forward",
    "single-command-recovery",
    "single-command-forward-recovery",
    "single-command-rollback-regenerate",
    "block-rollback-regenerate",
    "block-live-repair-no-patch",
    "whole-script-forward",
    "whole-script-recovery",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.project_retries < 0:
        raise SystemExit("--project-retries must be >= 0")
    if args.jobs < 1:
        raise SystemExit("--jobs must be >= 1")
    run_root = args.run_root.resolve()
    projects_root = run_root / "projects"
    state_root = run_root / "state"
    project_files_root = run_root / "project-files"
    logs_root = run_root / "logs"
    results_root = run_root / "results"
    for path in (projects_root, state_root, project_files_root, logs_root, results_root):
        path.mkdir(parents=True, exist_ok=True)
    summary_path = results_root / "summary.json"
    jsonl_path = results_root / "results.jsonl"
    failures_path = results_root / "failures.tsv"
    previous_failures = load_failure_records(failures_path) if args.rerun_failures else []
    failed_owner_repos = (
        {record["owner_repo"] for record in previous_failures}
        if args.rerun_failures
        else None
    )

    items = select_items(
        load_index(args.index),
        start=args.start,
        limit=args.limit,
        only=args.only,
        only_owner_repos=failed_owner_repos,
    )

    if args.rerun_failures and not previous_failures:
        print(f"no previous failures found: {failures_path}")
        return 0

    if args.validate_oracles:
        validate_oracles(items)
        print(f"validated {len(items)} setupbench oracle files")
        return 0

    base_dockerfile = resolve_path(args.base_dockerfile)
    if not base_dockerfile.is_file():
        raise SystemExit(f"base Dockerfile not found: {base_dockerfile}")

    runner = shlex.split(args.runner)
    if not runner:
        raise SystemExit("--runner must not be empty")
    if args.require_uv and shutil.which(runner[0]) is None:
        raise SystemExit(
            f"runner executable not found: {runner[0]!r}; "
            "install uv or pass --runner 'python -m pheragent'"
        )

    prepare_result_files(
        jsonl_path=jsonl_path,
        failures_path=failures_path,
        fresh=args.fresh_results,
    )
    if args.rerun_failures:
        reset_selected_failed_workspaces(
            items,
            projects_root=projects_root,
            state_root=state_root,
        )

    print(f"setupbench projects: {len(items)}")
    if args.rerun_failures:
        print(f"rerun failures from: {failures_path}")
    print(f"runner: {' '.join(shlex.quote(part) for part in runner)}")
    print(f"run root: {run_root}")
    print(f"summary: {summary_path}")

    if args.dry_run:
        for index, item in enumerate(items, start=1):
            owner_repo = item["owner_repo"]
            commit = item["commit_version"]
            oracle_file = resolve_path(item["oracle_file"])
            project_slug = slug(owner_repo)
            project_file = project_files_root / f"{project_slug}.txt"
            task_description = task_description_for_item(item, oracle_file)
            command = build_command(
                args=args,
                runner=runner,
                project_file=project_file,
                project_slug=project_slug,
                oracle_file=oracle_file,
                task_description=task_description,
                projects_root=projects_root,
                state_root=state_root,
                base_dockerfile=base_dockerfile,
            )
            print(f"[dry-run {index}/{len(items)}] {owner_repo}@{commit}")
            print("  " + " ".join(shlex.quote(part) for part in command))
        return 0

    results: list[dict[str, Any]] = []
    failure_count = 0
    for index, item in enumerate(items, start=1):
        payload = run_project(
            args=args,
            index=index,
            total=len(items),
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

        if not payload["ok"]:
            failure_count += 1
            if args.rerun_failures:
                update_failure_record(failures_path, payload, failed=True)
            else:
                append_failure(failures_path, payload)
            print(
                f"[setupbench] failed: {payload['owner_repo']} "
                f"rc={payload['returncode']}",
                flush=True,
            )
            if args.stop_on_failure:
                break
        else:
            if args.rerun_failures:
                update_failure_record(failures_path, payload, failed=False)
            print(f"[setupbench] ok: {payload['owner_repo']}", flush=True)

    summary = {
        "ok": failure_count == 0,
        "total": len(results),
        "failures": failure_count,
        "run_root": str(run_root),
        "results_jsonl": str(jsonl_path),
        "failures_tsv": str(failures_path),
        "results": results,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    print(f"\nsetupbench complete: {len(results) - failure_count} ok, {failure_count} failed")
    print(f"summary: {summary_path}")
    if failure_count:
        print(f"failures: {failures_path}")
        return 1
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run SetupBench projects one by one through the pheragent CLI. "
            "Each project gets its matching --oracle-file, so setup completion "
            "is followed by oracle validation in that project's Docker run."
        )
    )
    parser.add_argument(
        "--runner",
        default="uv run pheragent",
        help="Command prefix used to invoke pheragent. Default: 'uv run pheragent'.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=Path("tests/projects/setupbench-oracles/index.json"),
    )
    parser.add_argument(
        "--base-dockerfile",
        type=Path,
        default=Path("tests/dockerfile/Dockerfile.heragent-thin"),
    )
    parser.add_argument("--run-root", type=Path, default=Path("setupbench-runs"))
    parser.add_argument("--run-id-prefix", default="setupbench")
    parser.add_argument("--image-prefix", default="pheragent-setupbench")
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
    parser.add_argument(
        "--ablation",
        choices=ABLATION_MODES,
        default="full",
        help="Progress-control ablation mode passed through to pheragent build-projects.",
    )
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
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of projects the underlying pheragent build-projects command may run.",
    )
    parser.add_argument("--command-timeout", type=float, default=1800.0)
    parser.add_argument("--oracle-timeout", type=float, default=1800.0)
    parser.add_argument("--docker-build-timeout", type=float, default=7200.0)
    parser.add_argument("--clone-timeout", type=float, default=1800.0)
    parser.add_argument("--start", type=int, default=0, help="Zero-based start index.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", default=None, help="Regex matched against owner/repo.")
    parser.add_argument(
        "--rerun-failures",
        action="store_true",
        help=(
            "Only run repos currently listed in this run-root's results/failures.tsv. "
            "Old selected failures are removed before rerun and re-added only if they fail again."
        ),
    )
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--stream-logs", action="store_true")
    parser.add_argument("--keep-container", action="store_true")
    parser.add_argument("--cleanup-images", action="store_true")
    parser.add_argument("--json", action="store_true", help="Pass --json through to pheragent.")
    parser.add_argument(
        "--fresh-results",
        action="store_true",
        help="Clear results.jsonl and failures.tsv before running.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-oracles", action="store_true")
    parser.add_argument(
        "--no-require-uv",
        dest="require_uv",
        action="store_false",
        help="Do not check that the first --runner executable is on PATH.",
    )
    parser.set_defaults(require_uv=True)
    return parser.parse_args(argv)


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
    owner_repo = item["owner_repo"]
    commit = item["commit_version"]
    project_slug = slug(owner_repo)
    oracle_file = resolve_path(item["oracle_file"])
    task_description = task_description_for_item(item, oracle_file)
    project_file = project_files_root / f"{project_slug}.txt"
    project_file.write_text(f"{owner_repo} {commit}\n", encoding="utf-8")

    max_attempts = args.project_retries + 1
    attempt_payloads: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            reset_project_workspace(
                project_slug,
                projects_root=projects_root,
                state_root=state_root,
            )

        log_path = project_log_path(
            logs_root,
            index=index,
            project_slug=project_slug,
            attempt=attempt,
            max_attempts=max_attempts,
        )
        command = build_command(
            args=args,
            runner=runner,
            project_file=project_file,
            project_slug=project_slug,
            oracle_file=oracle_file,
            task_description=task_description,
            projects_root=projects_root,
            state_root=state_root,
            base_dockerfile=base_dockerfile,
        )

        if attempt == 1:
            print(f"\n===== [{index}/{total}] {owner_repo}@{commit} =====", flush=True)
        else:
            print(
                f"\n===== [{index}/{total}] retry {attempt}/{max_attempts} "
                f"{owner_repo}@{commit} =====",
                flush=True,
            )
        print(f"log: {log_path}", flush=True)

        result = run_command(command, log_path=log_path, echo=args.stream_logs)
        manifest_path = find_manifest(state_root / project_slug)
        manifest_info = read_manifest_info(manifest_path)
        payload = {
            "ok": result.returncode == 0,
            "index": index,
            "owner_repo": owner_repo,
            "commit_version": commit,
            "project_slug": project_slug,
            "project_file": str(project_file),
            "oracle_file": str(oracle_file),
            "task_description": task_description,
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
                f"[setupbench] retrying: {owner_repo} "
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
    project_file: Path,
    project_slug: str,
    oracle_file: Path,
    task_description: str | None,
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
        str(projects_root / project_slug),
        "--state-dir",
        str(state_root / project_slug),
        "--run-id-prefix",
        args.run_id_prefix,
        "--base-dockerfile",
        str(base_dockerfile),
        "--oracle-file",
        str(oracle_file),
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
        "--ablation",
        args.ablation,
        "--max-repair-attempts",
        str(args.max_repair_attempts),
        "--max-probe-failures",
        str(args.max_probe_failures),
        "--jobs",
        str(args.jobs),
    ]
    if task_description:
        command.extend(["--task-description", task_description])
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
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(shlex.quote(part) for part in command) + "\n\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
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


def load_index(path: Path) -> list[dict[str, Any]]:
    resolved = resolve_path(path)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    items = payload.get("oracles")
    if not isinstance(items, list):
        raise SystemExit(f"oracle index must contain an 'oracles' list: {resolved}")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"invalid oracle index item {index}: expected object")
        for key in ("owner_repo", "commit_version", "oracle_file"):
            if key not in item:
                raise SystemExit(f"invalid oracle index item {index}: missing {key}")
        normalized_item: dict[str, Any] = {
            "owner_repo": str(item["owner_repo"]),
            "commit_version": str(item["commit_version"]),
            "oracle_file": str(item["oracle_file"]),
        }
        for key in TASK_DESCRIPTION_KEYS:
            if key in item:
                normalized_item[key] = item[key]
        normalized.append(normalized_item)
    return normalized


def select_items(
    items: list[dict[str, Any]],
    *,
    start: int,
    limit: int | None,
    only: str | None,
    only_owner_repos: set[str] | None = None,
) -> list[dict[str, Any]]:
    if start < 0:
        raise SystemExit("--start must be >= 0")
    selected = items
    if only:
        pattern = re.compile(only)
        selected = [item for item in selected if pattern.search(item["owner_repo"])]
    if only_owner_repos is not None:
        selected = [item for item in selected if item["owner_repo"] in only_owner_repos]
    selected = selected[start:]
    if limit is not None:
        if limit < 0:
            raise SystemExit("--limit must be >= 0")
        selected = selected[:limit]
    return selected


def validate_oracles(items: list[dict[str, Any]]) -> None:
    failures: list[str] = []
    for item in items:
        path = resolve_path(item["oracle_file"])
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            commands = oracle_commands(payload)
        except Exception as exc:
            failures.append(f"{path}: invalid JSON/oracle format: {exc}")
            continue
        if not commands:
            failures.append(f"{path}: no fixed_test_commands commands found")
            continue
        for command_index, command in enumerate(commands, start=1):
            result = subprocess.run(
                ["sh", "-n", "-c", command],
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                failures.append(
                    f"{path}: command {command_index} shell syntax failed: "
                    f"{result.stderr.strip()}"
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


def task_description_for_item(item: dict[str, Any], oracle_file: Path) -> str | None:
    direct = _first_text(item, TASK_DESCRIPTION_KEYS)
    if direct:
        return direct
    try:
        payload = json.loads(oracle_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return oracle_task_description(payload)


def oracle_task_description(payload: dict[str, Any]) -> str | None:
    direct = _first_text(payload, TASK_DESCRIPTION_KEYS)
    if direct:
        return direct

    descriptions: list[str] = []
    commands: list[str] = []
    fixed = payload.get("fixed_test_commands")
    if isinstance(fixed, list):
        for item in fixed:
            if not isinstance(item, dict):
                continue
            description = _first_text(item, TASK_DESCRIPTION_KEYS)
            if description:
                descriptions.append(description)
            original_command = _first_text(item, ("original_command", "command"))
            if original_command:
                commands.append(_single_line(original_command))
            raw_commands = item.get("commands")
            if isinstance(raw_commands, list):
                commands.extend(_single_line(str(command)) for command in raw_commands)

    unique_descriptions = _dedupe(descriptions)
    unique_commands = _dedupe(command for command in commands if command)
    if unique_descriptions:
        text = "\n".join(unique_descriptions)
        if unique_commands:
            text += "\n\nSetupBench target validation command(s):\n" + "\n".join(
                f"- {command}" for command in unique_commands
            )
        return text
    if unique_commands:
        return "SetupBench target validation command(s):\n" + "\n".join(
            f"- {command}" for command in unique_commands
        )
    return None


def _first_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_multiline(value)
    return None


def _normalize_multiline(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()


def _single_line(value: str) -> str:
    return " ".join(value.split()).strip()


def _dedupe(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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


def prepare_result_files(*, jsonl_path: Path, failures_path: Path, fresh: bool) -> None:
    if fresh:
        jsonl_path.write_text("", encoding="utf-8")
        failures_path.write_text("", encoding="utf-8")
        return
    jsonl_path.touch()
    failures_path.touch()


def reset_selected_failed_workspaces(
    items: list[dict[str, str]],
    *,
    projects_root: Path,
    state_root: Path,
) -> None:
    for item in items:
        reset_project_workspace(
            slug(item["owner_repo"]),
            projects_root=projects_root,
            state_root=state_root,
        )


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
        handle.write(_failure_record_line(payload) + "\n")


def update_failure_record(path: Path, payload: dict[str, Any], *, failed: bool) -> None:
    owner_repo = str(payload["owner_repo"])
    records = [
        record for record in load_failure_records(path) if record["owner_repo"] != owner_repo
    ]
    if failed:
        records.append(_failure_record(payload))
    write_failure_records(path, records)


def load_failure_records(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    records: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        records.append(
            {
                "owner_repo": parts[0],
                "commit_version": parts[1],
                "returncode": parts[2],
                "manifest_path": parts[3],
                "oracle_file": parts[4],
                "log_path": parts[5],
            }
        )
    return records


def write_failure_records(path: Path, records: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(_failure_record_line(record) + "\n")


def _failure_record(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "owner_repo": str(payload["owner_repo"]),
        "commit_version": str(payload["commit_version"]),
        "returncode": str(payload.get("returncode", "")),
        "manifest_path": str(payload.get("manifest_path") or ""),
        "oracle_file": str(payload.get("oracle_file") or ""),
        "log_path": str(payload.get("log_path") or ""),
    }


def _failure_record_line(payload: dict[str, Any]) -> str:
    return "\t".join(
        [
            str(payload["owner_repo"]),
            str(payload["commit_version"]),
            str(payload.get("returncode", "")),
            str(payload.get("manifest_path") or ""),
            str(payload.get("oracle_file") or ""),
            str(payload.get("log_path") or ""),
        ]
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
