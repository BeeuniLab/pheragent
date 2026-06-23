from __future__ import annotations

import json
from pathlib import Path

from pheragent.models import (
    BlockExecution,
    CommandBlock,
    CommandResult,
    RepairContext,
    RepairProbeResult,
    RepoContext,
)
from pheragent.repair import (
    OpenAIResponsesRepairConfig,
    OpenAIResponsesRepairPlanner,
    RepairCommand,
    RepairPlanner,
    _heuristic_failure_localization,
    _heuristic_repair_hints,
    make_repair_planner,
)


def test_repair_hints_use_project_venv_for_pep_668_failure() -> None:
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

    suggestions = _heuristic_repair_hints(block, result)

    assert suggestions
    assert suggestions[0].title == "Use project virtualenv pip"
    assert "rm -rf .venv" in suggestions[0].command
    assert "python3 -m venv .venv" in suggestions[0].command
    assert "./.venv/bin/python -m pip install" in suggestions[0].command
    assert "PIP_BREAK_SYSTEM_PACKAGES" not in suggestions[0].command


def test_repair_hints_pin_pnpm_for_older_node_runtime() -> None:
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

    suggestions = _heuristic_repair_hints(block, result)

    assert suggestions
    assert suggestions[0].title == "Install Node-compatible pnpm"
    assert "PNPM_PACKAGE=pnpm@9" in suggestions[0].command
    assert 'npm install -g "$PNPM_PACKAGE"' in suggestions[0].command


def test_repair_hints_add_python_alias() -> None:
    block = CommandBlock(
        id="03-validation",
        title="Validation",
        goal="Run validation",
        script="#!/bin/sh\npython -m pytest --version\n",
    )
    result = CommandResult(exit_code=127, stderr="sh: 1: python: not found")

    suggestions = _heuristic_repair_hints(block, result)

    assert suggestions
    assert "/usr/local/bin/python" in suggestions[0].command


def test_repair_hints_install_matching_python_venv_package() -> None:
    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\npython3 -m venv .venv\n",
    )
    result = CommandResult(
        exit_code=1,
        stdout=(
            "The virtual environment was not created successfully because ensurepip is not\n"
            "available. On Debian/Ubuntu systems, you need to install the python3-venv\n"
            "package using the following command.\n\n"
            "    apt install python3.12-venv\n"
        ),
    )

    suggestions = _heuristic_repair_hints(block, result)

    assert suggestions
    assert suggestions[0].title == "Install Python venv package"
    assert "python3.12-venv" in suggestions[0].command
    assert "python3 -m venv /tmp/pheragent-venv-check" in suggestions[0].command
    assert "python3.12-venv" in suggestions[0].patch_script


def test_repair_hints_include_qt_opencv_runtime_bundle() -> None:
    block = CommandBlock(
        id="04-build-test-prep",
        title="Build Test Prep",
        goal="Run tests",
        script="#!/bin/sh\n.venv/bin/python -m pytest --collect-only\n",
    )
    result = CommandResult(
        exit_code=1,
        stderr="ImportError: libGL.so.1: cannot open shared object file",
    )

    suggestions = _heuristic_repair_hints(block, result)

    qt_hint = next(
        suggestion
        for suggestion in suggestions
        if suggestion.title == "Install Qt/OpenCV runtime libraries"
    )
    assert "libgl1" in qt_hint.command
    assert "libegl1" in qt_hint.command
    assert "libxkbcommon0" in qt_hint.command
    assert "libglib2.0-0t64" in qt_hint.command


def test_repair_hints_dedupe_duplicate_requirements_without_repo_edit() -> None:
    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\n.venv/bin/python -m pip install -r requirements.txt\n",
    )
    result = CommandResult(
        exit_code=1,
        stderr=(
            "ERROR: Double requirement given: Jinja2 (from -r requirements.txt "
            "(line 30)) (already in Jinja2==3.1.2 (from -r requirements.txt "
            "(line 5)), name='Jinja2')"
        ),
    )

    suggestions = _heuristic_repair_hints(block, result)

    hint = next(
        suggestion
        for suggestion in suggestions
        if suggestion.title == "Install deduplicated requirements copy"
    )
    assert "/tmp/pheragent-requirements.dedup.txt" in hint.command
    assert "pip install -r /tmp/pheragent-requirements.dedup.txt" in hint.command
    assert "requirements.txt').read_text()" in hint.command
    assert ".write_text(" not in hint.command
    assert "sed -i" not in hint.command


def test_repair_hints_relax_dunder_version_validation() -> None:
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

    suggestions = _heuristic_repair_hints(block, result)
    patched = RepairPlanner().patch_block(block, suggestions[0])

    assert suggestions
    assert suggestions[0].command == "true"
    assert patched.validation_command == 'uv run python -c "import flask; print(flask)"'


def test_patch_block_normalizes_source_to_posix_dot() -> None:
    block = CommandBlock(
        id="30-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\nset -eu\nsource .venv/bin/activate\npython -m pip install -e .\n",
    )
    repair = RepairCommand(
        title="No-op normalized source",
        command="./.venv/bin/python -m pip --version",
        patch_script="",
    )

    patched = RepairPlanner().patch_block(block, repair)

    assert "source .venv/bin/activate" not in patched.script
    assert ". .venv/bin/activate" in patched.script


def test_repair_hints_do_not_relax_plain_pytest_collect_dependency_failure() -> None:
    block = CommandBlock(
        id="50-test-tooling",
        title="Test Tooling",
        goal="Validate test tooling",
        script="#!/bin/sh\n./.venv/bin/python -m pytest --collect-only -q\n",
        validation_command="./.venv/bin/python -m pytest --collect-only -q",
    )
    result = CommandResult(
        exit_code=1,
        stderr=(
            "/workspace/repo/.venv/bin/python: No module named pytest_mock\n"
            "command was: ./.venv/bin/python -m pytest --collect-only -q"
        ),
    )

    suggestions = _heuristic_repair_hints(block, result)

    assert all(
        suggestion.title != "Relax pytest collection validation" for suggestion in suggestions
    )


def test_repair_hints_relax_pytest_conftest_application_behavior() -> None:
    block = CommandBlock(
        id="50-test-tooling",
        title="Test Tooling",
        goal="Validate test tooling",
        script="#!/bin/sh\n./.venv/bin/python -m pytest --collect-only -q\n",
        validation_command="./.venv/bin/python -m pytest --collect-only -q",
    )
    result = CommandResult(
        exit_code=4,
        stderr=(
            "ImportError while loading conftest '/workspace/repo/tests/conftest.py'.\n"
            "E   ValueError: function azure_gpt35_turbo_16k_llm_config is not a fixture"
        ),
    )

    suggestions = _heuristic_repair_hints(block, result)

    hint = next(
        suggestion
        for suggestion in suggestions
        if suggestion.title == "Relax pytest collection validation"
    )
    assert hint.patch_validation_command == "./.venv/bin/python -m pytest --version"


def test_repair_hints_cover_python312_setuptools_and_opentelemetry_failures() -> None:
    block = CommandBlock(
        id="30-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\n./.venv/bin/python -m pip install -r requirements.txt\n",
    )

    pkg_resources_hints = _heuristic_repair_hints(
        block,
        CommandResult(exit_code=1, stderr="ModuleNotFoundError: No module named pkg_resources"),
    )
    distutils_hints = _heuristic_repair_hints(
        block,
        CommandResult(exit_code=1, stderr="ModuleNotFoundError: No module named 'distutils'"),
    )
    numpy_hints = _heuristic_repair_hints(
        block,
        CommandResult(
            exit_code=1,
            stderr=(
                "AttributeError: module 'pkgutil' has no attribute 'ImpImporter' "
                "while building numpy"
            ),
        ),
    )
    otel_hints = _heuristic_repair_hints(
        block,
        CommandResult(
            exit_code=1,
            stderr="ModuleNotFoundError: No module named 'opentelemetry.instrumentation.openai'",
        ),
    )

    assert any("setuptools<82" in hint.command for hint in pkg_resources_hints)
    assert any("SETUPTOOLS_USE_DISTUTILS=local" in hint.patch_script for hint in distutils_hints)
    assert any("'numpy>=1.26,<2'" in hint.command for hint in numpy_hints)
    assert any("opentelemetry-instrumentation-openai" in hint.command for hint in otel_hints)


def test_failure_localization_keeps_test_tooling_module_failures_local() -> None:
    previous = CommandBlock(
        id="30-python-deps",
        title="Python Dependencies",
        goal="Install Python package requirements",
        script="#!/bin/sh\n.venv/bin/python -m pip install -r requirements.txt\n",
        status="succeeded",
    )
    block = CommandBlock(
        id="50-test-tooling",
        title="Test Tooling",
        goal="Install test runner and validate collection",
        script="#!/bin/sh\n.venv/bin/python -m pytest --collect-only -q\n",
    )
    result = CommandResult(
        exit_code=1,
        stderr="/workspace/repo/.venv/bin/python: No module named pytest_mock",
    )
    context = RepairContext(
        repo_context=RepoContext(repo_path=Path("/repo")),
        checkpoint_before="fake:30-python-deps-success",
        previous_blocks=[previous],
    )

    localization = _heuristic_failure_localization(block, result, context)

    assert localization is not None
    assert localization.root_cause_block_id == "50-test-tooling"


def test_failure_localization_keeps_pytest_argparse_failures_local() -> None:
    previous = CommandBlock(
        id="30-python-deps",
        title="Python Dependencies",
        goal="Install Python package requirements",
        script="#!/bin/sh\n.venv/bin/python -m pip install -r requirements.txt\n",
        status="succeeded",
    )
    block = CommandBlock(
        id="50-test-tooling",
        title="Test Tooling",
        goal="Run pytest collection",
        script="#!/bin/sh\n.venv/bin/python -m pytest --collect-only -q\n",
    )
    result = CommandResult(
        exit_code=2,
        stderr="__main__.py: error: unrecognized arguments: --collect-only -q",
    )
    context = RepairContext(
        repo_context=RepoContext(repo_path=Path("/repo")),
        checkpoint_before="fake:30-python-deps-success",
        previous_blocks=[previous],
    )

    localization = _heuristic_failure_localization(block, result, context)

    assert localization is not None
    assert localization.root_cause_block_id == "50-test-tooling"


def test_patch_block_applies_script_when_validation_is_replaced() -> None:
    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\nset -eu\npython3 -m venv .venv\n",
        validation_command="python3 --version",
    )
    repair = RepairCommand(
        title="Install venv support",
        command="apt-get install -y python3.12-venv",
        patch_script="apt-get install -y python3.12-venv",
        patch_validation_command=".venv/bin/python -m pip --version",
    )

    patched = RepairPlanner().patch_block(block, repair)

    assert "apt-get install -y python3.12-venv" in patched.script
    assert patched.script.index("apt-get install") < patched.script.index("python3 -m venv")
    assert patched.validation_command == ".venv/bin/python -m pip --version"
    assert patched.repair_attempts == 1


def test_patch_block_prepends_patch_even_when_same_snippet_exists_later() -> None:
    patch_script = 'PYTHON_BIN="${PYTHON_BIN:-python3}"\nexport PYTHON_BIN'
    block = CommandBlock(
        id="02-language-deps",
        title="Language Dependencies",
        goal="Install deps",
        script=(
            "#!/bin/sh\n"
            "set -eu\n\n"
            'echo "[pheragent] repair: old broken patch"\n'
            'if [ ! -d .venv ]; then "$PYTHON_BIN" -m venv .venv; fi\n\n'
            f"{patch_script}\n"
        ),
    )
    repair = RepairCommand(
        title="Define PYTHON_BIN before use",
        command="python3 --version",
        patch_script=patch_script,
    )

    patched = RepairPlanner().patch_block(block, repair)
    lines = patched.script.splitlines()

    assert lines[3] == 'echo "[pheragent] repair: Define PYTHON_BIN before use"'
    assert lines[4] == 'PYTHON_BIN="${PYTHON_BIN:-python3}"'
    assert patched.script.index("Define PYTHON_BIN before use") < patched.script.index(
        "old broken patch"
    )


def test_patch_block_does_not_duplicate_same_leading_patch() -> None:
    patch_script = "python3 --version"
    block = CommandBlock(
        id="02-language-deps",
        title="Language Dependencies",
        goal="Install deps",
        script=(
            "#!/bin/sh\n"
            "set -eu\n\n"
            'echo "[pheragent] repair: Check python"\n'
            "python3 --version\n\n"
            "echo original\n"
        ),
    )
    repair = RepairCommand(
        title="Check python",
        command="python3 --version",
        patch_script=patch_script,
    )

    patched = RepairPlanner().patch_block(block, repair)

    assert patched.script.count('echo "[pheragent] repair: Check python"') == 1
    assert patched.script.count("python3 --version") == 1


def test_repair_planner_prefers_llm_suggestions_and_passes_heuristic_hints() -> None:
    class FakeLLMRepairPlanner:
        heuristic_hints: list[RepairCommand] | None = None

        def suggest(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
            heuristic_hints: list[RepairCommand] | None = None,
        ) -> list[RepairCommand]:
            del block, result, context
            self.heuristic_hints = heuristic_hints
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
    llm_planner = FakeLLMRepairPlanner()

    suggestions = RepairPlanner(llm_planner=llm_planner).suggest(block, result)

    assert suggestions[0].title == "Install cmake"
    assert len(suggestions) == 1
    assert llm_planner.heuristic_hints is not None
    assert "build-essential" in llm_planner.heuristic_hints[0].command


def test_repair_planner_does_not_execute_heuristic_hints_when_llm_fails() -> None:
    class FailingLLMRepairPlanner:
        def suggest(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
            heuristic_hints: list[RepairCommand] | None = None,
        ) -> list[RepairCommand]:
            del block, result, context, heuristic_hints
            raise RuntimeError("proxy unavailable")

    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\npip install example\n",
    )
    result = CommandResult(exit_code=1, stderr="gcc: not found")
    planner = RepairPlanner(llm_planner=FailingLLMRepairPlanner())

    suggestions = planner.suggest(block, result)

    assert suggestions == []
    assert planner.last_llm_error == "proxy unavailable"


def test_repair_planner_does_not_execute_hints_without_llm() -> None:
    block = CommandBlock(
        id="02-python-deps",
        title="Python Dependencies",
        goal="Install deps",
        script="#!/bin/sh\npip install example\n",
    )
    result = CommandResult(exit_code=1, stderr="gcc: not found")

    suggestions = RepairPlanner().suggest(block, result)

    assert suggestions == []


def test_repair_planner_records_llm_failure_for_unknown_errors() -> None:
    class FailingLLMRepairPlanner:
        def suggest(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
            heuristic_hints: list[RepairCommand] | None = None,
        ) -> list[RepairCommand]:
            del block, result, context, heuristic_hints
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
    assert "unsafe token 'docker '" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_filters_pure_diagnostic_repairs() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Check python dev",
                        "command": "dpkg-query -W python3-dev build-essential",
                        "patch_script": "dpkg-query -W python3-dev build-essential",
                    },
                    {
                        "title": "Install python dev",
                        "command": (
                            "apt-get update && apt-get install -y "
                            "--no-install-recommends python3-dev build-essential"
                        ),
                        "patch_script": (
                            "apt-get update && apt-get install -y "
                            "--no-install-recommends python3-dev build-essential"
                        ),
                    },
                ]
            }
        )
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Install python dev"
    assert "pure diagnostic/probe command" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_allows_probe_plus_durable_repair() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Install missing python dev package",
                        "command": (
                            "dpkg-query -W python3-dev || apt-get update && "
                            "apt-get install -y --no-install-recommends "
                            "python3-dev build-essential && dpkg-query -W "
                            "python3-dev build-essential"
                        ),
                        "patch_script": (
                            "apt-get update && apt-get install -y "
                            "--no-install-recommends python3-dev build-essential"
                        ),
                    }
                ]
            }
        )
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Install missing python dev package"
    assert planner.last_parse_diagnostics == []


def test_openai_responses_repair_parser_filters_transient_block_script_paths() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        """
        {
          "repairs": [
            {
              "title": "Rerun temp script",
              "command": "python -m pip install pytest && sh /tmp/pheragent/blocks/04.sh",
              "patch_script": "python -m pip install pytest"
            },
            {
              "title": "Install pytest",
              "command": "python -m pip install pytest && python -m pytest --version",
              "patch_script": "python -m pip install pytest"
            }
          ]
        }
        """
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Install pytest"
    assert "transient runtime path" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_filters_test_monkeypatch_files() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        """
        {
          "repairs": [
            {
              "title": "Monkeypatch tests",
              "command": "cat > conftest.py <<'PY'\\nprint('patch')\\nPY",
              "patch_script": "cat > conftest.py <<'PY'\\nprint('patch')\\nPY"
            },
            {
              "title": "Collect tests",
              "command": "python -m pytest --collect-only -q",
              "patch_script": "true",
              "validation_command": "python -m pytest --collect-only -q"
            }
          ]
        }
        """
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Collect tests"
    assert "test monkeypatch file" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_filters_python_source_writes() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())
    source_write_command = (
        "python - <<'PY'\n"
        "from pathlib import Path\n"
        "Path('fastmlx/utils.py').write_text('patch')\n"
        "PY"
    )

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Patch source",
                        "command": source_write_command,
                        "patch_script": source_write_command,
                    },
                    {
                        "title": "Collect tests",
                        "command": "python -m pytest --collect-only -q",
                        "patch_script": "true",
                        "validation_command": "python -m pytest --collect-only -q",
                    },
                ]
            }
        )
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Collect tests"
    assert "python file write token" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_allows_apt_cache_cleanup() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())
    command = (
        "apt-get update && apt-get install -y python3-pytest && "
        "rm -rf /var/lib/apt/lists/*"
    )

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Install pytest",
                        "command": command,
                        "patch_script": command,
                    }
                ]
            }
        )
    )

    assert len(repairs) == 1
    assert repairs[0].title == "Install pytest"
    assert planner.last_parse_diagnostics == []


def test_openai_responses_repair_parser_rejects_absolute_rm_rf_targets() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        """
        {
          "repairs": [
            {
              "title": "Bad cleanup",
              "command": "rm -rf /etc",
              "patch_script": "rm -rf /etc"
            }
          ]
        }
        """
    )

    assert repairs == []
    assert "unsafe absolute rm target" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_allows_common_absolute_cleanup_targets() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())
    command = (
        "rm -rf /workspace/repo/.venv /workspace/repo/node_modules "
        "/workspace/repo/build /tmp/pheragent-cache"
    )

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Clean caches",
                        "command": command,
                        "patch_script": command,
                    }
                ]
            }
        )
    )

    assert len(repairs) == 1
    assert planner.last_parse_diagnostics == []


def test_openai_responses_repair_parser_rejects_workspace_repo_root_cleanup() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Bad cleanup",
                        "command": "rm -rf /workspace/repo",
                        "patch_script": "rm -rf /workspace/repo",
                    }
                ]
            }
        )
    )

    assert repairs == []
    assert "unsafe absolute rm target" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_checks_all_rm_rf_targets() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs(
        json.dumps(
            {
                "repairs": [
                    {
                        "title": "Mixed cleanup",
                        "command": "rm -rf /tmp/pheragent-cache /etc",
                        "patch_script": "rm -rf /tmp/pheragent-cache /etc",
                    }
                ]
            }
        )
    )

    assert repairs == []
    assert "unsafe absolute rm target '/etc'" in planner.last_parse_diagnostics[0]


def test_openai_responses_repair_parser_records_empty_repairs_diagnostic() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    repairs = planner._parse_repairs('{"repairs": []}')

    assert repairs == []
    assert planner.last_parse_diagnostics == ["repairs list is empty"]


def test_openai_responses_probe_parser_filters_mutating_commands() -> None:
    planner = OpenAIResponsesRepairPlanner(OpenAIResponsesRepairConfig())

    probes = planner._parse_probes(
        """
        {
          "probes": [
            {
              "title": "Bad install",
              "command": "python3 -m pip install pytest"
            },
            {
              "title": "Read pyproject",
              "command": "sed -n '1,120p' pyproject.toml"
            }
          ]
        }
        """
    )

    assert len(probes) == 1
    assert probes[0].title == "Read pyproject"
    assert "mutating or network token" in planner.last_probe_parse_diagnostics[0]


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
            task_description="Setup target: run a CMake-backed import smoke test.",
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
        probe_results=[
            RepairProbeResult(
                title="Check cmake",
                command="command -v cmake || true",
                exit_code=0,
                timed_out=False,
                stdout_tail="",
                stderr_tail="",
            )
        ],
    )

    heuristic_hints = [
        RepairCommand(
            title="Install cmake",
            command="apt-get update && apt-get install -y cmake",
            patch_script="apt-get update && apt-get install -y cmake",
        )
    ]

    payload = planner._request_payload(
        block,
        result,
        context,
        heuristic_hints=heuristic_hints,
    )
    assert isinstance(payload["input"], list)
    assert payload["input"][0]["role"] == "user"
    input_text = payload["input"][0]["content"][0]
    assert input_text["type"] == "input_text"
    content = json.loads(input_text["text"])

    assert content["output_instructions"] == "Return JSON only."
    assert "json" in input_text["text"].lower()
    assert content["repair_context"]["checkpoint_before"] == "fake:baseline"
    assert content["repair_context"]["repo_context"]["task_description"] == (
        "Setup target: run a CMake-backed import smoke test."
    )
    assert "tool:cmake=missing" in content["repair_context"]["repo_context"]["runtime_notes"]
    assert content["repair_context"]["previous_blocks"][0]["id"] == "00-preflight"
    assert content["repair_context"]["recent_executions"][0]["phase"] == "block"
    assert content["repair_context"]["probe_results"][0]["title"] == "Check cmake"
    assert content["heuristic_hints"][0]["title"] == "Install cmake"
    assert payload["stream"] is True
    assert payload["text"] == {"format": {"type": "json_object"}}
    assert "max_output_tokens" not in payload
    assert "temperature" not in payload

    probe_payload = planner._probe_request_payload(block, result, context)
    assert isinstance(probe_payload["input"], list)
    assert probe_payload["input"][0]["content"][0]["type"] == "input_text"
    probe_text = probe_payload["input"][0]["content"][0]["text"]
    probe_content = json.loads(probe_text)
    assert probe_content["output_instructions"] == "Return JSON only."
    assert "json" in probe_text.lower()
    assert probe_content["repair_context"]["checkpoint_before"] == "fake:baseline"
    assert probe_content["repair_context"]["repo_context"]["task_description"] == (
        "Setup target: run a CMake-backed import smoke test."
    )
    assert "max_output_tokens" not in probe_payload
    assert "temperature" not in probe_payload

    localization_payload = planner._localization_request_payload(block, result, context)
    assert isinstance(localization_payload["input"], list)
    localization_text = localization_payload["input"][0]["content"][0]["text"]
    localization_content = json.loads(localization_text)
    assert localization_content["repair_context"]["previous_blocks"][0]["id"] == "00-preflight"
    assert "json" in localization_text.lower()

    localization = planner._parse_localization(
        '{"root_cause_block_id":"00-preflight","rationale":"missing prior tool"}'
    )
    assert localization is not None
    assert localization.root_cause_block_id == "00-preflight"
    assert localization.rationale == "missing prior tool"


def test_openai_chat_completions_repair_uses_chat_payload_and_usage() -> None:
    class FakeChatCompletions:
        def __init__(self):
            self.calls: list[dict[str, object]] = []

        def create(self, **payload):
            self.calls.append(payload)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "repairs": [
                                        {
                                            "title": "Install cmake",
                                            "command": "apt-get update && apt-get install -y cmake",
                                            "patch_script": (
                                                "apt-get update && apt-get install -y cmake"
                                            ),
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 21,
                    "completion_tokens": 9,
                    "completion_tokens_details": {"reasoning_tokens": 4},
                    "total_tokens": 30,
                },
            }

    class FakeClient:
        def __init__(self):
            self.chat = type("FakeChat", (), {"completions": FakeChatCompletions()})()

    planner = OpenAIResponsesRepairPlanner(
        OpenAIResponsesRepairConfig(api_mode="chat-completions")
    )
    block = CommandBlock(
        id="02-build",
        title="Build",
        goal="compile",
        script="#!/bin/sh\nmake\n",
    )
    result = CommandResult(exit_code=1, stderr="cmake: not found")

    payload = planner._request_payload(block, result)
    assert payload["response_format"] == {"type": "json_object"}
    assert "input" not in payload
    assert "text" not in payload
    assert "stream" not in payload
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert "json" in payload["messages"][1]["content"].lower()

    probe_payload = planner._probe_request_payload(block, result)
    assert probe_payload["response_format"] == {"type": "json_object"}
    assert "input" not in probe_payload
    assert "stream" not in probe_payload

    client = FakeClient()
    content = planner._create_response(
        client,
        payload,
        error_context="LLM repair",
        usage_phase="repair",
    )

    repairs = planner._parse_repairs(content)
    assert repairs[0].title == "Install cmake"
    assert client.chat.completions.calls[0] == payload
    assert planner.usage_summary()["total"] == {
        "requests": 1,
        "input_tokens": 21,
        "output_tokens": 9,
        "reasoning_tokens": 4,
        "total_tokens": 30,
    }


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
