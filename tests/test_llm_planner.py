from __future__ import annotations

import json
import urllib.error
from pathlib import Path

from pheragent.analyzer import RepoAnalyzer
from pheragent.llm_planner import OpenAICompatibleBlockPlanner, OpenAIPlannerConfig, make_planner
from pheragent.planner import RuleBasedBlockPlanner


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


def test_openai_compatible_planner_parses_chat_completion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    requests: list[object] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "blocks": [
                                            {
                                                "id": "00-custom",
                                                "order": 0,
                                                "title": "Custom",
                                                "goal": "custom setup",
                                                "script": "echo custom",
                                                "validation_command": (
                                                    'uv run python -c "import flask; '
                                                    'print(flask.__version__)"'
                                                ),
                                            }
                                        ]
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        del timeout
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    planner = OpenAICompatibleBlockPlanner(OpenAIPlannerConfig(model="gpt-5.5"))

    blocks = planner.plan(context)

    assert blocks[0].id == "00-custom"
    assert blocks[0].script.startswith("#!/bin/sh")
    assert "echo custom" in blocks[0].script
    assert blocks[0].validation_command == 'uv run python -c "import flask; print(flask)"'
    request = requests[0]
    assert request.full_url == "https://example.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["model"] == "gpt-5.5"
    assert payload["response_format"] == {"type": "json_object"}


def test_openai_compatible_planner_retries_transient_request_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    calls = 0

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "blocks": [
                                            {
                                                "id": "00-custom",
                                                "order": 0,
                                                "title": "Custom",
                                                "goal": "custom setup",
                                                "script": "echo custom",
                                            }
                                        ]
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        nonlocal calls
        del request, timeout
        calls += 1
        if calls == 1:
            raise urllib.error.URLError("temporary")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    planner = OpenAICompatibleBlockPlanner(
        OpenAIPlannerConfig(model="gpt-5.5", max_retries=2, retry_delay_s=0)
    )

    blocks = planner.plan(context)

    assert calls == 2
    assert blocks[0].id == "00-custom"


def test_openai_compatible_planner_auto_falls_back_after_retries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_urlopen(request, timeout):
        del request, timeout
        raise urllib.error.URLError("temporary")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    planner = OpenAICompatibleBlockPlanner(
        OpenAIPlannerConfig(
            model="gpt-5.5",
            max_retries=1,
            retry_delay_s=0,
            fallback_on_error=True,
        )
    )

    blocks = planner.plan(context)

    assert blocks
    assert any(block.id.endswith("python-deps") for block in blocks)


def test_openai_compatible_planner_uses_safe_preflight_script() -> None:
    planner = OpenAICompatibleBlockPlanner(OpenAIPlannerConfig(model="gpt-5.5"))

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


def test_openai_compatible_planner_uses_safe_python_dependency_script() -> None:
    planner = OpenAICompatibleBlockPlanner(OpenAIPlannerConfig(model="gpt-5.5"))

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
    assert blocks[0].validation_command is not None
    assert ".venv/bin/python" in blocks[0].validation_command
