from __future__ import annotations

import ast
import json
import os
import re
import shlex
from dataclasses import dataclass
from typing import Any

from .llm_planner import (
    _add_token_usage,
    _chat_completion_payload,
    _copy_token_usage,
    _create_chat_completion_with_usage,
    _empty_token_usage,
    _format_llm_error,
    _normalize_llm_api_mode,
    _openai_client,
    _parse_json_object,
    _read_streamed_response_with_usage,
    _resolve_openai_base_url,
    _responses_payload,
    _retryable_llm_error,
    _sleep_before_retry,
    merge_usage_summaries,
)
from .models import CommandBlock, CommandResult, LLMApiMode, RepairContext, to_jsonable
from .utils import normalize_posix_source, shell_script, tail_text


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
class FailureLocalization:
    root_cause_block_id: str
    rationale: str = ""


@dataclass(slots=True)
class OpenAIResponsesRepairConfig:
    model: str = "gpt-5.5"
    api_mode: LLMApiMode = "responses"
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
        self.config.api_mode = _normalize_llm_api_mode(self.config.api_mode)
        self.last_raw_response: str | None = None
        self.last_parse_diagnostics: list[str] = []
        self.last_probe_raw_response: str | None = None
        self.last_probe_parse_diagnostics: list[str] = []
        self.token_usage_by_phase = {
            "localization": _empty_token_usage(),
            "probe": _empty_token_usage(),
            "repair": _empty_token_usage(),
        }

    def localize_failure(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> FailureLocalization | None:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key in env var {self.config.api_key_env}")
        base_url = _resolve_openai_base_url(
            configured_base_url=self.config.base_url,
            base_url_env=self.config.base_url_env,
            api_mode=self.config.api_mode,
        )

        content = self._create_response(
            _openai_client(base_url=base_url, api_key=api_key, timeout=self.config.timeout),
            self._localization_request_payload(
                block,
                result,
                context,
                heuristic_hints=heuristic_hints,
            ),
            error_context="LLM failure localization",
            usage_phase="localization",
        )
        return self._parse_localization(content)

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
        base_url = _resolve_openai_base_url(
            configured_base_url=self.config.base_url,
            base_url_env=self.config.base_url_env,
            api_mode=self.config.api_mode,
        )

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
            usage_phase="probe",
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
        base_url = _resolve_openai_base_url(
            configured_base_url=self.config.base_url,
            base_url_env=self.config.base_url_env,
            api_mode=self.config.api_mode,
        )

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
            usage_phase="repair",
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
        user_text = json.dumps(payload, ensure_ascii=False, indent=2)
        if self.config.api_mode == "chat-completions":
            return _chat_completion_payload(self.config.model, _REPAIR_SYSTEM_PROMPT, user_text)
        return _responses_payload(self.config.model, _REPAIR_SYSTEM_PROMPT, user_text)

    def _localization_request_payload(
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
        user_text = json.dumps(payload, ensure_ascii=False, indent=2)
        if self.config.api_mode == "chat-completions":
            return _chat_completion_payload(
                self.config.model,
                _LOCALIZATION_SYSTEM_PROMPT,
                user_text,
            )
        return _responses_payload(self.config.model, _LOCALIZATION_SYSTEM_PROMPT, user_text)

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
        user_text = json.dumps(payload, ensure_ascii=False, indent=2)
        if self.config.api_mode == "chat-completions":
            return _chat_completion_payload(self.config.model, _PROBE_SYSTEM_PROMPT, user_text)
        return _responses_payload(self.config.model, _PROBE_SYSTEM_PROMPT, user_text)

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
        usage_phase: str,
    ) -> str:
        content = ""
        max_attempts = max(1, self.config.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                if self.config.api_mode == "chat-completions":
                    content, usage = _create_chat_completion_with_usage(
                        client,
                        payload,
                        error_context=error_context,
                    )
                else:
                    stream = client.responses.create(**payload)
                    content, usage = _read_streamed_response_with_usage(
                        stream,
                        error_context=error_context,
                    )
                _add_token_usage(self.token_usage_by_phase[usage_phase], usage)
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

    def usage_summary(self) -> dict[str, dict[str, int]]:
        summary = {
            phase: _copy_token_usage(usage)
            for phase, usage in self.token_usage_by_phase.items()
            if any(value for value in usage.values())
        }
        return merge_usage_summaries(summary)

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
            command_effect_rejection = _repair_command_effect_rejection_reason(command)
            if command_effect_rejection:
                self.last_parse_diagnostics.append(
                    f"{diagnostic_prefix}.command rejected: {command_effect_rejection}"
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
            validation = _sanitize_repair_validation_command(validation)
            repairs.append(
                RepairCommand(
                    title=title,
                    command=command,
                    patch_script=patch_script,
                    patch_validation_command=validation,
                )
            )
        return _dedupe(repairs[:3])

    def _parse_localization(self, content: str) -> FailureLocalization | None:
        data = _parse_json_object(content)
        root_cause_block_id = _optional_text(
            data.get("root_cause_block_id")
            or data.get("root_cause_block")
            or data.get("block_id")
        )
        if not root_cause_block_id:
            return None
        return FailureLocalization(
            root_cause_block_id=root_cause_block_id,
            rationale=_optional_text(data.get("rationale") or data.get("reason")) or "",
        )

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

    def localize_failure(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
    ) -> FailureLocalization | None:
        heuristic_hints = _heuristic_repair_hints(block, result)

        if self.llm_planner is not None and hasattr(self.llm_planner, "localize_failure"):
            try:
                localization = self.llm_planner.localize_failure(
                    block,
                    result,
                    context=context,
                    heuristic_hints=heuristic_hints,
                )
                if localization is not None:
                    return localization
            except Exception:
                pass

        return _heuristic_failure_localization(block, result, context)

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

    def usage_summary(self) -> dict[str, dict[str, int]]:
        if self.llm_planner is None:
            return {}
        usage_summary = getattr(self.llm_planner, "usage_summary", None)
        if not callable(usage_summary):
            return {}
        return usage_summary()

    def patch_block(self, block: CommandBlock, repair: RepairCommand) -> CommandBlock:
        if repair.patch_validation_command and _allow_validation_patch(block, repair):
            block.validation_command = repair.patch_validation_command

        original = normalize_posix_source(block.script)
        patch_script = normalize_posix_source(repair.patch_script)
        if patch_script:
            repair_header = f'echo "[pheragent] repair: {repair.title}"'
            patch_chunk = f"{repair_header}\n{patch_script}".strip()
        else:
            patch_chunk = ""
        if patch_script and not _repair_patch_is_leading(original, patch_chunk):
            if original.startswith("#!/"):
                lines = original.splitlines()
                shebang = lines[0]
                rest = "\n".join(lines[1:]).lstrip()
                block.script = (
                    f"{shebang}\nset -eu\n\n"
                    f"{patch_chunk}\n\n"
                    f"{rest}\n"
                )
            else:
                block.script = shell_script(f"{patch_chunk}\n\n{original}")
        else:
            block.script = original
        block.repair_attempts += 1
        block.status = "repaired"
        return block


def _repair_patch_is_leading(script: str, patch_chunk: str) -> bool:
    if not patch_chunk:
        return True
    lines = script.splitlines()
    if lines and lines[0].startswith("#!"):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    if lines and lines[0].strip() == "set -eu":
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines).lstrip().startswith(patch_chunk)


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
    if _needs_headless_gui_hint(output):
        suggestions.append(_headless_gui_runtime_repair())
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
                title="Use project virtualenv pip",
                command=_project_venv_pip_command(),
                patch_script=_project_venv_pip_command(),
            )
        )
    if (
        "no module named 'pluggy'" in output
        or 'no module named "pluggy"' in output
        or "no module named pytest" in output
        or "no module named 'pytest'" in output
    ):
        suggestions.append(
            RepairCommand(
                title="Repair pytest installation",
                command=_project_venv_pip_command(),
                patch_script=_project_venv_pip_command(),
            )
        )
    if "detected dubious ownership" in output or "safe.directory" in output:
        suggestions.append(
            RepairCommand(
                title="Trust container repo worktree",
                command="git config --global --add safe.directory /workspace/repo",
                patch_script="git config --global --add safe.directory /workspace/repo || true",
            )
        )
    if "has requirement setuptools<82" in output or (
        "setuptools" in output and "but you have setuptools" in output
    ):
        suggestions.append(_setuptools_upper_bound_repair())
    if "pnpm" in output and "requires at least node.js" in output:
        suggestions.append(
            RepairCommand(
                title="Install Node-compatible pnpm",
                command=_node_compatible_pnpm_command(),
                patch_script=_node_compatible_pnpm_command(),
            )
        )
    if "source: not found" in output:
        suggestions.append(
            RepairCommand(
                title="Use POSIX dot activation instead of source",
                command="true",
                patch_script="",
            )
        )
    if "no module named 'distutils'" in output or "no module named distutils" in output:
        suggestions.append(_setuptools_distutils_repair())
    if "pkgutil" in output and "impimporter" in output and "numpy" in output:
        suggestions.append(_python312_numpy_repair())
    if "no module named 'pkg_resources'" in output or "no module named pkg_resources" in output:
        suggestions.append(_setuptools_pkg_resources_repair())
    if (
        "opentelemetry.instrumentation.openai" in output
        or (
            "no module named 'openai'" in output
            and "opentelemetry.instrumentation.openai" in output
        )
    ):
        suggestions.append(_opentelemetry_openai_repair())
    if _looks_like_requirements_sanitizer_syntax_failure(output):
        suggestions.append(_requirements_sanitizer_repair())
    if "double requirement given" in output and "requirements.txt" in output:
        suggestions.append(_dedupe_requirements_repair())
    missing_module_repair = _missing_python_module_repair(output)
    if missing_module_repair is not None:
        suggestions.append(missing_module_repair)
    if block.validation_command and _pytest_collection_is_application_behavior(output):
        suggestions.append(
            RepairCommand(
                title="Relax pytest collection validation",
                command=_pytest_tooling_validation_command(),
                patch_script="",
                patch_validation_command=_pytest_tooling_validation_command(),
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
    if _looks_like_secret_placeholder_validation(output, block.validation_command):
        suggestions.append(
            RepairCommand(
                title="Relax placeholder secret validation",
                command="true",
                patch_script="",
                patch_validation_command=_generic_environment_validation_command(),
            )
        )

    return suggestions


def _heuristic_failure_localization(
    block: CommandBlock,
    result: CommandResult,
    context: RepairContext | None,
) -> FailureLocalization | None:
    if context is None or not context.previous_blocks:
        return FailureLocalization(block.id, "no previous successful block context")
    output = result.combined_output.lower()
    local_rationale = _failed_block_localization_rationale(block, output)
    if local_rationale:
        return FailureLocalization(block.id, local_rationale)
    candidates: list[tuple[tuple[str, ...], tuple[str, ...], str]] = [
        (
            ("python", "venv"),
            (
                "python: not found",
                "python3: not found",
                "python executable not found",
                "no module named pip",
                "ensurepip is not available",
            ),
            "python runtime/venv evidence matched the failure output",
        ),
        (
            ("node", "npm", "pnpm", "yarn"),
            ("node: not found", "npm: not found", "pnpm: not found", "yarn: not found"),
            "node runtime/dependency evidence matched the failure output",
        ),
        (
            ("go", "golang"),
            ("go: not found", "go.mod", "go version"),
            "go runtime/dependency evidence matched the failure output",
        ),
        (
            ("rust", "cargo"),
            ("cargo: not found", "rustc: not found"),
            "rust runtime/dependency evidence matched the failure output",
        ),
        (
            ("java", "maven", "gradle"),
            ("java: not found", "mvn: not found", "gradle: not found", "gradlew"),
            "java runtime/dependency evidence matched the failure output",
        ),
        (
            ("system", "native", "build-config"),
            (
                "gcc: not found",
                "cc: not found",
                "make: not found",
                "pkg-config: not found",
                "cannot open shared object file",
                "libgl.so.1",
                "libegl.so.1",
                "libglib-2.0.so.0",
            ),
            "system/native build evidence matched the failure output",
        ),
    ]
    for block_tokens, output_tokens, rationale in candidates:
        if not any(token in output for token in output_tokens):
            continue
        localized = _latest_previous_block_matching(context.previous_blocks, block_tokens)
        if localized is not None:
            return FailureLocalization(localized.id, rationale)
    return FailureLocalization(block.id, "failure appears local to the failed block")


def _failed_block_localization_rationale(block: CommandBlock, output: str) -> str | None:
    block_text = f"{block.id} {block.title} {block.goal}".lower()
    test_tooling_block = any(
        token in block_text for token in ("test", "tool", "validation", "prep")
    )
    if (
        ("unrecognized arguments" in output and "--collect-only" in output)
        or ("systemexit: 2" in output and "--collect-only" in output)
    ):
        return "pytest collection triggered project CLI argument parsing in the failed block"

    local_test_modules = (
        "no module named pytest",
        "no module named 'pytest'",
        "no module named pluggy",
        "no module named 'pluggy'",
        "no module named pytest_mock",
        "no module named 'pytest_mock'",
    )
    if test_tooling_block and any(token in output for token in local_test_modules):
        return "test tooling dependency is missing in the failed test/tooling block"

    return None


def _latest_previous_block_matching(
    previous_blocks: list[CommandBlock],
    tokens: tuple[str, ...],
) -> CommandBlock | None:
    for previous in reversed(previous_blocks):
        haystack = f"{previous.id} {previous.title} {previous.goal}".lower()
        if any(token in haystack for token in tokens):
            return previous
    return None


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
    api_mode: str = "responses",
) -> RepairPlanner:
    if mode == "rules":
        return RepairPlanner()
    has_key = bool(os.getenv(api_key_env))
    if mode == "auto" and not has_key:
        return RepairPlanner()
    if mode not in {"auto", "llm"}:
        raise ValueError(f"unsupported planner mode for repair: {mode}")
    normalized_api_mode = _normalize_llm_api_mode(api_mode)
    return RepairPlanner(
        llm_planner=OpenAIResponsesRepairPlanner(
            OpenAIResponsesRepairConfig(
                model=(
                    model
                    or os.getenv("PHERAGENT_MODEL")
                    or os.getenv("OPENAI_MODEL")
                    or "gpt-5.5"
                ),
                api_mode=normalized_api_mode,
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


def _headless_gui_runtime_repair() -> RepairCommand:
    command = """if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends xvfb xauth libx11-6 libxcb1 libxext6 libxrender1
else
  echo 'apt-get not available for repair' >&2
  exit 127
fi
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export MPLBACKEND="${MPLBACKEND:-Agg}"
export XAUTHORITY="${XAUTHORITY:-/tmp/pheragent-empty-xauthority}"
touch "$XAUTHORITY"
if [ -z "${DISPLAY:-}" ]; then
  export DISPLAY=:99
fi
if command -v Xvfb >/dev/null 2>&1; then
  Xvfb "$DISPLAY" -screen 0 1280x1024x24 >/tmp/pheragent-xvfb.log 2>&1 &
  sleep 1
fi
if [ -x ./.venv/bin/python ]; then
  ./.venv/bin/python - <<'PY'
import os
print(os.environ.get("DISPLAY", ""))
PY
else
  python3 - <<'PY'
import os
print(os.environ.get("DISPLAY", ""))
PY
fi"""
    return RepairCommand(
        title="Install headless GUI runtime",
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


def _needs_headless_gui_hint(output: str) -> bool:
    markers = (
        ".xauthority",
        "xauthority",
        "could not connect to display",
        "couldn't connect to display",
        "cannot connect to x server",
        "no display name and no $display",
        "xlib.error.displayconnectionerror",
        "qt.qpa.xcb",
    )
    return any(marker in output for marker in markers)


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


def _project_venv_pip_command() -> str:
    return (
        "cd /workspace/repo && "
        "if [ ! -x .venv/bin/python ]; then rm -rf .venv && python3 -m venv .venv; fi && "
        "./.venv/bin/python -m pip --version >/dev/null 2>&1 || "
        "./.venv/bin/python -m ensurepip --upgrade || true; "
        "./.venv/bin/python -m pip install --upgrade "
        "pip 'setuptools>=68.2,<82' wheel pytest pluggy iniconfig packaging && "
        "./.venv/bin/python -m pytest --version"
    )


def _setuptools_upper_bound_repair() -> RepairCommand:
    command = (
        "cd /workspace/repo && "
        "./.venv/bin/python -m pip install --upgrade 'setuptools>=68.2,<82' wheel && "
        "./.venv/bin/python -m pip --version"
    )
    return RepairCommand(
        title="Use dependency-compatible setuptools",
        command=command,
        patch_script="./.venv/bin/python -m pip install --upgrade 'setuptools>=68.2,<82' wheel",
    )


def _setuptools_pkg_resources_repair() -> RepairCommand:
    command = (
        "cd /workspace/repo && "
        "./.venv/bin/python -m pip install --upgrade 'setuptools<82' wheel && "
        "./.venv/bin/python -c \"import pkg_resources; print(pkg_resources.__name__)\""
    )
    return RepairCommand(
        title="Install setuptools pkg_resources",
        command=command,
        patch_script=command,
    )


def _setuptools_distutils_repair() -> RepairCommand:
    command = (
        "cd /workspace/repo && "
        "export SETUPTOOLS_USE_DISTUTILS=local && "
        "./.venv/bin/python -m pip install --upgrade 'setuptools<82' wheel && "
        "./.venv/bin/python -c \"import setuptools, distutils.filelist; "
        "print(setuptools.__version__)\""
    )
    patch_script = (
        "export SETUPTOOLS_USE_DISTUTILS=local\n"
        "./.venv/bin/python -m pip install --upgrade 'setuptools<82' wheel"
    )
    return RepairCommand(
        title="Use setuptools vendored distutils",
        command=command,
        patch_script=patch_script,
    )


def _python312_numpy_repair() -> RepairCommand:
    command = (
        "cd /workspace/repo && "
        "./.venv/bin/python -m pip install --upgrade 'setuptools<82' wheel && "
        "./.venv/bin/python -m pip install 'numpy>=1.26,<2' && "
        "./.venv/bin/python -c \"import numpy; print(numpy.__version__)\""
    )
    return RepairCommand(
        title="Install Python 3.12 compatible numpy",
        command=command,
        patch_script=command,
    )


def _opentelemetry_openai_repair() -> RepairCommand:
    command = (
        "cd /workspace/repo && "
        "./.venv/bin/python -m pip install openai opentelemetry-instrumentation-openai && "
        "./.venv/bin/python -c \"import openai; "
        "from opentelemetry.instrumentation.openai import OpenAIInstrumentor; "
        "print(OpenAIInstrumentor)\""
    )
    return RepairCommand(
        title="Install OpenTelemetry OpenAI extras",
        command=command,
        patch_script=command,
    )


_IMPORT_TO_PIP_PACKAGE = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python-headless",
    "crypto": "pycryptodome",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "google.protobuf": "protobuf",
    "grpc": "grpcio",
    "jwt": "PyJWT",
    "langfuse.decorators": "langfuse",
    "opentelemetry.instrumentation.openai": "opentelemetry-instrumentation-openai",
    "pil": "Pillow",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
}

_SAME_NAME_PYPI_IMPORTS = {
    "aiohttp",
    "click",
    "fastapi",
    "httpx",
    "jinja2",
    "langfuse",
    "msgpack",
    "numpy",
    "pandas",
    "pluggy",
    "psutil",
    "pydantic",
    "pytest",
    "pytest_asyncio",
    "pytest_mock",
    "requests",
    "rich",
    "tenacity",
    "torch",
    "transformers",
    "typer",
    "uvicorn",
}


def _missing_python_module_repair(output: str) -> RepairCommand | None:
    modules = _missing_python_modules(output)
    if not modules:
        return None
    packages: list[str] = []
    imports_to_check: list[str] = []
    for module in modules:
        package = _pip_package_for_import(module)
        if package is None:
            continue
        packages.append(package)
        imports_to_check.append(module)
    if not packages:
        return None
    packages = _dedupe_text(packages)
    imports_to_check = _dedupe_text(imports_to_check)
    install_args = " ".join(shlex.quote(package) for package in packages)
    import_json = json.dumps(imports_to_check)
    command = f"""cd /workspace/repo
test -x ./.venv/bin/python
./.venv/bin/python -m pip install --upgrade {install_args}
./.venv/bin/python - <<'PY'
import importlib

for module in {import_json}:
    importlib.import_module(module)
    print(module)
PY"""
    return RepairCommand(
        title="Install missing Python modules",
        command=command,
        patch_script=command,
    )


def _missing_python_modules(output: str) -> list[str]:
    modules: list[str] = []
    patterns = (
        r"(?:modulenotfounderror|importerror):\s+no module named ['\"]?([a-z0-9_.-]+)",
        r"(?:^|\n)[^\n]*python[^\n:]*:\s+no module named ['\"]?([a-z0-9_.-]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, output):
            module = match.group(1).strip(" .'\"")
            if _safe_import_name(module):
                modules.append(module)
    return _dedupe_text(modules)


def _pip_package_for_import(module: str) -> str | None:
    normalized = module.lower().replace("-", "_")
    if normalized in _IMPORT_TO_PIP_PACKAGE:
        return _IMPORT_TO_PIP_PACKAGE[normalized]
    top_level = normalized.split(".", 1)[0]
    if top_level in _IMPORT_TO_PIP_PACKAGE:
        return _IMPORT_TO_PIP_PACKAGE[top_level]
    if normalized in _SAME_NAME_PYPI_IMPORTS:
        return normalized.replace("_", "-")
    if top_level in _SAME_NAME_PYPI_IMPORTS:
        return top_level.replace("_", "-")
    return None


def _safe_import_name(module: str) -> bool:
    return bool(re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*", module))


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _requirements_sanitizer_repair() -> RepairCommand:
    command = _requirements_sanitizer_repair_script()
    return RepairCommand(
        title="Install sanitized requirements with heredoc script",
        command=command,
        patch_script=command,
    )


def _requirements_sanitizer_repair_script() -> str:
    return """cd /workspace/repo
test -x .venv/bin/python
if [ -f requirements.txt ]; then
  sanitized_file=/tmp/pheragent-requirements-sanitized.txt
  PHERAGENT_SKIP_CUDA_DEPS=0
  if [ -z "${CUDA_HOME:-}" ] && ! command -v nvcc >/dev/null 2>&1; then
    PHERAGENT_SKIP_CUDA_DEPS=1
  fi
  export PHERAGENT_SKIP_CUDA_DEPS
  ./.venv/bin/python - requirements.txt > "$sanitized_file" <<'PY'
import os
import re
import sys
from pathlib import Path

source = Path(sys.argv[1])
skip_cuda_deps = os.environ.get("PHERAGENT_SKIP_CUDA_DEPS") == "1"
cuda_source_packages = {
    "apex",
    "bitsandbytes",
    "causal-conv1d",
    "deepspeed",
    "flash-attn",
    "flash-attention",
    "flashattention",
    "mamba-ssm",
    "vllm",
    "xformers",
}
for raw in source.read_text(encoding="utf-8").splitlines():
    stripped = raw.strip()
    if not stripped or stripped.startswith("#"):
        print(raw)
        continue
    passthrough = ("-r ", "--requirement", "-c ", "--constraint", "-e ", "--editable")
    if stripped.startswith(passthrough):
        print(raw)
        continue
    name = re.split(r"\\s*(?:===|==|~=|!=|<=|>=|<|>|;)", stripped, 1)[0]
    name = name.split("[", 1)[0].strip().lower().replace("_", "-")
    if skip_cuda_deps and name in cuda_source_packages:
        print(f"[pheragent] skipped {name} because CUDA/nvcc is unavailable", file=sys.stderr)
        continue
    if (
        sys.version_info >= (3, 12)
        and name == "numpy"
        and re.search(r"(?:<|<=)\\s*1\\.2[0-3](?:\\.|$)", stripped)
    ):
        print("numpy>=1.26,<2")
        print("[pheragent] relaxed numpy<1.24 requirement for Python 3.12", file=sys.stderr)
        continue
    print(raw)
PY
  ./.venv/bin/python -m pip install -r "$sanitized_file"
else
  echo "requirements.txt not found" >&2
  exit 1
fi"""


def _pytest_tooling_validation_command() -> str:
    return "./.venv/bin/python -m pytest --version"


def _pytest_collect_only_validation_command() -> str:
    return (
        "cd /workspace/repo && ( "
        "test -x .venv/bin/python; "
        "./.venv/bin/python -m pytest --collect-only -q; "
        "status=$?; "
        'if [ "$status" -eq 5 ]; then '
        'echo "[pheragent] no pytest tests collected"; exit 0; '
        "fi; "
        'exit "$status"'
        " )"
    )


def _sanitize_repair_validation_command(command: str | None) -> str | None:
    if command is None:
        return None
    if "pip check" in command.lower():
        return _pytest_collect_only_validation_command()
    return command


def _pytest_collection_is_application_behavior(output: str) -> bool:
    markers = (
        "importerror while loading conftest",
        "unrecognized arguments: --collect-only",
        "systemexit: 2",
        "is not a fixture",
    )
    return any(marker in output for marker in markers)


def _looks_like_requirements_sanitizer_syntax_failure(output: str) -> bool:
    if "syntaxerror" not in output:
        return False
    markers = (
        "requirements sanit",
        "sanitize_requirements",
        "requirements_sanit",
        "pheragent-requirements-sanitized",
        "invalid syntax in python requirements",
        ". = path",
    )
    return any(marker in output for marker in markers)


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


def _dedupe_requirements_repair() -> RepairCommand:
    command = (
        "if [ -f requirements.txt ]; then "
        "python3 - <<'PY' > /tmp/pheragent-requirements.dedup.txt\n"
        "import re\n"
        "from pathlib import Path\n"
        "seen = set()\n"
        "for raw in Path('requirements.txt').read_text().splitlines():\n"
        "    line = raw.strip()\n"
        "    if not line or line.startswith('#'):\n"
        "        print(raw)\n"
        "        continue\n"
        "    passthrough = ('-r ', '--requirement', '-c ', '--constraint', '-e ', '--editable')\n"
        "    if line.startswith(passthrough):\n"
        "        print(raw)\n"
        "        continue\n"
        "    name = re.split(r'\\s*(?:===|==|~=|!=|<=|>=|<|>|;)', line, 1)[0]\n"
        "    name = name.split('[', 1)[0].strip().lower().replace('_', '-')\n"
        "    if name and name in seen:\n"
        "        continue\n"
        "    if name:\n"
        "        seen.add(name)\n"
        "    print(raw)\n"
        "PY\n"
        "./.venv/bin/python -m pip install -r /tmp/pheragent-requirements.dedup.txt; "
        "else echo 'requirements.txt not found' >&2; exit 1; fi"
    )
    return RepairCommand(
        title="Install deduplicated requirements copy",
        command=command,
        patch_script=command,
    )


def _looks_like_secret_placeholder_validation(
    output: str,
    validation_command: str | None,
) -> bool:
    haystack = f"{output}\n{validation_command or ''}".lower()
    return any(
        token in haystack
        for token in (
            "your_openai_api_key",
            "your-openai-api-key",
            "openai_api_key_here",
            "api key here",
            "api_key ==",
            "openai_api_key ==",
        )
    )


def _generic_environment_validation_command() -> str:
    return (
        "cd /workspace/repo && "
        "if [ -x .venv/bin/python ]; then ./.venv/bin/python -m pip --version >/dev/null 2>&1; "
        "elif command -v python3 >/dev/null 2>&1; then python3 --version >/dev/null 2>&1; fi; "
        "if [ -f package.json ] && command -v node >/dev/null 2>&1; then "
        "node --version >/dev/null 2>&1; fi"
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
    for token in dangerous_tokens:
        if token in normalized:
            return f"unsafe token {token!r}"
    python_inline_rejection = _python_inline_rejection_reason(command)
    if python_inline_rejection:
        return python_inline_rejection
    python_heredoc_rejection = _python_heredoc_rejection_reason(command)
    if python_heredoc_rejection:
        return python_heredoc_rejection
    python_heredoc_syntax_rejection = _python_heredoc_syntax_rejection_reason(command)
    if python_heredoc_syntax_rejection:
        return python_heredoc_syntax_rejection
    setuptools_rejection = _setuptools_pin_rejection_reason(normalized)
    if setuptools_rejection:
        return setuptools_rejection
    rm_rf_rejection = _rm_rf_rejection_reason(normalized)
    if rm_rf_rejection:
        return rm_rf_rejection
    tmp_requirements_rejection = _tmp_requirements_artifact_rejection_reason(command)
    if tmp_requirements_rejection:
        return tmp_requirements_rejection
    for token in transient_runtime_paths:
        if token in normalized:
            return f"transient runtime path {token!r}"
    repo_modification = _repo_code_modification_rejection_reason(normalized)
    if repo_modification:
        return repo_modification
    return None


def _python_inline_rejection_reason(command: str) -> str | None:
    normalized = re.sub(r"\s+", " ", command.strip())
    lower = normalized.lower()
    if not re.search(r"(?:^|\s)(?:\.?/?[\w./-]*python3?|python3?)\s+-c\s+", lower):
        return None
    compound_after_semicolon = (
        r";\s*(?:async\s+)?(?:for|while|if|with|try|except|finally|def|class)\b"
    )
    if re.search(compound_after_semicolon, normalized):
        return "compound Python statement in python -c one-liner"
    starts_with_compound = (
        r"(?:python3?|\.?/?[\w./-]*python3?)\s+-c\s+[\"']\s*"
        r"(?:async\s+)?(?:for|while|if|with|try|def|class)\b"
    )
    if re.search(starts_with_compound, lower):
        return "compound Python statement in python -c one-liner"
    return None


def _python_heredoc_rejection_reason(command: str) -> str | None:
    stripped = command.strip()
    if not re.search(r"(?:^|\s)(?:\.?/?[\w./-]*python3?|python3?)\s+-", stripped):
        return None
    if "<<'PY'" not in stripped and '<<"PY"' not in stripped and "<<PY" not in stripped:
        return None
    if re.search(r"(?m)^PY[ \t]+\S+", stripped):
        return "arguments after Python heredoc terminator"
    return None


def _python_heredoc_syntax_rejection_reason(command: str) -> str | None:
    if not _uses_python_heredoc(command):
        return None
    marker_match = re.search(r"<<(?:(?:'PY')|(?:\"PY\")|PY)\n", command)
    if marker_match is None:
        return None
    terminator_match = re.search(r"(?m)^PY\s*$", command[marker_match.end() :])
    if terminator_match is None:
        return "unterminated Python heredoc"
    snippet = command[
        marker_match.end() : marker_match.end() + terminator_match.start()
    ]
    try:
        ast.parse(snippet, filename="<repair-python-heredoc>", mode="exec")
    except SyntaxError as exc:
        return f"invalid Python heredoc syntax: {exc.msg}"
    return None


def _setuptools_pin_rejection_reason(normalized_command: str) -> str | None:
    too_old_exact = re.search(r"setuptools\s*={2,3}\s*(\d+)(?:[.\s'\"]|$)", normalized_command)
    if too_old_exact and int(too_old_exact.group(1)) < 68:
        return "setuptools pin is too old for Python 3.12"
    too_old_upper = re.search(r"setuptools\s*<\s*(\d+)(?:[.\s'\"]|$)", normalized_command)
    if too_old_upper and int(too_old_upper.group(1)) <= 68:
        return "setuptools upper bound is too old for Python 3.12"
    return None


def _repair_command_effect_rejection_reason(command: str) -> str | None:
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    if not normalized:
        return "empty command"

    repair_tokens = (
        "apt-get install",
        "apt install",
        "apk add",
        "dnf install",
        "yum install",
        "pip install",
        "pip3 install",
        "python -m pip install",
        "python3 -m pip install",
        ".venv/bin/python -m pip install",
        "./.venv/bin/python -m pip install",
        "uv sync",
        "uv pip install",
        "poetry install",
        "pipenv install",
        "npm install",
        "npm i ",
        "pnpm install",
        "yarn install",
        "cargo fetch",
        "cargo install",
        "go mod download",
        "go install",
        "chmod ",
        "ln -s",
        "ln -sf",
        "rm -rf .venv",
        "python3 -m venv",
        "python -m venv",
        "mkdir ",
        "touch ",
        "export ",
    )
    if any(token in normalized for token in repair_tokens):
        return None
    if _uses_python_heredoc(command):
        return "python heredoc repair command does not include a durable state-changing action"

    diagnostic_patterns = (
        r"^(?:sudo\s+)?dpkg-query\b",
        r"^(?:sudo\s+)?dpkg\s+-[ls]\b",
        r"^(?:sudo\s+)?apt-cache\b",
        r"^(?:sudo\s+)?command\s+-v\b",
        r"^(?:sudo\s+)?which\b",
        r"^(?:sudo\s+)?whereis\b",
        r"^(?:sudo\s+)?type\b",
        r"^(?:sudo\s+)?test\b",
        r"^(?:sudo\s+)?ls\b",
        r"^(?:sudo\s+)?cat\b",
        r"^(?:sudo\s+)?echo\b",
        r"^(?:sudo\s+)?python(?:3)?\s+--version\b",
        r"^(?:sudo\s+)?(?:\.?/?[\w./-]*python3?|python3?)\s+-c\b",
        r"^(?:sudo\s+)?node\s+--version\b",
        r"^(?:sudo\s+)?npm\s+--version\b",
        r"^(?:sudo\s+)?pip(?:3)?\s+--version\b",
    )
    if any(re.search(pattern, normalized) for pattern in diagnostic_patterns):
        return "repair command is a pure diagnostic/probe command"
    return None


def _uses_python_heredoc(command: str) -> bool:
    return bool(
        re.search(
            r"(?:^|\s)(?:\.?/?[\w./-]*python3?|python3?)\s+-[^\n]*<<(?:(?:'PY')|(?:\"PY\")|PY)",
            command,
        )
    )


def _tmp_requirements_artifact_rejection_reason(command: str) -> str | None:
    match = re.search(
        r"(?:\S+\s+-m\s+)?pip(?:3)?\s+install(?:\s+[^;\n]*)?\s+-r\s+"
        r"(/tmp/[^\s;&|]+(?:requirements|sanitized)[^\s;&|]*)",
        command,
        re.IGNORECASE,
    )
    if not match:
        return None
    target = match.group(1)
    if _tmp_artifact_created_in_command(command, target):
        return None
    return f"transient requirements artifact {target!r} is not created in the same command"


def _tmp_artifact_created_in_command(command: str, target: str) -> bool:
    escaped = re.escape(target)
    creator_patterns = (
        rf">\s*(?:['\"]?{escaped}['\"]?|\$[A-Za-z_][A-Za-z0-9_]*)",
        rf"\b(?:tee|cp|mv)\b[^\n]*\s{escaped}(?:\s|$)",
        rf"\b(?:cat|printf|echo)\b[^\n]*>\s*['\"]?{escaped}['\"]?",
        rf"\b(?:rm\s+-rf|mkdir\s+-p)\b[^\n]*{escaped}",
    )
    return any(re.search(pattern, command) for pattern in creator_patterns)


def _allow_validation_patch(block: CommandBlock, repair: RepairCommand) -> bool:
    if repair.patch_validation_command is None:
        return False
    block_text = f"{block.id} {block.title} {block.goal}".lower()
    python_dependency_block = (
        "python" in block_text and "dep" in block_text
    ) or ("language" in block_text and "dep" in block_text)
    if not python_dependency_block:
        return True
    return repair.command.strip() == "true" and not repair.patch_script.strip()


def _repo_code_modification_rejection_reason(normalized_command: str) -> str | None:
    for token in ("conftest.py", "sitecustomize.py"):
        if token in normalized_command:
            return f"test monkeypatch file {token!r}"
    for token in (".write_text(", ".write_bytes(", "open("):
        if token in normalized_command:
            return f"python file write token {token!r}"
    if re.search(r"\b(?:sed\s+-i|perl\s+-pi)\b", normalized_command):
        return "in-place source edit command"
    if re.search(r"(?:^|[;&|]\s*)patch\b", normalized_command):
        return "source patch command"
    if re.search(
        r"(?:^|[;&|]\s*)touch\s+(?:/workspace/repo/)?"
        r"[^;&|\s]+\.(?:py|pyi|js|jsx|ts|tsx|java|go|rs|c|cc|cpp|h|hpp|rb|php|sh)",
        normalized_command,
    ):
        return "touch source-like file"
    if re.search(
        r"(?:^|[;&|]\s*)(?:cat|tee|echo|printf)\b[^;&|>]*>\s*(?:/workspace/repo/)?"
        r"[^;&|\s]+\.(?:py|pyi|js|jsx|ts|tsx|java|go|rs|c|cc|cpp|h|hpp|rb|php|sh)",
        normalized_command,
    ):
        return "redirect writes to source-like file"
    if re.search(
        r"(?:^|[;&|]\s*)(?:cp|mv)\b[^;&|]*\s+(?:/workspace/repo/)?"
        r"[^;&|\s]+\.(?:py|pyi|js|jsx|ts|tsx|java|go|rs|c|cc|cpp|h|hpp|rb|php|sh)",
        normalized_command,
    ):
        return "copy or move to source-like file"
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


_LOCALIZATION_SYSTEM_PROMPT = """
You localize the root-cause block for one failed environment setup block.
Return strict JSON only:
{
  "root_cause_block_id": "one block id from repair_context.previous_blocks or the failed block id",
  "rationale": "short reason"
}

Rules:
- The failed block is where the symptom appeared. It may not be the block that
  introduced the faulty state.
- Be conservative. Return an earlier block only when the logs strongly show
  that earlier block introduced the faulty environment state. If evidence is
  ambiguous, keep the failed block.
- Use the failed block, stdout/stderr tails, previous successful blocks, recent
  execution evidence, probe results, and heuristic hints.
- If an earlier runtime, system package, dependency, native-build, or tooling
  block should have produced the missing or inconsistent resource, return that
  earlier block id.
- Missing GUI/OpenCV/Qt shared libraries such as libGL.so.1, libEGL.so.1, or
  libglib-2.0.so.0 are OS/runtime-library issues, not Python-runtime issues.
  Select an earlier system/native package block only if one clearly owns OS
  packages; otherwise keep the failed validation/test-tooling block.
- If pytest collection triggers the project CLI (for example SystemExit: 2 or
  "unrecognized arguments: --collect-only"), keep the failed validation or
  test-tooling block. This is a validation/tooling adjustment, not an earlier
  dependency/runtime rollback.
- Missing pytest, pluggy, pytest-mock, or similar test-tooling modules in a
  validation/test-prep block should usually stay with that failed block unless
  a previous block explicitly owned test-tool installation and the evidence is
  unambiguous.
- If the evidence is weak or the failure is local to the failed block, return
  the failed block id.
- Never invent block ids. Choose only from repair_context.previous_blocks plus
  the failed block.
- Do not suggest repair commands here; only localize the root-cause block.
- The word JSON appears here intentionally because JSON mode requires an explicit JSON instruction.
""".strip()


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
- command may include checks or validation, but it must not be only a probe.
  Pure diagnostic commands such as dpkg-query, command -v, which, --version
  checks, ls, cat, test, or echo belong in probes, not repairs. A repair command
  should include a state-changing fix, such as apt-get install, venv creation,
  symlink repair, chmod, or environment setup. For missing Debian/Ubuntu
  packages, use apt-get update followed by apt-get install -y
  --no-install-recommends for the required packages.
- patch_script must be the persistent, replayable form of the successful repair.
  If command installs a package, exports an environment variable, changes pip
  flags, or replaces validation assumptions, patch_script must include the same
  durable setup needed when the whole block is rerun from the baseline.
- Prefer package-manager fixes, missing tool installs, compatibility pins, and validation fixes.
- If repair_context.repo_context.task_description is present, repair toward that
  task/setup goal without editing project source code or turning validation into
  a full application correctness test.
- For Python projects with `.venv/bin/python`, use `.venv/bin/python -m pip`
  and `.venv/bin/python -m pytest`. Do not use system `python3 -m pip install`
  when PEP 668 or externally-managed-environment is present.
- For Python version failures, inspect `requires-python`, `.python-version`,
  `runtime.txt`, tox/nox config, and CI hints. Prefer installing a compatible
  interpreter such as python3.10, python3.11, or python3.12 and recreating
  `.venv`; do not edit repository metadata or source to bypass version
  constraints. If the base image cannot provide that interpreter, report that
  base/runtime selection is the blocker.
- The block is executed by POSIX sh. Use `. .venv/bin/activate` or direct
  `.venv/bin/python -m pip`; do not try to repair `source: not found` by
  calling transient block scripts, catting scripts into themselves, or rewriting
  the repo.
- For Python 3.12 failures involving old `pkg_resources`, `distutils`, numpy
  build metadata, or `pkgutil.ImpImporter`, prefer compatibility pins and
  environment variables such as `SETUPTOOLS_USE_DISTUTILS=local` inside the
  block script. Use `setuptools>=68.2,<82` or a similar Python-3.12-compatible
  range; do not pin setuptools to 65/66 or below 68. Do not edit setup.py,
  pyproject.toml, or package source.
- Do not put Python compound statements (`for`, `if`, `with`, `try`, `def`,
  `class`) inside `python -c` one-liners. Use a heredoc such as
  `.venv/bin/python - <<'PY' ... PY` for multi-line Python repair logic.
- If a requirements sanitizer script failed, do not patch fake files such as
  failed_script.py and do not use sed/perl in-place edits. Replace the setup
  step with a temporary sanitized requirements file under /tmp generated by a
  heredoc, then install from that temporary file.
- For pip "Double requirement given" or duplicated requirement entries, do not
  edit requirements.txt and do not rely on the legacy resolver as the primary
  fix. Generate a temporary sanitized requirements file under /tmp and install
  from that file, preserving the original repo file unchanged.
- For Python dependency errors caused by packages declaring an incompatible
  Requires-Python range, treat the package as an environment compatibility
  issue. Prefer interpreter-compatible pins, optional-dependency avoidance, or
  dependency-only installs over editing project source.
- For git "dubious ownership" failures inside the container, configure
  `git config --global --add safe.directory /workspace/repo`; do not rewrite
  repository ownership from the host.
- Never require real external secrets for environment setup validation. If a
  generated validation checks placeholder API keys such as
  `your_openai_api_key_here`, replace that validation with a local tool/import
  check instead.
- Do not use `pip check` as a success criterion. If validation needs to prove a
  Python environment is usable, prefer `.venv/bin/python -m pytest --collect-only
  -q` with exit code 5 treated as success, or use `.venv/bin/python -m pytest
  --version` when collection imports application code that needs services or
  credentials.
- Do not edit application source, tests, conftest.py, or sitecustomize.py to make
  tests pass. If validation is running the full test suite and failures are
  application behavior, replace validation with a tool/import/pytest collect-only
  check instead.
- If pytest collection imports application conftest code that requires external
  services, credentials, or custom fixture decorators, validation may be relaxed
  to confirming the test runner/tooling is installed. Do not patch tests or
  conftest.py.
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
- If repair_context.repo_context.task_description is present, probes may inspect
  task-relevant manifests, CLIs, and imports, but must still be read-only.
- Keep each command single-line, deterministic, and fast.
- The orchestrator will run accepted probes from the failed block baseline and
  then ask for the actual repair command with probe_results included.
- The word JSON appears here intentionally because JSON mode requires an explicit JSON instruction.
""".strip()
