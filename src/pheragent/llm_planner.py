from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from .models import CommandBlock, RepoContext, to_jsonable
from .planner import BlockPlanner, RuleBasedBlockPlanner, _preflight_script
from .utils import shell_script, slugify


@dataclass(slots=True)
class OpenAIResponsesPlannerConfig:
    model: str = "gpt-5.5"
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    base_url: str | None = None
    timeout: float = 120.0
    max_tokens: int = 4096
    max_retries: int = 3
    retry_delay_s: float = 1.0
    fallback_on_error: bool = False


class OpenAIResponsesBlockPlanner:
    def __init__(
        self,
        config: OpenAIResponsesPlannerConfig,
        *,
        fallback: BlockPlanner | None = None,
    ):
        self.config = config
        self.fallback = fallback or RuleBasedBlockPlanner()

    def plan(self, context: RepoContext) -> list[CommandBlock]:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key in env var {self.config.api_key_env}")
        base_url = (self.config.base_url or os.getenv(self.config.base_url_env) or "").rstrip("/")
        if not base_url:
            base_url = "https://api.openai.com/v1"

        try:
            content = self._create_response(
                _openai_client(base_url=base_url, api_key=api_key, timeout=self.config.timeout),
                self._request_payload(context),
            )
            return self._parse_blocks(content)
        except Exception:
            if self.config.fallback_on_error:
                return self.fallback.plan(context)
            raise

    def _request_payload(self, context: RepoContext) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "instructions": _SYSTEM_PROMPT,
            "input": _response_text_input(
                json.dumps(
                    {
                        "output_instructions": "Return JSON only.",
                        "repo_context": to_jsonable(context),
                        "fallback_blocks": [
                            to_jsonable(block) for block in self.fallback.plan(context)
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            ),
            "text": {"format": {"type": "json_object"}},
            "stream": True,
        }

    def _create_response(
        self,
        client: Any,
        payload: dict[str, Any],
    ) -> str:
        content = ""
        max_attempts = max(1, self.config.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                stream = client.responses.create(**payload)
                content = _read_streamed_response(stream, error_context="LLM planner")
                break
            except Exception as exc:
                last_error = RuntimeError(_format_llm_error("LLM planner", exc))
                if attempt == max_attempts:
                    raise last_error from exc
                if not _retryable_llm_error(exc):
                    raise last_error from exc
            _sleep_before_retry(attempt, self.config.retry_delay_s)
        else:
            raise RuntimeError(f"LLM planner request failed: {last_error}") from last_error

        return content

    def _parse_blocks(self, content: str) -> list[CommandBlock]:
        data = _parse_json_object(content)
        raw_blocks = data.get("blocks")
        if not isinstance(raw_blocks, list) or not raw_blocks:
            raise ValueError("LLM planner JSON must contain a non-empty blocks list")

        blocks: list[CommandBlock] = []
        used_ids: set[str] = set()
        for index, item in enumerate(raw_blocks):
            if not isinstance(item, dict):
                raise ValueError("block entries must be JSON objects")
            title = str(item.get("title") or "block")
            block_id = str(item.get("id") or f"{index:02d}-{slugify(title)}")
            block_id = slugify(block_id)
            if block_id in used_ids:
                block_id = f"{block_id}-{index}"
            used_ids.add(block_id)
            script = str(item.get("script", "")).strip()
            if not script:
                raise ValueError(f"block {block_id} has empty script")
            if "preflight" in block_id or "preflight" in title.lower():
                script = _preflight_script()
            validation_command = _sanitize_validation_command(
                _optional_str(item.get("validation_command"))
            )
            if _is_python_dependency_block(block_id, title):
                script = _safe_python_dependency_script()
                validation_command = _safe_python_dependency_validation_command()
            blocks.append(
                CommandBlock(
                    id=block_id,
                    order=int(item.get("order", index)),
                    title=title,
                    goal=str(item.get("goal") or ""),
                    script=shell_script(script),
                    validation_command=validation_command,
                )
            )
        return sorted(blocks, key=lambda block: (block.order, block.id))


def make_planner(
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
) -> BlockPlanner:
    fallback = RuleBasedBlockPlanner()
    if mode == "rules":
        return fallback
    has_key = bool(os.getenv(api_key_env))
    if mode == "auto" and not has_key:
        return fallback
    if mode not in {"auto", "llm"}:
        raise ValueError(f"unsupported planner mode: {mode}")
    return OpenAIResponsesBlockPlanner(
        OpenAIResponsesPlannerConfig(
            model=model or os.getenv("PHERAGENT_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.5",
            api_key_env=api_key_env,
            base_url_env=base_url_env,
            base_url=base_url,
            timeout=timeout,
            max_tokens=max_tokens,
            max_retries=retries,
            retry_delay_s=retry_delay,
            fallback_on_error=mode == "auto",
        ),
        fallback=fallback,
    )


def _openai_client(*, base_url: str, api_key: str, timeout: float) -> Any:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(f"failed to import OpenAI Python SDK: {exc}") from exc

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=0,
    )


def _response_text_input(text: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": text,
                }
            ],
        }
    ]


def _read_streamed_response(stream: Any, *, error_context: str) -> str:
    chunks: list[str] = []
    done_text: str | None = None
    completed_text: str | None = None
    try:
        for event in stream:
            event_type = _event_value(event, "type")
            if event_type == "response.output_text.delta":
                delta = _event_value(event, "delta")
                if delta is not None:
                    chunks.append(str(delta))
            elif event_type == "response.output_text.done":
                text = _event_value(event, "text")
                if text is not None:
                    done_text = str(text)
            elif event_type == "response.completed":
                completed_text = _extract_response_output_text(_event_value(event, "response"))
            elif event_type in {"error", "response.failed"}:
                raise RuntimeError(f"{error_context} stream failed: {_event_error_text(event)}")
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()
    content = "".join(chunks)
    if not content:
        content = done_text or completed_text or ""
    if not content:
        raise RuntimeError(f"{error_context} stream returned no content")
    return content


def _event_value(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _event_error_text(event: Any) -> str:
    error = _event_value(event, "error")
    if error is None:
        return str(event)
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(getattr(error, "message", None) or error)


def _extract_response_output_text(response: Any) -> str:
    output_text = _event_value(response, "output_text")
    if isinstance(output_text, str):
        return output_text

    if not isinstance(response, dict) and hasattr(response, "model_dump"):
        response = response.model_dump()
    output = _event_value(response, "output")
    if not isinstance(output, list):
        return ""
    text_parts: list[str] = []
    for item in output:
        content = _event_value(item, "content")
        if not isinstance(content, list):
            continue
        for part in content:
            if _event_value(part, "type") == "output_text":
                text = _event_value(part, "text")
                if text is not None:
                    text_parts.append(str(text))
    return "".join(text_parts)


def _retryable_http_status(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def _sleep_before_retry(attempt: int, retry_delay_s: float) -> None:
    delay = max(0.0, retry_delay_s) * (2 ** (attempt - 1))
    if delay > 0:
        time.sleep(delay)


def _retryable_llm_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return _retryable_http_status(status_code)
    openai_error_name = type(exc).__name__
    if openai_error_name in {"APIConnectionError", "APITimeoutError"}:
        return True
    return isinstance(
        exc,
        (TimeoutError, ConnectionError, OSError),
    )


def _format_llm_error(error_context: str, exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        detail = _api_status_detail(exc)
        return f"{error_context} request failed: HTTP {status_code}: {detail}"
    if type(exc).__name__ == "APIError":
        return f"{error_context} request failed: {exc}"
    return f"{error_context} request failed: {exc}"


def _api_status_detail(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    detail = getattr(response, "text", None)
    if detail:
        return str(detail)[:1000]
    return str(exc)


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(content):
            if char != "{":
                continue
            try:
                data, _ = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            break
        else:
            raise ValueError("content did not contain a JSON object") from None
    if not isinstance(data, dict):
        raise ValueError("content JSON must be an object")
    return data


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sanitize_validation_command(command: str | None) -> str | None:
    if command is None or "__version__" not in command:
        return command
    patched = re.sub(r"print\(([A-Za-z_][A-Za-z0-9_]*)\.__version__\)", r"print(\1)", command)
    return re.sub(r"([A-Za-z_][A-Za-z0-9_]*)\.__version__", r"\1", patched)


def _is_python_dependency_block(block_id: str, title: str) -> bool:
    haystack = f"{block_id} {title}".lower()
    return "python" in haystack and ("dep" in haystack or "environment" in haystack)


def _safe_python_dependency_script() -> str:
    return """
cd /workspace/repo

echo "[pheragent] python dependencies"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends python3 python3-pip python3-venv
  PYTHON_BIN=python3
else
  echo "python executable not found" >&2
  exit 127
fi

if command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  if [ -w /usr/local/bin ] || [ "$(id -u)" = "0" ]; then
    ln -sf "$(command -v python3)" /usr/local/bin/python
  fi
fi

mkdir -p .cache/uv .cache/pip
export UV_CACHE_DIR=/workspace/repo/.cache/uv
export PIP_CACHE_DIR=/workspace/repo/.cache/pip

if [ -f uv.lock ]; then
  if ! command -v uv >/dev/null 2>&1; then
    python3 -m venv .pheragent-tools
    ./.pheragent-tools/bin/python -m pip install --upgrade pip
    ./.pheragent-tools/bin/python -m pip install uv
    if [ -w /usr/local/bin ] || [ "$(id -u)" = "0" ]; then
      ln -sf /workspace/repo/.pheragent-tools/bin/uv /usr/local/bin/uv
    else
      export PATH="/workspace/repo/.pheragent-tools/bin:$PATH"
    fi
  fi
  uv sync --locked --all-extras --dev \
    || uv sync --frozen --all-extras --dev \
    || uv sync --all-extras --dev
else
  if [ ! -d .venv ]; then
    "$PYTHON_BIN" -m venv .venv
  fi
  ./.venv/bin/python -m pip install --upgrade pip setuptools wheel
  if [ -f requirements.txt ]; then
    ./.venv/bin/python -m pip install -r requirements.txt
  fi
  if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ]; then
    ./.venv/bin/python -m pip install -e '.[dev]' || ./.venv/bin/python -m pip install -e .
  fi
fi
""".strip()


def _safe_python_dependency_validation_command() -> str:
    return (
        "cd /workspace/repo && test -x .venv/bin/python && "
        '.venv/bin/python -c "import sys; print(sys.version)"'
    )


_SYSTEM_PROMPT = """
You are pheragent's environment setup block planner.

Return JSON only. The JSON object must have this shape:
{
  "blocks": [
    {
      "id": "00-preflight",
      "order": 0,
      "title": "Preflight",
      "goal": "short purpose",
      "script": "POSIX sh commands",
      "validation_command": "optional POSIX sh command"
    }
  ]
}

Rules:
- Generate command blocks for a Docker container whose repo working directory is /workspace/repo.
- Split setup into coarse, replayable blocks: preflight, system deps, language deps,
  build/test prep.
- Use POSIX sh, not bash-specific syntax.
- Keep commands deterministic and idempotent where practical.
- Do not start long-running services in setup blocks.
- Do not use host paths outside /workspace/repo.
- Prefer the provided fallback_blocks when they are suitable, and improve them only
  when repo context indicates a better block sequence.
- The word JSON appears here intentionally because JSON mode requires an explicit JSON instruction.
""".strip()
