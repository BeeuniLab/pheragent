from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pheragent.analyzer import RepoAnalyzer
from pheragent.llm_planner import (
    OpenAIResponsesBlockPlanner,
    OpenAIResponsesPlannerConfig,
    _openai_client,
    make_planner,
)
from pheragent.planner import RuleBasedBlockPlanner


class FakeEvent:
    def __init__(self, event_type: str, **values: object):
        self.type = event_type
        for name, value in values.items():
            setattr(self, name, value)


class FakeStream:
    def __init__(self, events: list[FakeEvent]):
        self.events = events
        self.closed = False

    def __iter__(self):
        return iter(self.events)

    def close(self) -> None:
        self.closed = True


class FakeResponses:
    def __init__(self, events: list[FakeEvent], *, failures_before_success: int = 0):
        self.events = events
        self.failures_before_success = failures_before_success
        self.calls: list[dict[str, Any]] = []

    def create(self, **payload):
        self.calls.append(payload)
        if len(self.calls) <= self.failures_before_success:
            raise TimeoutError("temporary")
        return FakeStream(self.events)


class FakeOpenAI:
    clients: list[FakeOpenAI] = []
    events: list[FakeEvent] = []
    failures_before_success = 0

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.responses = FakeResponses(
            self.events,
            failures_before_success=self.failures_before_success,
        )
        type(self).clients.append(self)


def _planner_response_events() -> list[FakeEvent]:
    content = json.dumps(
        {
            "blocks": [
                {
                    "id": "00-custom",
                    "order": 0,
                    "title": "Custom",
                    "goal": "custom setup",
                    "script": "echo custom",
                    "validation_command": (
                        'uv run python -c "import flask; print(flask.__version__)"'
                    ),
                }
            ]
        }
    )
    midpoint = len(content) // 2
    return [
        FakeEvent("response.output_text.delta", delta=content[:midpoint]),
        FakeEvent("response.output_text.delta", delta=content[midpoint:]),
        FakeEvent(
            "response.completed",
            response={
                "usage": {
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "output_tokens_details": {"reasoning_tokens": 3},
                    "total_tokens": 18,
                }
            },
        ),
    ]


def test_make_planner_auto_uses_rules_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = make_planner(
        mode="auto",
        model=None,
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        base_url=None,
        timeout=120.0,
        max_tokens=4096,
        retries=3,
        retry_delay=1.0,
    )

    assert isinstance(planner, RuleBasedBlockPlanner)


def test_openai_responses_planner_uses_sdk_streaming(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    FakeOpenAI.clients = []
    FakeOpenAI.events = _planner_response_events()
    FakeOpenAI.failures_before_success = 0
    monkeypatch.setattr("pheragent.llm_planner._openai_client", FakeOpenAI)

    planner = OpenAIResponsesBlockPlanner(OpenAIResponsesPlannerConfig(model="gpt-5.5"))

    blocks = planner.plan(context)

    assert blocks[0].id == "00-custom"
    assert blocks[0].script.startswith("#!/bin/sh")
    assert "echo custom" in blocks[0].script
    assert blocks[0].validation_command == 'uv run python -c "import flask; print(flask)"'
    assert planner.usage_summary()["total"] == {
        "requests": 1,
        "input_tokens": 11,
        "output_tokens": 7,
        "reasoning_tokens": 3,
        "total_tokens": 18,
    }

    client = FakeOpenAI.clients[0]
    assert client.kwargs["api_key"] == "test-key"
    assert client.kwargs["base_url"] == "https://example.test/v1"
    assert client.kwargs["timeout"] == 120.0

    payload = client.responses.calls[0]
    assert payload["model"] == "gpt-5.5"
    assert payload["stream"] is True
    assert payload["text"] == {"format": {"type": "json_object"}}
    assert "max_output_tokens" not in payload
    assert "temperature" not in payload
    assert "messages" not in payload
    assert "response_format" not in payload
    assert isinstance(payload["input"], list)
    assert payload["input"][0]["role"] == "user"
    input_text = payload["input"][0]["content"][0]
    assert input_text["type"] == "input_text"
    content = json.loads(input_text["text"])
    assert content["output_instructions"] == "Return JSON only."
    assert "json" in input_text["text"].lower()
    assert "repo_context" in content


def test_openai_client_disables_sdk_retries() -> None:
    client = _openai_client(
        base_url="https://example.test/v1",
        api_key="test-key",
        timeout=120.0,
    )

    assert client.max_retries == 0


def test_openai_responses_planner_retries_transient_sdk_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    FakeOpenAI.clients = []
    FakeOpenAI.events = _planner_response_events()
    FakeOpenAI.failures_before_success = 1
    monkeypatch.setattr("pheragent.llm_planner._openai_client", FakeOpenAI)
    planner = OpenAIResponsesBlockPlanner(
        OpenAIResponsesPlannerConfig(model="gpt-5.5", max_retries=2, retry_delay_s=0)
    )

    blocks = planner.plan(context)

    assert len(FakeOpenAI.clients[0].responses.calls) == 2
    assert blocks[0].id == "00-custom"


def test_openai_responses_planner_auto_falls_back_after_retries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FailingResponses:
        def create(self, **payload):
            del payload
            raise TimeoutError("temporary")

    class FailingOpenAI:
        def __init__(self, **kwargs):
            del kwargs
            self.responses = FailingResponses()

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("pheragent.llm_planner._openai_client", FailingOpenAI)
    planner = OpenAIResponsesBlockPlanner(
        OpenAIResponsesPlannerConfig(
            model="gpt-5.5",
            max_retries=1,
            retry_delay_s=0,
            fallback_on_error=True,
        )
    )

    blocks = planner.plan(context)

    assert blocks
    assert any(block.id.endswith("python-deps") for block in blocks)


def test_openai_responses_planner_uses_safe_preflight_script() -> None:
    planner = OpenAIResponsesBlockPlanner(OpenAIResponsesPlannerConfig(model="gpt-5.5"))

    blocks = planner._parse_blocks(
        json.dumps(
            {
                "blocks": [
                    {
                        "id": "00-preflight",
                        "order": 0,
                        "title": "Preflight",
                        "goal": "inspect",
                        "script": (
                            "echo preflight; "
                            "echo 'python executable not found' >&2; "
                            "exit 127"
                        ),
                    }
                ]
            }
        )
    )

    assert "python executable not found" not in blocks[0].script
    assert "command -v python3" in blocks[0].script


def test_openai_responses_planner_uses_safe_python_dependency_script() -> None:
    planner = OpenAIResponsesBlockPlanner(OpenAIResponsesPlannerConfig(model="gpt-5.5"))

    blocks = planner._parse_blocks(
        json.dumps(
            {
                "blocks": [
                    {
                        "id": "02-python-deps",
                        "order": 2,
                        "title": "Python Dependencies",
                        "goal": "install",
                        "script": "python3 -m pip install --upgrade pip setuptools wheel",
                    }
                ]
            }
        )
    )

    assert "PIP_BREAK_SYSTEM_PACKAGES" not in blocks[0].script
    assert "python3 -m venv .pheragent-tools" in blocks[0].script
    assert "ln -sf /workspace/repo/.pheragent-tools/bin/uv /usr/local/bin/uv" in blocks[
        0
    ].script
    assert "ensure_pytest /workspace/repo/.venv/bin/python" in blocks[0].script
    assert "ln -sf /workspace/repo/.venv/bin/python /usr/local/bin/python" in blocks[0].script
    assert "ln -sf /workspace/repo/.venv/bin/pytest /usr/local/bin/pytest" in blocks[0].script
    assert blocks[0].validation_command is not None
    assert ".venv/bin/python" in blocks[0].validation_command


def test_openai_responses_planner_uses_collect_only_for_build_test_validation() -> None:
    planner = OpenAIResponsesBlockPlanner(OpenAIResponsesPlannerConfig(model="gpt-5.5"))

    blocks = planner._parse_blocks(
        json.dumps(
            {
                "blocks": [
                    {
                        "id": "03-build-test-prep",
                        "order": 3,
                        "title": "Build/Test Prep",
                        "goal": "install pytest and validate tests",
                        "script": "python -m pip install pytest",
                        "validation_command": (
                            "cd /workspace/repo && ./.venv/bin/python -m pytest -q"
                        ),
                    }
                ]
            }
        )
    )

    assert blocks[0].validation_command is not None
    assert "--collect-only" in blocks[0].validation_command
    assert "pytest -q" not in blocks[0].validation_command
    assert "conftest.py" not in blocks[0].script


def test_openai_responses_planner_replaces_repo_code_modifying_build_test_script() -> None:
    planner = OpenAIResponsesBlockPlanner(OpenAIResponsesPlannerConfig(model="gpt-5.5"))

    blocks = planner._parse_blocks(
        json.dumps(
            {
                "blocks": [
                    {
                        "id": "03-build-test-prep",
                        "order": 3,
                        "title": "Build/Test Prep",
                        "goal": "prepare tests",
                        "script": "cat > conftest.py <<'PY'\nprint('patch')\nPY",
                        "validation_command": "python -m pytest -q",
                    }
                ]
            }
        )
    )

    assert "build/test prep" in blocks[0].script
    assert "conftest.py" not in blocks[0].script
    assert "--collect-only" in (blocks[0].validation_command or "")


def test_openai_responses_planner_rejects_repo_code_modifying_setup_blocks() -> None:
    planner = OpenAIResponsesBlockPlanner(OpenAIResponsesPlannerConfig(model="gpt-5.5"))
    source_write_script = (
        "python - <<'PY'\n"
        "from pathlib import Path\n"
        "Path('pkg/app.py').write_text('x')\n"
        "PY"
    )

    with pytest.raises(ValueError, match="modifies repository code"):
        planner._parse_blocks(
            json.dumps(
                {
                    "blocks": [
                        {
                            "id": "01-system-deps",
                            "order": 1,
                            "title": "System Dependencies",
                            "goal": "install deps",
                            "script": source_write_script,
                        }
                    ]
                }
            )
        )
