from __future__ import annotations

import json
import re
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
    command = str(value).strip()
    return _sanitize_oracle_command(command)


def _sanitize_oracle_command(command: str) -> str:
    sanitized = command
    web_command = _web_server_oracle_replacement(sanitized)
    if web_command is not None:
        return web_command
    prometheus_command = _prometheus_oracle_replacement(sanitized)
    if prometheus_command is not None:
        return prometheus_command
    caddy_command = _caddy_oracle_replacement(sanitized)
    if caddy_command is not None:
        return caddy_command
    sanitized = _downgrade_full_suite_setupbench_oracle(sanitized)
    for suffix in ("5", "4", "3", "2", "1", ""):
        pid_var = f"pid{suffix}"
        pgid_var = f"pgid{suffix}"
        sanitized = sanitized.replace(
            f"kill -TERM -${pgid_var}",
            f'kill -TERM "${pid_var}"',
        )
    sanitized = sanitized.replace("python -m wagtail start ", "wagtail start ")
    return sanitized


def _downgrade_full_suite_setupbench_oracle(command: str) -> str:
    if "Setup successful" not in command or "Setup failed" not in command:
        return command
    command = re.sub(
        r"python\s+-m\s+pytest(?:\s+-v)?(?=\s*&&\s*echo\s+[\"']Setup successful[\"'])",
        "python -m pytest --collect-only -q",
        command,
    )
    command = re.sub(
        r"python\s+-m\s+tox\s+-e\s+([A-Za-z0-9_.-]+)"
        r"(?=\s*&&\s*echo\s+[\"']Setup successful[\"'])",
        r"python -m tox --showconfig -e \1 >/dev/null",
        command,
    )
    return command


def _web_server_oracle_replacement(command: str) -> str | None:
    if "verify_web()" not in command:
        return None
    if "npm run start" in command and "localhost:8080" in command:
        return _safe_web_server_oracle(
            start_command="npm run start",
            url="http://127.0.0.1:8080",
        )
    if "pnpm run dev" in command and "localhost:5173" in command:
        return _safe_web_server_oracle(
            start_command="pnpm run dev",
            url="http://localhost:5173",
            wait_seconds=180,
        )
    return None


def _safe_web_server_oracle(
    *,
    start_command: str,
    url: str,
    wait_seconds: int = 90,
) -> str:
    return f"""
set -eu
ulimit -n 1048576 2>/dev/null || ulimit -n 65535 2>/dev/null || true
log_file="$(mktemp /tmp/pheragent-web-oracle.XXXXXX)"
setsid sh -c {json.dumps(start_command)} >"$log_file" 2>&1 &
pid=$!
cleanup_web_child() {{
  pgid="$(ps -o pgid= "$pid" 2>/dev/null | tr -d ' ' || true)"
  if [ -n "$pgid" ]; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
  fi
  kill "$pid" 2>/dev/null || true
}}
trap cleanup_web_child EXIT INT TERM
ready=0
i=0
while [ "$i" -lt {wait_seconds} ]; do
  code="$(curl -s -o /dev/null -w "%{{http_code}}" {json.dumps(url)} || true)"
  if [ "$code" = "200" ]; then
    ready=1
    break
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    break
  fi
  sleep 1
  i=$((i + 1))
done
if [ "$ready" -eq 1 ]; then
  echo "Setup successful"
  rm -f "$log_file"
  exit 0
fi
cat "$log_file" || true
rm -f "$log_file"
echo "Setup failed"
exit 1
""".strip()


def _prometheus_oracle_replacement(command: str) -> str | None:
    if "localhost:9090/metrics" not in command or "prometheus_build_info" not in command:
        return None
    return """
set -eu
cd /workspace/repo
if [ -x ./prometheus ]; then
  prometheus_bin=./prometheus
else
  prometheus_bin=/tmp/pheragent-prometheus
  PATH="/usr/local/go/bin:/usr/lib/go-1.22/bin:/usr/lib/go/bin:$PATH" \
    GOFLAGS="${GOFLAGS:-} -buildvcs=false" \
    go build -o "$prometheus_bin" ./cmd/prometheus
fi
rm -rf /tmp/pheragent-prometheus-data
"$prometheus_bin" \
  --config.file=documentation/examples/prometheus.yml \
  --storage.tsdb.path=/tmp/pheragent-prometheus-data \
  --web.listen-address=127.0.0.1:9090 \
  >/tmp/pheragent-prometheus.log 2>&1 &
pid=$!
ready=0
i=0
while [ "$i" -lt 60 ]; do
  if curl -s http://127.0.0.1:9090/metrics | grep -q 'prometheus_build_info'; then
    ready=1
    break
  fi
  sleep 1
  i=$((i + 1))
done
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
if [ "$ready" -eq 1 ]; then
  echo "Setup successful"
  exit 0
fi
cat /tmp/pheragent-prometheus.log || true
echo "Setup failed"
exit 1
""".strip()


def _caddy_oracle_replacement(command: str) -> str | None:
    if "caddy list-modules" not in command or "Setup successful" not in command:
        return None
    return """
set -eu
cd /workspace/repo
export PATH="/usr/local/go/bin:/usr/lib/go-1.22/bin:/usr/lib/go/bin:$PATH"
export GOFLAGS="${GOFLAGS:-} -buildvcs=false"
if command -v caddy >/dev/null 2>&1; then
  caddy_bin="$(command -v caddy)"
elif [ -x ./caddy ]; then
  caddy_bin=./caddy
else
  caddy_bin=/tmp/pheragent-caddy
  go build -o "$caddy_bin" ./cmd/caddy
fi
if "$caddy_bin" list-modules | grep -q 'http'; then
  echo "Setup successful"
  exit 0
fi
echo "Setup failed"
exit 1
""".strip()
