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
    _response_text_input,
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
class RepairProbeCommand:
    title: str
    command: str


@dataclass(slots=True)
class OpenAIResponsesRepairConfig:
    model: str = "gpt-5.5"
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    base_url: str | None = None
    timeout: float = 120.0
    max_tokens: int = 2048
    max_retries: int = 3
    retry_delay_s: float = 1.0


class OpenAIResponsesRepairPlanner:
    def __init__(self, config: OpenAIResponsesRepairConfig):
        self.config = config
        self.last_raw_response: str | None = None
        self.last_parse_diagnostics: list[str] = []
        self.last_probe_raw_response: str | None = None
        self.last_probe_parse_diagnostics: list[str] = []

    def propose_probes(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> list[RepairProbeCommand]:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key in env var {self.config.api_key_env}")
        base_url = (self.config.base_url or os.getenv(self.config.base_url_env) or "").rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"

        self.last_probe_raw_response = None
        self.last_probe_parse_diagnostics = []
        content = self._create_response(
            _openai_client(base_url=base_url, api_key=api_key, timeout=self.config.timeout),
            self._probe_request_payload(
                block,
                result,
                context,
                heuristic_hints=heuristic_hints,
            ),
            error_context="LLM probe",
        )
        self.last_probe_raw_response = content
        return self._parse_probes(content)

    def suggest(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> list[RepairCommand]:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key in env var {self.config.api_key_env}")
        base_url = (self.config.base_url or os.getenv(self.config.base_url_env) or "").rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"

        self.last_raw_response = None
        self.last_parse_diagnostics = []
        content = self._create_response(
            _openai_client(base_url=base_url, api_key=api_key, timeout=self.config.timeout),
            self._request_payload(
                block,
                result,
                context,
                heuristic_hints=heuristic_hints,
            ),
            error_context="LLM repair",
        )
        self.last_raw_response = content
        return self._parse_repairs(content)

    def _request_payload(
        self,
        block: CommandBlock,
        result: CommandResult,
        context: RepairContext | None = None,
        *,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> dict[str, Any]:
        payload = self._failure_payload(
            block,
            result,
            context,
            heuristic_hints=heuristic_hints,
        )
        return {
            "model": self.config.model,
            "instructions": _REPAIR_SYSTEM_PROMPT,
            "input": _response_text_input(json.dumps(payload, ensure_ascii=False, indent=2)),
            "text": {"format": {"type": "json_object"}},
            "stream": True,
        }

    def _probe_request_payload(
        self,
        block: CommandBlock,
        result: CommandResult,
        context: RepairContext | None = None,
        *,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> dict[str, Any]:
        payload = self._failure_payload(
            block,
            result,
            context,
            heuristic_hints=heuristic_hints,
        )
        return {
            "model": self.config.model,
            "instructions": _PROBE_SYSTEM_PROMPT,
            "input": _response_text_input(json.dumps(payload, ensure_ascii=False, indent=2)),
            "text": {"format": {"type": "json_object"}},
            "stream": True,
        }

    def _failure_payload(
        self,
        block: CommandBlock,
        result: CommandResult,
        context: RepairContext | None = None,
        *,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "output_instructions": "Return JSON only.",
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
        if heuristic_hints:
            payload["heuristic_hints"] = [to_jsonable(hint) for hint in heuristic_hints]
        return payload

    def _create_response(
        self,
        client,
        payload: dict[str, Any],
        *,
        error_context: str,
    ) -> str:
        content = ""
        max_attempts = max(1, self.config.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                stream = client.responses.create(**payload)
                content = _read_streamed_response(stream, error_context=error_context)
                break
            except Exception as exc:
                last_error = RuntimeError(_format_llm_error(error_context, exc))
                if attempt == max_attempts:
                    raise last_error from exc
                if not _retryable_llm_error(exc):
                    raise last_error from exc
            _sleep_before_retry(attempt, self.config.retry_delay_s)
        else:
            raise RuntimeError(f"LLM repair request failed: {last_error}") from last_error

        return content

    def _parse_repairs(self, content: str) -> list[RepairCommand]:
        self.last_parse_diagnostics = []
        try:
            data = _parse_json_object(content)
        except Exception as exc:
            self.last_parse_diagnostics.append(f"parse_error: {exc}")
            raise
        raw_repairs = data.get("repairs")
        if raw_repairs is None and "command" in data:
            raw_repairs = [data]
        if not isinstance(raw_repairs, list):
            self.last_parse_diagnostics.append("missing or invalid repairs list")
            raise ValueError("LLM repair JSON must contain a repairs list")
        if not raw_repairs:
            self.last_parse_diagnostics.append("repairs list is empty")

        repairs: list[RepairCommand] = []
        for index, item in enumerate(raw_repairs):
            diagnostic_prefix = f"repairs[{index}]"
            if not isinstance(item, dict):
                self.last_parse_diagnostics.append(f"{diagnostic_prefix} is not an object")
                continue
            command = _optional_text(item.get("command"))
            patch_script = _optional_text(item.get("patch_script")) or command
            if not command or not patch_script:
                self.last_parse_diagnostics.append(
                    f"{diagnostic_prefix} missing command or patch_script"
                )
                continue
            command_rejection = _repair_command_rejection_reason(command)
            if command_rejection:
                self.last_parse_diagnostics.append(
                    f"{diagnostic_prefix}.command rejected: {command_rejection}"
                )
                continue
            patch_rejection = _repair_command_rejection_reason(patch_script)
            if patch_rejection:
                self.last_parse_diagnostics.append(
                    f"{diagnostic_prefix}.patch_script rejected: {patch_rejection}"
                )
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

    def _parse_probes(self, content: str) -> list[RepairProbeCommand]:
        self.last_probe_parse_diagnostics = []
        try:
            data = _parse_json_object(content)
        except Exception as exc:
            self.last_probe_parse_diagnostics.append(f"parse_error: {exc}")
            raise
        raw_probes = data.get("probes")
        if raw_probes is None and "command" in data:
            raw_probes = [data]
        if not isinstance(raw_probes, list):
            self.last_probe_parse_diagnostics.append("missing or invalid probes list")
            raise ValueError("LLM probe JSON must contain a probes list")
        if not raw_probes:
            self.last_probe_parse_diagnostics.append("probes list is empty")

        probes: list[RepairProbeCommand] = []
        for index, item in enumerate(raw_probes):
            diagnostic_prefix = f"probes[{index}]"
            if not isinstance(item, dict):
                self.last_probe_parse_diagnostics.append(f"{diagnostic_prefix} is not an object")
                continue
            command = _optional_text(item.get("command"))
            if not command:
                self.last_probe_parse_diagnostics.append(f"{diagnostic_prefix} missing command")
                continue
            rejection = _probe_command_rejection_reason(command)
            if rejection:
                self.last_probe_parse_diagnostics.append(
                    f"{diagnostic_prefix}.command rejected: {rejection}"
                )
                continue
            title = _optional_text(item.get("title")) or "LLM probe"
            probes.append(RepairProbeCommand(title=title, command=command))
        return _dedupe_probes(probes[:5])


class RepairPlanner:
    def __init__(self, llm_planner: OpenAIResponsesRepairPlanner | None = None):
        self.llm_planner = llm_planner
        self.last_llm_error: str | None = None
        self.last_llm_raw_response: str | None = None
        self.last_llm_parse_diagnostics: list[str] = []
        self.last_probe_error: str | None = None
        self.last_probe_raw_response: str | None = None
        self.last_probe_parse_diagnostics: list[str] = []

    def propose_probes(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
    ) -> list[RepairProbeCommand]:
        self.last_probe_error = None
        self.last_probe_raw_response = None
        self.last_probe_parse_diagnostics = []
        heuristic_hints = _heuristic_repair_hints(block, result)

        if self.llm_planner is None or not hasattr(self.llm_planner, "propose_probes"):
            return []

        try:
            probes = self.llm_planner.propose_probes(
                block,
                result,
                context=context,
                heuristic_hints=heuristic_hints,
            )
            self._capture_probe_debug()
            return _dedupe_probes(probes)
        except Exception as exc:
            self._capture_probe_debug()
            self.last_probe_error = str(exc)
            return []

    def suggest(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
    ) -> list[RepairCommand]:
        self.last_llm_error = None
        self.last_llm_raw_response = None
        self.last_llm_parse_diagnostics = []
        heuristic_hints = _heuristic_repair_hints(block, result)

        if self.llm_planner is not None:
            try:
                llm_suggestions = self.llm_planner.suggest(
                    block,
                    result,
                    context=context,
                    heuristic_hints=heuristic_hints,
                )
                self._capture_llm_debug()
                if llm_suggestions:
                    return _dedupe(llm_suggestions)
                self.last_llm_error = "LLM repair returned no usable suggestions"
            except Exception as exc:
                self._capture_llm_debug()
                self.last_llm_error = str(exc)

        return []

    def _capture_llm_debug(self) -> None:
        if self.llm_planner is None:
            return
        raw_response = getattr(self.llm_planner, "last_raw_response", None)
        diagnostics = getattr(self.llm_planner, "last_parse_diagnostics", [])
        self.last_llm_raw_response = raw_response if isinstance(raw_response, str) else None
        self.last_llm_parse_diagnostics = list(diagnostics or [])

    def _capture_probe_debug(self) -> None:
        if self.llm_planner is None:
            return
        raw_response = getattr(self.llm_planner, "last_probe_raw_response", None)
        diagnostics = getattr(self.llm_planner, "last_probe_parse_diagnostics", [])
        self.last_probe_raw_response = raw_response if isinstance(raw_response, str) else None
        self.last_probe_parse_diagnostics = list(diagnostics or [])

    def patch_block(self, block: CommandBlock, repair: RepairCommand) -> CommandBlock:
        if repair.patch_validation_command:
            block.validation_command = repair.patch_validation_command

        original = block.script
        if repair.patch_script and repair.patch_script not in original:
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
                block.script = shell_script(
                    f"{repair_header}\n{repair.patch_script}\n\n{original}"
                )
        block.repair_attempts += 1
        block.status = "repaired"
        return block


def _heuristic_repair_hints(block: CommandBlock, result: CommandResult) -> list[RepairCommand]:
    output = result.combined_output.lower()
    suggestions: list[RepairCommand] = []

    if any(token in output for token in ("gcc: not found", "cc: not found", "make: not found")):
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
    if _needs_qt_opencv_runtime_hint(output):
        suggestions.append(_qt_opencv_runtime_repair())
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
    if "ensurepip is not available" in output or "python3-venv" in output:
        command, patch_script = _python_venv_repair_command(output)
        suggestions.append(
            RepairCommand(
                title="Install Python venv package",
                command=command,
                patch_script=patch_script,
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
                )
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

    return suggestions


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


def _qt_opencv_runtime_repair() -> RepairCommand:
    packages = (
        "libgl1 libegl1 libxkbcommon0 libxcb-cursor0 libdbus-1-3 "
        "libfontconfig1 libxrender1 libxext6 libsm6"
    )
    command = (
        "if command -v apt-get >/dev/null 2>&1; then "
        "export DEBIAN_FRONTEND=noninteractive; apt-get update && "
        f"(apt-get install -y --no-install-recommends {packages} libglib2.0-0 || "
        f"apt-get install -y --no-install-recommends {packages} libglib2.0-0t64); "
        "else echo 'apt-get not available for repair' >&2; exit 127; fi"
    )
    return RepairCommand(
        title="Install Qt/OpenCV runtime libraries",
        command=command,
        patch_script=command,
    )


def _python_venv_repair_command(output: str) -> tuple[str, str]:
    package_match = re.search(r"apt\s+install\s+([a-z0-9.+-]+-venv)", output)
    package = package_match.group(1) if package_match else "python3-venv"
    if package != "python3-venv":
        install = (
            f"(apt-get install -y --no-install-recommends {package} || "
            "apt-get install -y --no-install-recommends python3-venv)"
        )
    else:
        install = "apt-get install -y --no-install-recommends python3-venv"
    patch_script = (
        "if command -v apt-get >/dev/null 2>&1; then "
        "export DEBIAN_FRONTEND=noninteractive; apt-get update && "
        f"{install}; "
        "else echo 'apt-get not available for repair' >&2; exit 127; fi"
    )
    command = (
        f"{patch_script} && "
        "rm -rf /tmp/pheragent-venv-check && "
        "python3 -m venv /tmp/pheragent-venv-check"
    )
    return command, patch_script


def _dedupe(suggestions: list[RepairCommand]) -> list[RepairCommand]:
    seen: set[str] = set()
    deduped: list[RepairCommand] = []
    for suggestion in suggestions:
        if suggestion.command in seen:
            continue
        seen.add(suggestion.command)
        deduped.append(suggestion)
    return deduped


def _dedupe_probes(probes: list[RepairProbeCommand]) -> list[RepairProbeCommand]:
    seen: set[str] = set()
    deduped: list[RepairProbeCommand] = []
    for probe in probes:
        if probe.command in seen:
            continue
        seen.add(probe.command)
        deduped.append(probe)
    return deduped


def _needs_qt_opencv_runtime_hint(output: str) -> bool:
    missing_runtime_tokens = (
        "libgl.so.1",
        "libegl.so.1",
        "libxkbcommon.so.0",
        "libglib-2.0.so.0",
        "libxcb-cursor",
    )
    package_tokens = ("pyside6", "pyqt", "qfluentwidgets", "opencv", "cv2")
    return any(token in output for token in missing_runtime_tokens) or (
        "cannot open shared object file" in output
        and any(token in output for token in package_tokens)
    )


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
    return _repair_command_rejection_reason(command) is None


def _probe_command_rejection_reason(command: str) -> str | None:
    if len(command) > 1000:
        return "command is too long"
    if "\n" in command or "\r" in command:
        return "multi-line commands are not allowed"
    repair_rejection = _repair_command_rejection_reason(command)
    if repair_rejection:
        return repair_rejection

    normalized = re.sub(r"\s+", " ", command.strip().lower())
    mutating_tokens = (
        "apt-get install",
        "apt install",
        "apt-get upgrade",
        "apt upgrade",
        "apt-get remove",
        "apt remove",
        "apk add",
        "yum install",
        "dnf install",
        "pip install",
        "pip3 install",
        "python -m pip install",
        "python3 -m pip install",
        "uv sync",
        "uv pip install",
        "poetry install",
        "pipenv install",
        "npm install",
        "npm i ",
        "pnpm install",
        "yarn install",
        "cargo install",
        "go install",
        "make install",
        "curl ",
        "wget ",
    )
    for token in mutating_tokens:
        if token in normalized:
            return f"mutating or network token {token!r}"
    return None


def _repair_command_rejection_reason(command: str) -> str | None:
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    dangerous_tokens = (
        "docker ",
        "podman ",
        "git push",
        "mkfs",
        "shutdown",
        "reboot",
        "poweroff",
        "dd if=",
        ">/dev/sd",
    )
    transient_runtime_paths = (
        "/tmp/pheragent/blocks/",
        "/tmp/pheragent/blocks",
    )
    test_monkeypatch_files = (
        "conftest.py",
        "sitecustomize.py",
    )
    for token in dangerous_tokens:
        if token in normalized:
            return f"unsafe token {token!r}"
    rm_rf_rejection = _rm_rf_rejection_reason(normalized)
    if rm_rf_rejection:
        return rm_rf_rejection
    for token in transient_runtime_paths:
        if token in normalized:
            return f"transient runtime path {token!r}"
    for token in test_monkeypatch_files:
        if token in normalized:
            return f"test monkeypatch file {token!r}"
    return None


def _rm_rf_rejection_reason(normalized_command: str) -> str | None:
    pattern = r"(?:^|[;&|]\s*)rm\s+(-[a-z]*[rf][a-z]*[rf][a-z]*)\s+([^;&|]+)"
    for match in re.finditer(pattern, normalized_command):
        targets = [target.strip().strip("\"'") for target in match.group(2).split()]
        for target in targets:
            if target in {"/", "/*"}:
                return f"unsafe rm target {target!r}"
            if _allowed_absolute_rm_target(target):
                continue
            if target.startswith("/"):
                return f"unsafe absolute rm target {target!r}"
    return None


def _allowed_absolute_rm_target(target: str) -> bool:
    if target.startswith("/var/lib/apt/lists/") or target == "/var/lib/apt/lists/*":
        return True
    if target.startswith("/tmp/") and target not in {"/tmp/", "/tmp/*"}:
        return True

    repo_prefix = "/workspace/repo/"
    if not target.startswith(repo_prefix):
        return False
    relative = target[len(repo_prefix) :].strip("/")
    if not relative or relative in {"*", "."}:
        return False
    safe_names = {
        ".cache",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "target",
    }
    first_part = relative.split("/", 1)[0]
    return first_part in safe_names


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
- Do not call /tmp/pheragent/blocks/*.sh or any other transient block script path.
  The orchestrator will copy and rerun the patched block script after a repair
  command succeeds.
- Make command validate only the repair itself from the failed block baseline
  (for example, install a missing package and run a small import/version check).
- Prefer package-manager fixes, missing tool installs, compatibility pins, and validation fixes.
- Do not edit application source, tests, conftest.py, or sitecustomize.py to make
  tests pass. If validation is running the full test suite and failures are
  application behavior, replace validation with a tool/import/pytest collect-only
  check instead.
- Keep each repair small enough to belong to the failed block.
- Analyze the failed block and failure stdout/stderr first; repair_context and
  heuristic_hints are supporting evidence, not a substitute for the error.
- Treat heuristic_hints as candidate clues for your analysis. They are not
  authoritative repairs; use or adapt them only when they actually match the
  failure and runtime context.
- Use repair_context to account for container OS/tools, previous successful blocks,
  and recent failures.
- If repair_context.probe_results are present, use them as observed container
  evidence for this failed block.
""".strip()


_PROBE_SYSTEM_PROMPT = """
You choose a few safe shell probes to gather missing context before repairing one
failed environment setup block inside an isolated Docker container.
Return strict JSON only:
{
  "probes": [
    {
      "title": "short title",
      "command": "single-line POSIX sh command"
    }
  ]
}

Rules:
- Return at most 5 probes. Return {"probes": []} if the failure is already clear.
- Probes must inspect only local repo/container state or run small validation checks.
- Do not install packages, sync dependencies, modify the repo, call network tools,
  start services, use docker/podman, or call /tmp/pheragent/blocks/*.sh.
- Prefer commands like ls, find with shallow depth, sed/head on manifests,
  python/node version checks, import checks, dpkg/apt-cache queries, and env probes.
- Keep each command single-line, deterministic, and fast.
- The orchestrator will run accepted probes from the failed block baseline and
  then ask for the actual repair command with probe_results included.
- The word JSON appears here intentionally because JSON mode requires an explicit JSON instruction.
""".strip()
