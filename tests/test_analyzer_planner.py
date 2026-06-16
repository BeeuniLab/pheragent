from __future__ import annotations

from pathlib import Path

from pheragent.analyzer import RepoAnalyzer
from pheragent.planner import RuleBasedBlockPlanner


def test_analyzer_detects_python_uv_repo(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    context = RepoAnalyzer().analyze(tmp_path)

    assert context.languages == ["python"]
    assert "uv" in context.package_managers
    assert "python -m pytest -q" in context.test_commands


def test_rule_based_planner_writes_preflight_and_python_blocks(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)

    blocks = RuleBasedBlockPlanner().plan(context)

    assert [block.id for block in blocks] == ["00-preflight", "01-python-deps"]
    assert "pip install" in blocks[1].script
    assert "pip install pytest" in blocks[1].script
    assert blocks[1].script.startswith("#!/bin/sh")


def test_rule_based_planner_collects_pytest_without_running_full_suite(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    context = RepoAnalyzer().analyze(tmp_path)

    blocks = RuleBasedBlockPlanner().plan(context)

    assert blocks[1].validation_command == "python -m pytest --collect-only -q"


def test_rule_based_planner_installs_node_compatible_pnpm(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build"}}', encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
    context = RepoAnalyzer().analyze(tmp_path)

    blocks = RuleBasedBlockPlanner().plan(context)
    node_block = next(block for block in blocks if block.id.endswith("node-deps"))

    assert "ensure_pnpm" in node_block.script
    assert "PNPM_PACKAGE=pnpm@9" in node_block.script
    assert 'npm install -g "$PNPM_PACKAGE"' in node_block.script
