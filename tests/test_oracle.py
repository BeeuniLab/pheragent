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


def test_load_oracle_commands_downgrades_full_pytest_setupbench_oracle(
    tmp_path: Path,
) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {
                        "command": (
                            "python -m pytest -v && echo \"Setup successful\" "
                            "|| echo \"Setup failed\""
                        )
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    commands = load_oracle_commands(oracle_file)

    assert commands == [
        'python -m pytest --collect-only -q && echo "Setup successful" || echo "Setup failed"'
    ]


def test_load_oracle_commands_downgrades_tox_setupbench_oracle(tmp_path: Path) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {
                        "command": (
                            "python -m tox -e py310 && echo \"Setup successful\" "
                            "|| echo \"Setup failed\""
                        )
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    commands = load_oracle_commands(oracle_file)

    assert commands == [
        (
            'python -m tox --showconfig -e py310 >/dev/null && echo "Setup successful" '
            '|| echo "Setup failed"'
        )
    ]


def test_load_oracle_commands_rewrites_web_server_oracle(tmp_path: Path) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {
                        "command": (
                            "verify_web() { npm run start & pid=$!; sleep 90; "
                            'code=$(curl -s -o /dev/null -w "%{http_code}" '
                            "http://localhost:8080); [ $code -eq 200 ] && "
                            "echo \"Setup successful\" || echo \"Setup failed\"; "
                            "pgid=$(ps -o pgid= $pid | tr -d ' '); "
                            "kill -TERM -$pgid 2>/dev/null; }; verify_web || "
                            "echo \"Setup failed\""
                        )
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    command = load_oracle_commands(oracle_file)[0]

    assert "setsid sh -c \"npm run start\"" in command
    assert "cleanup_web_processes" in command
    assert 'oracle_pid="$$"' in command
    assert "$1 != oracle_pid" in command
    assert "127.0.0.1:8080" in command
    assert "kill -TERM -- \"-$pgid\"" in command


def test_load_oracle_commands_rewrites_prometheus_metrics_oracle(tmp_path: Path) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {
                        "command": (
                            "curl -s http://localhost:9090/metrics | "
                            "grep -q 'prometheus_build_info' && "
                            "echo 'Setup successful' || echo 'Setup failed'"
                        )
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    command = load_oracle_commands(oracle_file)[0]

    assert 'GOFLAGS="${GOFLAGS:-} -buildvcs=false"' in command
    assert "go build -o \"$prometheus_bin\" ./cmd/prometheus" in command
    assert "--web.listen-address=127.0.0.1:9090" in command
    assert "prometheus_build_info" in command


def test_load_oracle_commands_rewrites_caddy_oracle(tmp_path: Path) -> None:
    oracle_file = tmp_path / "oracle.json"
    oracle_file.write_text(
        json.dumps(
            {
                "fixed_test_commands": [
                    {
                        "command": (
                            "caddy list-modules | grep -q 'http' && "
                            "echo 'Setup successful' || echo 'Setup failed'"
                        )
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    command = load_oracle_commands(oracle_file)[0]

    assert "command -v caddy" in command
    assert "[ -x ./caddy ]" in command
    assert "go build -o \"$caddy_bin\" ./cmd/caddy" in command
    assert "\"$caddy_bin\" list-modules | grep -q 'http'" in command
