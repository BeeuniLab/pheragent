from __future__ import annotations

import json
from pathlib import Path


def load_oracle_commands(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    commands: list[str] = []
    fixed_test_commands = payload.get("fixed_test_commands")
    if isinstance(fixed_test_commands, list):
        for item in fixed_test_commands:
            if not isinstance(item, dict):
                continue
            raw_commands = item.get("commands")
            if isinstance(raw_commands, list):
                commands.extend(_clean_command(command) for command in raw_commands)
            elif isinstance(item.get("command"), str):
                commands.append(_clean_command(item["command"]))
    return [command for command in commands if command]


def _clean_command(value: object) -> str:
    return str(value).strip()
