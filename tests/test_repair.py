from __future__ import annotations

import json
from pathlib import Path

from pheragent.models import BlockExecution, CommandBlock, CommandResult, RepairContext, RepoContext
from pheragent.repair import (
    OpenAIResponsesRepairConfig,
    OpenAIResponsesRepairPlanner,
    RepairCommand,
    RepairPlanner,
    make_repair_planner,
)


def test_repair_planner_handles_pep_668_uv_install_failure() -> None:
    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\nset -eu\npython3 -m pip install uv\nuv sync\n",
    )
    result = CommandResult(
        exit_code=1,
        stderr="error: externally-managed-environment\nhint: See PEP 668",
    )

    suggestions = RepairPlanner().suggest(block, result)

    assert suggestions
    assert "python3 -m venv .pheragent-tools" in suggestions[0].command
    assert "python3-pip python3-venv" in suggestions[0].command
    assert "PIP_BREAK_SYSTEM_PACKAGES=1" in suggestions[0].command
    assert "ln -sf /workspace/repo/.pheragent-tools/bin/uv /usr/local/bin/uv" in suggestions[
        0
    ].command


def test_repair_planner_pins_pnpm_for_older_node_runtime() -> None:
    block = CommandBlock(
        id="03-node-deps",
        title="Node Dependencies",
        goal="Install deps",
        script="#!/bin/sh\nset -eu\nnpm install -g pnpm\npnpm install\n",
        validation_command="node --version && npm --version && pnpm --version",
    )
    result = CommandResult(
        exit_code=1,
        stderr=(
            "ERROR: This version of pnpm requires at least Node.js v22.13\n"
            "The current version of Node.js is v18.19.1"
        ),
    )

    suggestions = RepairPlanner().suggest(block, result)

    assert suggestions
    assert suggestions[0].title == "Install Node-compatible pnpm"
    assert "PNPM_PACKAGE=pnpm@9" in suggestions[0].command
    assert 'npm install -g "$PNPM_PACKAGE"' in suggestions[0].command


def test_repair_planner_adds_python_alias() -> None:
    block = CommandBlock(
        id="03-validation",
        title="Validation",
        goal="Run validation",
        script="#!/bin/sh\npython -m pytest --version\n",
    )
    result = CommandResult(exit_code=127, stderr="sh: 1: python: not found")

    suggestions = RepairPlanner().suggest(block, result)

    assert suggestions
    assert "/usr/local/bin/python" in suggestions[0].command


def test_repair_planner_relaxes_dunder_version_validation() -> None:
    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\nset -eu\nuv sync\n",
        validation_command='uv run python -c "import flask; print(flask.__version__)"',
    )
    result = CommandResult(
        exit_code=1,
        stderr="AttributeError: module 'flask' has no attribute '__version__'",
    )

    suggestions = RepairPlanner().suggest(block, result)
    patched = RepairPlanner().patch_block(block, suggestions[0])

    assert suggestions
    assert suggestions[0].command == "true"
    assert patched.validation_command == 'uv run python -c "import flask; print(flask)"'


def test_repair_planner_appends_llm_suggestions_after_rules() -> None:
    class FakeLLMRepairPlanner:
        def suggest(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
        ) -> list[RepairCommand]:
            del block, result, context
            return [
                RepairCommand(
                    title="Install cmake",
                    command="apt-get update && apt-get install -y cmake",
                    patch_script="apt-get update && apt-get install -y cmake",
                )
            ]

    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\npip install example\n",
    )
    result = CommandResult(exit_code=1, stderr="gcc: not found")

    suggestions = RepairPlanner(llm_planner=FakeLLMRepairPlanner()).suggest(block, result)

    assert "build-essential" in suggestions[0].command
    assert suggestions[1].title == "Install cmake"


def test_repair_planner_records_llm_failure_for_unknown_errors() -> None:
    class FailingLLMRepairPlanner:
        def suggest(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
        ) -> list[RepairCommand]:
            del block, result, context
            raise RuntimeError("proxy unavailable")

    block = CommandBlock(
        id="02-custom",
        title="Custom",
        goal="install",
        script="#!/bin/sh\ncustom-install\n",
    )
    result = CommandResult(exit_code=1, stderr="mystery failure")
    planner = RepairPlanner(llm_planner=FailingLLMRepairPlanner())

    suggestions = planner.suggest(block, result)

    assert suggestions == []
    assert planner.last_llm_error == "proxy unavailable"


def test_openai_responses_repair_parser_filters_dangerous_commands() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        """
        {
          "repairs": [
            {
              "title": "Bad",
              "command": "docker rm -f something",
              "patch_script": "docker rm -f something"
            },
            {
              "title": "Good",
              "command": "apt-get update && apt-get install -y libssl-dev",
              "patch_script": "apt-get update && apt-get install -y libssl-dev"
            }
          ]
        }
        """
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Good"


def test_openai_responses_repair_payload_includes_repair_context(tmp_path: Path) -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())
    block = CommandBlock(
        id="02-build",
        title="Build",
        goal="compile",
        script="#!/bin/sh\nmake\n",
    )
    result = CommandResult(exit_code=1, stderr="cmake: not found")
    context = RepairContext(
        repo_context=RepoContext(
            repo_path=tmp_path,
            languages=["python"],
            runtime_notes=["tool:python3=/usr/bin/python3", "tool:cmake=missing"],
        ),
        checkpoint_before="fake:baseline",
        previous_blocks=[
            CommandBlock(
                id="00-preflight",
                title="Preflight",
                goal="inspect",
                script="#!/bin/sh\necho ok\n",
                status="succeeded",
            )
        ],
        recent_executions=[
            BlockExecution(
                block_id="02-build",
                phase="block",
                attempt=1,
                exit_code=1,
                timed_out=False,
                stdout_tail="",
                stderr_tail="cmake: not found",
            )
        ],
    )

    payload = planner._request_payload(block, result, context)
    content = json.loads(payload["input"])

    assert content["repair_context"]["checkpoint_before"] == "fake:baseline"
    assert "tool:cmake=missing" in content["repair_context"]["repo_context"]["runtime_notes"]
    assert content["repair_context"]["previous_blocks"][0]["id"] == "00-preflight"
    assert content["repair_context"]["recent_executions"][0]["phase"] == "block"
    assert payload["stream"] is True
    assert payload["text"] == {"format": {"type": "json_object"}}


def test_make_repair_planner_auto_uses_rules_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    planner = make_repair_planner(
        mode="auto",
        model=None,
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        base_url=None,
        timeout=120,
        max_tokens=4096,
        retries=3,
        retry_delay=1,
    )

    assert planner.llm_planner is None
