from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from .models import (
    BlockExecution,
    BuildResult,
    CommandBlock,
    CommandResult,
    RepoContext,
    to_jsonable,
)


class BlockStore:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.blocks_dir = run_dir / "blocks"
        self.scripts_dir = run_dir / "scripts"
        self.logs_dir = run_dir / "logs"
        self.executions_path = run_dir / "executions.jsonl"
        self.context_path = run_dir / "context.json"
        self.manifest_path = run_dir / "manifest.json"
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def save_context(self, context: RepoContext) -> None:
        self.context_path.write_text(
            json.dumps(to_jsonable(context), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def write_blocks(self, blocks: list[CommandBlock]) -> list[CommandBlock]:
        written: list[CommandBlock] = []
        for block in sorted(blocks, key=lambda item: (item.order, item.id)):
            written.append(self.write_block(block))
        return written

    def write_block(self, block: CommandBlock) -> CommandBlock:
        script_path = self.script_path(block.id)
        script_path.write_text(block.script, encoding="utf-8")
        script_path.chmod(0o755)
        metadata_path = self.block_path(block.id)
        metadata_path.write_text(
            json.dumps(to_jsonable(block), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return replace(block)

    def update_block(self, block: CommandBlock) -> None:
        self.write_block(block)

    def list_blocks(self) -> list[CommandBlock]:
        blocks: list[CommandBlock] = []
        for path in sorted(self.blocks_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            blocks.append(CommandBlock(**payload))
        return sorted(blocks, key=lambda item: (item.order, item.id))

    def script_path(self, block_id: str) -> Path:
        return self.scripts_dir / f"{block_id}.sh"

    def block_path(self, block_id: str) -> Path:
        return self.blocks_dir / f"{block_id}.json"

    def append_execution(self, execution: BlockExecution) -> None:
        with self.executions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_jsonable(execution), ensure_ascii=False) + "\n")

    def write_execution_log(
        self,
        *,
        block_id: str,
        phase: str,
        attempt: int,
        command_result: CommandResult,
        checkpoint_before: str | None,
        checkpoint_after: str | None,
        repair_command: str | None,
    ) -> Path:
        block_logs_dir = self.logs_dir / block_id
        block_logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = block_logs_dir / f"{phase}-attempt-{attempt}.log"
        if log_path.exists():
            counter = 2
            while True:
                candidate = block_logs_dir / f"{phase}-attempt-{attempt}-{counter}.log"
                if not candidate.exists():
                    log_path = candidate
                    break
                counter += 1
        header = {
            "block_id": block_id,
            "phase": phase,
            "attempt": attempt,
            "exit_code": command_result.exit_code,
            "timed_out": command_result.timed_out,
            "duration_s": command_result.duration_s,
            "command": command_result.command,
            "checkpoint_before": checkpoint_before,
            "checkpoint_after": checkpoint_after,
            "repair_command": repair_command,
        }
        log_path.write_text(
            json.dumps(header, ensure_ascii=False, indent=2)
            + "\n\n--- stdout ---\n"
            + command_result.stdout
            + "\n\n--- stderr ---\n"
            + command_result.stderr,
            encoding="utf-8",
        )
        return log_path

    def save_manifest(self, result: BuildResult) -> None:
        self.manifest_path.write_text(
            json.dumps(to_jsonable(result), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
