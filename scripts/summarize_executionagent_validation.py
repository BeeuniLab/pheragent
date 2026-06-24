#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHASES = ("validation", "clean_replay_validation")
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_root = resolve_path(args.run_root)
    state_root = run_root / "state"
    output_path = resolve_path(args.output)
    manifest_paths = sorted(state_root.glob("*/*/runs/*/manifest.json"))

    projects: list[dict[str, Any]] = []
    phase_counts: Counter[str] = Counter()
    result_status_counts: Counter[str] = Counter()

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        block_map = {
            block["id"]: block
            for block in manifest.get("blocks", [])
            if isinstance(block, dict) and block.get("id")
        }
        relative_parts = manifest_path.relative_to(state_root).parts
        owner_repo = relative_parts[0]
        project_name = relative_parts[1]
        run_dir = relative_parts[3]

        validations: list[dict[str, Any]] = []
        for execution in manifest.get("executions", []):
            phase = execution.get("phase")
            if phase not in args.phases:
                continue
            block_id = execution.get("block_id")
            block = block_map.get(block_id, {})
            log_path = Path(execution["log_path"]) if execution.get("log_path") else None
            stdout_text, stderr_text = parse_log_output(log_path)
            result_status = classify_result(
                exit_code=execution.get("exit_code"),
                timed_out=execution.get("timed_out"),
            )
            phase_counts[phase] += 1
            result_status_counts[result_status] += 1

            validations.append(
                {
                    "block_id": block_id,
                    "phase": phase,
                    "attempt": execution.get("attempt"),
                    "exit_code": execution.get("exit_code"),
                    "timed_out": execution.get("timed_out"),
                    "duration_s": execution.get("duration_s"),
                    "declared_validation_command": block.get("validation_command"),
                    "command": extract_shell_command(execution.get("command")),
                    "raw_command": execution.get("command"),
                    "result_status": result_status,
                    "result_excerpt": build_combined_excerpt(
                        stdout_text,
                        stderr_text,
                        max_lines=args.max_excerpt_lines,
                        max_chars=args.max_excerpt_chars,
                    ),
                    "stdout_excerpt": trim_text(
                        stdout_text,
                        max_lines=args.max_excerpt_lines,
                        max_chars=args.max_excerpt_chars,
                    ),
                    "stderr_excerpt": trim_text(
                        stderr_text,
                        max_lines=args.max_excerpt_lines,
                        max_chars=args.max_excerpt_chars,
                    ),
                    "log_path": str(log_path) if log_path else None,
                }
            )

        projects.append(
            {
                "owner_repo": owner_repo,
                "project_name": project_name,
                "run_id": manifest.get("run_id", run_dir),
                "ok": manifest.get("ok"),
                "error": manifest.get("error"),
                "manifest_path": str(manifest_path),
                "validation_count": len(validations),
                "validations": validations,
            }
        )

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_root": str(run_root),
        "included_phases": list(args.phases),
        "project_count": len(projects),
        "manifest_count": len(manifest_paths),
        "validation_entry_count": sum(project["validation_count"] for project in projects),
        "phase_counts": dict(phase_counts),
        "result_status_counts": dict(result_status_counts),
        "projects": projects,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(output_path)
    print(
        json.dumps(
            {
                "project_count": summary["project_count"],
                "validation_entry_count": summary["validation_entry_count"],
                "phase_counts": summary["phase_counts"],
                "result_status_counts": summary["result_status_counts"],
            },
            ensure_ascii=True,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize ExecutionAgent block validation records into a JSON file."
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("executionagent-runs"),
        help="ExecutionAgent run root that contains state/ and results/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("executionagent-runs/results/block_validation_summary.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--phase",
        action="append",
        dest="phases",
        choices=DEFAULT_PHASES,
        help="Validation phase to include. Defaults to both validation phases.",
    )
    parser.add_argument(
        "--max-excerpt-lines",
        type=int,
        default=12,
        help="Maximum lines kept for each result excerpt.",
    )
    parser.add_argument(
        "--max-excerpt-chars",
        type=int,
        default=1200,
        help="Maximum characters kept for each result excerpt.",
    )
    args = parser.parse_args(argv)
    args.phases = tuple(args.phases or DEFAULT_PHASES)
    return args


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def parse_log_output(log_path: Path | None) -> tuple[str, str]:
    if log_path is None or not log_path.is_file():
        return "", ""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    stdout_marker = "\n--- stdout ---\n"
    stderr_marker = "\n--- stderr ---\n"
    stdout = ""
    stderr = ""
    if stdout_marker in text:
        _, remainder = text.split(stdout_marker, 1)
        if stderr_marker in remainder:
            stdout, stderr = remainder.split(stderr_marker, 1)
        else:
            stdout = remainder
    elif stderr_marker in text:
        _, stderr = text.split(stderr_marker, 1)
    return clean_output(stdout), clean_output(stderr)


def clean_output(text: str) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", text)
    return cleaned.strip()


def classify_result(exit_code: Any, timed_out: Any) -> str:
    if timed_out:
        return "timed_out"
    if exit_code == 0:
        return "success"
    return "failed"


def extract_shell_command(command: Any) -> str | None:
    if isinstance(command, list):
        if "-lc" in command:
            index = command.index("-lc")
            if index + 1 < len(command):
                return command[index + 1]
        return " ".join(shlex.quote(str(part)) for part in command)
    if isinstance(command, str):
        return command
    return None


def build_combined_excerpt(
    stdout_text: str,
    stderr_text: str,
    *,
    max_lines: int,
    max_chars: int,
) -> str:
    parts: list[str] = []
    if stdout_text:
        parts.append("[stdout]\n" + stdout_text)
    if stderr_text:
        parts.append("[stderr]\n" + stderr_text)
    if not parts:
        return ""
    return trim_text("\n\n".join(parts), max_lines=max_lines, max_chars=max_chars)


def trim_text(text: str, *, max_lines: int, max_chars: int) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    trimmed_lines = lines[:max_lines]
    trimmed = "\n".join(trimmed_lines).strip()
    if len(trimmed) > max_chars:
        trimmed = trimmed[: max_chars - 3].rstrip() + "..."
    elif len(lines) > max_lines:
        trimmed += "\n..."
    return trimmed


if __name__ == "__main__":
    raise SystemExit(main())
