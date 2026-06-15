from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from .llm_planner import (
    _format_llm_error,
    _openai_client,
    _parse_json_object,
    _read_streamed_response,
    _retryable_llm_error,
    _sleep_before_retry,
)
from .models import CommandBlock, CommandResult, RepairContext, to_jsonable
from .utils import shell_script, tail_text


@dataclass(slots=True)
class RepairCommand:
    title: str
    command: str
    patch_script: str
    patch_validation_command: str | None = None


@dataclass(slots=True)
class OpenAIResponsesRepairConfig:
    model: str = "gpt-5.5"
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    base_url: str | None = None
    timeout: float = 120.0
    max_tokens: int = 2048
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay_s: float = 1.0


class OpenAIResponsesRepairPlanner:
    def __init__(self, config: OpenAIResponsesRepairConfig):
        self.config = config

    def suggest(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
    ) -> list[RepairCommand]:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key in env var {self.config.api_key_env}")
        base_url = (self.config.base_url or os.getenv(self.config.base_url_env) or "").rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"

        content = self._create_response(
            _openai_client(base_url=base_url, api_key=api_key, timeout=self.config.timeout),
            self._request_payload(block, result, context),
        )
        return self._parse_repairs(content)

    def _request_payload(
        self,
        block: CommandBlock,
        result: CommandResult,
        context: RepairContext | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "block": to_jsonable(block),
            "failure": {
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "stdout_tail": tail_text(result.stdout, max_chars=4000),
                "stderr_tail": tail_text(result.stderr, max_chars=4000),
            },
        }
        if context is not None:
            payload["repair_context"] = to_jsonable(context)
        return {
            "model": self.config.model,
            "instructions": _REPAIR_SYSTEM_PROMPT,
            "input": json.dumps(payload, ensure_ascii=False, indent=2),
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
            "text": {"format": {"type": "json_object"}},
            "stream": True,
        }

    def _create_response(
        self,
        client,
        payload: dict[str, Any],
    ) -> str:
        content = ""
        max_attempts = max(1, self.config.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                stream = client.responses.create(**payload)
                content = _read_streamed_response(stream, error_context="LLM repair")
                break
            except Exception as exc:
                last_error = RuntimeError(_format_llm_error("LLM repair", exc))
                if attempt == max_attempts:
                    raise last_error from exc
                if not _retryable_llm_error(exc):
                    raise last_error from exc
            _sleep_before_retry(attempt, self.config.retry_delay_s)
        else:
            raise RuntimeError(f"LLM repair request failed: {last_error}") from last_error

        return content

    def _parse_repairs(self, content: str) -> list[RepairCommand]:
        data = _parse_json_object(content)
        raw_repairs = data.get("repairs")
        if raw_repairs is None and "command" in data:
            raw_repairs = [data]
        if not isinstance(raw_repairs, list):
            raise ValueError("LLM repair JSON must contain a repairs list")

        repairs: list[RepairCommand] = []
        for item in raw_repairs:
            if not isinstance(item, dict):
                continue
            command = _optional_text(item.get("command"))
            patch_script = _optional_text(item.get("patch_script")) or command
            if not command or not patch_script:
                continue
            if not _safe_repair_command(command) or not _safe_repair_command(patch_script):
                continue
            title = _optional_text(item.get("title")) or "LLM repair"
            validation = _optional_text(
                item.get("patch_validation_command") or item.get("validation_command")
            )
            repairs.append(
                RepairCommand(
                    title=title,
                    command=command,
                    patch_script=patch_script,
                    patch_validation_command=validation,
                )
            )
        return _dedupe(repairs[:3])


class RepairPlanner:
    def __init__(self, llm_planner: OpenAIResponsesRepairPlanner | None = None):
        self.llm_planner = llm_planner
        self.last_llm_error: str | None = None

    def suggest(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
    ) -> list[RepairCommand]:
        self.last_llm_error = None
        output = result.combined_output.lower()
        suggestions: list[RepairCommand] = []

        if any(
            token in output for token in ("gcc: not found", "cc: not found", "make: not found")
        ):
            suggestions.append(_apt_repair("Install build-essential", "build-essential"))
        if any(token in output for token in ("python.h", "fatal error: python")):
            suggestions.append(_apt_repair("Install Python headers", "python3-dev build-essential"))
        if "pg_config executable not found" in output or "libpq-fe.h" in output:
            suggestions.append(_apt_repair("Install PostgreSQL headers", "libpq-dev"))
        if "mysql_config" in output or "mysql.h" in output:
            suggestions.append(_apt_repair("Install MySQL headers", "default-libmysqlclient-dev"))
        if "openssl/ssl.h" in output or "-lssl" in output:
            suggestions.append(_apt_repair("Install OpenSSL headers", "libssl-dev"))
        if "ffi.h" in output or "libffi" in output:
            suggestions.append(_apt_repair("Install libffi headers", "libffi-dev"))
        if "cargo: not found" in output and block.id.endswith("rust-deps"):
            suggestions.append(_apt_repair("Install Rust toolchain", "cargo rustc"))
        if "certificate verify failed" in output or "ca certificates" in output:
            suggestions.append(_apt_repair("Install CA certificates", "ca-certificates"))
        if "permission denied" in output and "gradlew" in output:
            suggestions.append(
                RepairCommand(
                    title="Make Gradle wrapper executable",
                    command="chmod +x ./gradlew",
                    patch_script="chmod +x ./gradlew",
                )
            )
        if "no module named pip" in output or "pip: not found" in output:
            suggestions.append(
                RepairCommand(
                    title="Bootstrap pip",
                    command=(
                        "python3 -m ensurepip --upgrade || python -m ensurepip --upgrade || "
                        "(apt-get update && apt-get install -y python3-pip)"
                    ),
                    patch_script=(
                        "python3 -m ensurepip --upgrade || python -m ensurepip --upgrade || "
                        "(apt-get update && apt-get install -y python3-pip)"
                    ),
                )
            )
        if "python: not found" in output or "python executable not found" in output:
            suggestions.append(
                RepairCommand(
                    title="Add python alias",
                    command=(
                        "if command -v python3 >/dev/null 2>&1 "
                        "&& ! command -v python >/dev/null 2>&1; then "
                        "ln -sf \"$(command -v python3)\" /usr/local/bin/python; fi"
                    ),
                    patch_script=(
                        "if command -v python3 >/dev/null 2>&1 "
                        "&& ! command -v python >/dev/null 2>&1; then "
                        "ln -sf \"$(command -v python3)\" /usr/local/bin/python; fi"
                    ),
                )
            )
        if "externally-managed-environment" in output or "pep 668" in output:
            suggestions.append(
                RepairCommand(
                    title="Install uv in an isolated tool venv",
                    command=_uv_tool_venv_command(),
                    patch_script=_uv_tool_venv_command(),
                )
            )
        if "pnpm" in output and "requires at least node.js" in output:
            suggestions.append(
                RepairCommand(
                    title="Install Node-compatible pnpm",
                    command=_node_compatible_pnpm_command(),
                    patch_script=_node_compatible_pnpm_command(),
                )
            )
        if "attributeerror" in output and "__version__" in output and block.validation_command:
            patched_validation = _strip_dunder_version_probe(block.validation_command)
            if patched_validation != block.validation_command:
                suggestions.append(
                    RepairCommand(
                        title="Relax __version__ validation probe",
                        command="true",
                        patch_script="",
                        patch_validation_command=patched_validation,
                    )
                )

        if self.llm_planner is not None:
            try:
                llm_suggestions = self.llm_planner.suggest(block, result, context=context)
                if llm_suggestions:
                    suggestions.extend(llm_suggestions)
                else:
                    self.last_llm_error = "LLM repair returned no usable suggestions"
            except Exception as exc:
                self.last_llm_error = str(exc)

        return _dedupe(suggestions)

    def patch_block(self, block: CommandBlock, repair: RepairCommand) -> CommandBlock:
        if repair.patch_validation_command:
            block.validation_command = repair.patch_validation_command
            block.repair_attempts += 1
            block.status = "repaired"
            return block

        original = block.script
        if repair.patch_script in original:
            return block
        repair_header = f'echo "[pheragent] repair: {repair.title}"'
        if original.startswith("#!/"):
            lines = original.splitlines()
            shebang = lines[0]
            rest = "\n".join(lines[1:]).lstrip()
            block.script = (
                f"{shebang}\nset -eu\n\n"
                f"{repair_header}\n{repair.patch_script}\n\n"
                f"{rest}\n"
            )
        else:
            block.script = shell_script(f"{repair_header}\n{repair.patch_script}\n\n{original}")
        block.repair_attempts += 1
        block.status = "repaired"
        return block


def make_repair_planner(
    *,
    mode: str,
    model: str | None,
    api_key_env: str,
    base_url_env: str,
    base_url: str | None,
    timeout: float,
    max_tokens: int,
    retries: int,
    retry_delay: float,
) -> RepairPlanner:
    if mode == "rules":
        return RepairPlanner()
    has_key = bool(os.getenv(api_key_env))
    if mode == "auto" and not has_key:
        return RepairPlanner()
    if mode not in {"auto", "llm"}:
        raise ValueError(f"unsupported planner mode for repair: {mode}")
    return RepairPlanner(
        llm_planner=OpenAIResponsesRepairPlanner(
            OpenAIResponsesRepairConfig(
                model=(
                    model
                    or os.getenv("PHERAGENT_MODEL")
                    or os.getenv("OPENAI_MODEL")
                    or "gpt-5.5"
                ),
                api_key_env=api_key_env,
                base_url_env=base_url_env,
                base_url=base_url,
                timeout=timeout,
                max_tokens=min(max_tokens, 2048),
                max_retries=retries,
                retry_delay_s=retry_delay,
            )
        )
    )


def _apt_repair(title: str, packages: str) -> RepairCommand:
    command = (
        "if command -v apt-get >/dev/null 2>&1; then "
        "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y "
        f"{packages}; "
        "else echo 'apt-get not available for repair' >&2; exit 127; fi"
    )
    return RepairCommand(title=title, command=command, patch_script=command)


def _dedupe(suggestions: list[RepairCommand]) -> list[RepairCommand]:
    seen: set[str] = set()
    deduped: list[RepairCommand] = []
    for suggestion in suggestions:
        if suggestion.command in seen:
            continue
        seen.add(suggestion.command)
        deduped.append(suggestion)
    return deduped


def _uv_tool_venv_command() -> str:
    return (
        "export PIP_BREAK_SYSTEM_PACKAGES=1 && "
        "if { ! python3 -m pip --version >/dev/null 2>&1 || "
        "! python3 -m venv -h >/dev/null 2>&1; } "
        "&& command -v apt-get >/dev/null 2>&1; then "
        "apt-get update && apt-get install -y python3-pip python3-venv; fi && "
        "python3 -m venv .pheragent-tools && "
        "./.pheragent-tools/bin/python -m pip install --upgrade pip && "
        "./.pheragent-tools/bin/python -m pip install uv && "
        "if [ -w /usr/local/bin ] || [ \"$(id -u)\" = \"0\" ]; then "
        "ln -sf /workspace/repo/.pheragent-tools/bin/uv /usr/local/bin/uv; "
        "else export PATH=\"/workspace/repo/.pheragent-tools/bin:$PATH\"; fi"
    )


def _node_compatible_pnpm_command() -> str:
    return (
        "if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then "
        "echo 'node/npm not available for pnpm repair' >&2; exit 127; fi && "
        "PNPM_PACKAGE=pnpm@9 && "
        "if node -e \"const [major, minor] = process.versions.node.split('.').map(Number); "
        "process.exit((major > 22 || (major === 22 && minor >= 13)) ? 0 : 1)\" "
        ">/dev/null 2>&1; then PNPM_PACKAGE=pnpm; fi && "
        "npm install -g \"$PNPM_PACKAGE\" && "
        "pnpm --version"
    )


def _strip_dunder_version_probe(command: str) -> str:
    patched = re.sub(r"print\(([A-Za-z_][A-Za-z0-9_]*)\.__version__\)", r"print(\1)", command)
    return re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\.__version__", r"\1", patched)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_repair_command(command: str) -> bool:
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    dangerous_tokens = (
        "docker ",
        "podman ",
        "git push",
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "shutdown",
        "reboot",
        "poweroff",
        "dd if=",
        ">/dev/sd",
    )
    return not any(token in normalized for token in dangerous_tokens)


_REPAIR_SYSTEM_PROMPT = """
You repair one failed environment setup block inside an isolated Docker container.
Return strict JSON only:
{
  "repairs": [
    {
      "title": "short title",
      "command": "shell command to test the repair from the block baseline",
      "patch_script": "shell snippet to prepend to the failed block script",
      "validation_command": "optional replacement validation command"
    }
  ]
}

Rules:
- Suggest local, idempotent shell commands only.
- Do not use docker, podman, git push, service shutdown, or destructive host commands.
- Prefer package-manager fixes, missing tool installs, compatibility pins, and validation fixes.
- Keep each repair small enough to belong to the failed block.
- Use repair_context to account for container OS/tools, previous successful blocks,
  and recent failures.
""".strip()
