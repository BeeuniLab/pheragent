from __future__ import annotations

import json
from pathlib import Path

from pheragent.oracle import load_oracle_commands


def test_load_oracle_commands_reads_multi_oracle_format(tmp_path: Path) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {"commands": [" pytest -q ", ""]},
                    {"command": "tox run -e py3.12"},
                    {"commands": [123]},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_oracle_commands(oracle_file) == [
        "pytest -q",
        "tox run -e py3.12",
        "123",
    ]


def test_load_oracle_commands_sanitizes_known_unsafe_wrappers(tmp_path: Path) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {
                        "command": (
                            "python -m wagtail start mysite && "
                            "pgid=$(ps -o pgid= $pid | tr -d ' '); "
                            "kill -TERM -$pgid 2>/dev/null; "
                            "pgid1=$(ps -o pgid= $pid1 | tr -d ' '); "
                            "kill -TERM -$pgid1 2>/dev/null"
                        )
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_oracle_commands(oracle_file) == [
        (
            "wagtail start mysite && "
            "pgid=$(ps -o pgid= $pid | tr -d ' '); "
            'kill -TERM "$pid" 2>/dev/null; '
            "pgid1=$(ps -o pgid= $pid1 | tr -d ' '); "
            'kill -TERM "$pid1" 2>/dev/null'
        )
    ]
