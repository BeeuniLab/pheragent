from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .models import CommandBlock, RepoContext, to_jsonable
from .planner import BlockPlanner, RuleBasedBlockPlanner, _preflight_script
from .utils import shell_script, slugify


@dataclass(slots=True)
class OpenAIPlannerConfig:
    model: str = "gpt-5.5"
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    base_url: str | None = None
    timeout: float = 120.0
    max_tokens: int = 4096
    temperature: float = 0.1
    max_retries: int = 3
    retry_delay_s: float = 1.0
    stream: bool = False
    fallback_on_error: bool = False


class OpenAICompatibleBlockPlanner:
    def __init__(
        self,
        config: OpenAIPlannerConfig,
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
            content = self._post_chat_completion(
                base_url,
                api_key,
                self._request_payload(context, token_param="max_completion_tokens"),
            )
            return self._parse_blocks(content)
        except Exception:
            if self.config.fallback_on_error:
                return self.fallback.plan(context)
            raise

    def _request_payload(self, context: RepoContext, *, token_param: str) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            token_param: self.config.max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "repo_context": to_jsonable(context),
                            "fallback_blocks": [
                                to_jsonable(block) for block in self.fallback.plan(context)
                            ],
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                },
            ],
        }

    def _post_chat_completion(
        self,
        base_url: str,
        api_key: str,
        payload: dict[str, Any],
    ) -> str:
        content = ""
        max_attempts = max(1, self.config.max_retries)
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            request_payload = _maybe_stream_payload(payload, stream=self.config.stream)
            request = _chat_completion_request(base_url, api_key, request_payload)
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                    content = _read_chat_completion_response(
                        response,
                        stream=self.config.stream,
                        error_context="LLM planner",
                    )
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(
                    f"LLM planner request failed: HTTP {exc.code}: {detail}"
                )
                if not _retryable_http_status(exc.code) or attempt == max_attempts:
                    raise last_error from exc
            except (TimeoutError, urllib.error.URLError) as exc:
                last_error = RuntimeError(f"LLM planner request failed: {exc}")
                if attempt == max_attempts:
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
    stream: bool,
) -> BlockPlanner:
    fallback = RuleBasedBlockPlanner()
    if mode == "rules":
        return fallback
    has_key = bool(os.getenv(api_key_env))
    if mode == "auto" and not has_key:
        return fallback
    if mode not in {"auto", "llm"}:
        raise ValueError(f"unsupported planner mode: {mode}")
    return OpenAICompatibleBlockPlanner(
        OpenAIPlannerConfig(
            model=model or os.getenv("PHERAGENT_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.5",
            api_key_env=api_key_env,
            base_url_env=base_url_env,
            base_url=base_url,
            timeout=timeout,
            max_tokens=max_tokens,
            max_retries=retries,
            retry_delay_s=retry_delay,
            stream=stream or _env_flag("PHERAGENT_LLM_STREAM"),
            fallback_on_error=mode == "auto",
        ),
        fallback=fallback,
    )


def _chat_completion_request(
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
) -> urllib.request.Request:
    return urllib.request.Request(
        url=f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "pheragent/0.1",
        },
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )


def _maybe_stream_payload(payload: dict[str, Any], *, stream: bool) -> dict[str, Any]:
    if not stream:
        return payload
    streamed = dict(payload)
    streamed["stream"] = True
    return streamed


def _read_chat_completion_response(response, *, stream: bool, error_context: str) -> str:
    if stream:
        return _read_streaming_chat_completion(response, error_context=error_context)
    body = response.read().decode("utf-8", errors="replace")
    return _extract_chat_completion_content(body, error_context=error_context)


def _read_streaming_chat_completion(response, *, error_context: str) -> str:
    chunks: list[str] = []
    for raw_line in response:
        line = _decode_sse_line(raw_line)
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{error_context} returned invalid stream chunk: {data[:500]}"
            ) from exc
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0]
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if isinstance(delta, dict) and delta.get("content") is not None:
            chunks.append(str(delta["content"]))
        message = choice.get("message")
        if isinstance(message, dict) and message.get("content") is not None:
            chunks.append(str(message["content"]))
    content = "".join(chunks)
    if not content:
        raise RuntimeError(f"{error_context} stream returned no content")
    return content


def _decode_sse_line(raw_line: bytes | str) -> str:
    if isinstance(raw_line, bytes):
        return raw_line.decode("utf-8", errors="replace").strip()
    return raw_line.strip()


def _extract_chat_completion_content(body: str, *, error_context: str) -> str:
    try:
        data = json.loads(body)
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"{error_context} returned an unexpected response: {body[:1000]}"
        ) from exc


def _retryable_http_status(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def _sleep_before_retry(attempt: int, retry_delay_s: float) -> None:
    delay = max(0.0, retry_delay_s) * (2 ** (attempt - 1))
    if delay > 0:
        time.sleep(delay)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


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
