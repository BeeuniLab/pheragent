from __future__ import annotations

from pathlib import Path

from pheragent.block_store import BlockStore
from pheragent.models import (
    BuildRequest,
    Checkpoint,
    CommandBlock,
    CommandResult,
    RepairContext,
    RepoContext,
)
from pheragent.orchestrator import EnvironmentBuilder
from pheragent.repair import RepairCommand, RepairPlanner, RepairProbeCommand


class FakeRuntime:
    instances: list[FakeRuntime] = []
    base_image = "fake:base"

    def __init__(self, request: BuildRequest, run_id: str):
        type(self).instances.append(self)
        self.request = request
        self.run_id = run_id
        self.started: list[str] = []
        self.recreated: list[str] = []
        self.commits: list[str] = []
        self.block_runs = 0

    def build_base_image(self) -> CommandResult:
        return CommandResult(exit_code=0, stdout="built")

    def start(self, image_ref: str | None = None, *, seed_repo: bool = False) -> str:
        self.started.append(image_ref or self.base_image)
        if seed_repo:
            self.started.append("seed_repo")
        return "container"

    def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
        del timeout
        self.block_runs += 1
        script = script_path.read_text(encoding="utf-8")
        if "build-essential" not in script and "python-deps" in script_path.name:
            return CommandResult(exit_code=1, stderr="gcc: not found")
        return CommandResult(exit_code=0, stdout="ok")

    def execute_command(self, command: str, *, timeout: float) -> CommandResult:
        del timeout
        if "container preflight" in command:
            return CommandResult(
                exit_code=0,
                stdout="tool:python3=/usr/bin/python3\npython.version=3.12.0\n",
            )
        if "pytest" in command:
            return CommandResult(exit_code=0, stdout="tests ok")
        if "build-essential" in command:
            return CommandResult(exit_code=0, stdout="installed")
        return CommandResult(exit_code=0, stdout="ok")

    def commit(
        self,
        *,
        block_id: str | None,
        parent_image_ref: str | None,
        kind: str,
    ) -> Checkpoint:
        image_ref = f"fake:{block_id}-{kind}"
        self.commits.append(image_ref)
        return Checkpoint(
            id=f"cp-{len(self.commits)}",
            image_ref=image_ref,
            block_id=block_id,
            parent_image_ref=parent_image_ref,
            kind=kind,
        )

    def recreate_from(self, image_ref: str) -> str:
        self.recreated.append(image_ref)
        return "container"

    def cleanup(self) -> None:
        pass


class BuildEssentialLLMRepairPlanner:
    def suggest(
        self,
        block: CommandBlock,
        result: CommandResult,
        *,
        context: RepairContext | None = None,
        heuristic_hints: list[RepairCommand] | None = None,
    ) -> list[RepairCommand]:
        del block, result, context, heuristic_hints
        return [
            RepairCommand(
                title="Install build-essential",
                command="apt-get update && apt-get install -y build-essential",
                patch_script="apt-get update && apt-get install -y build-essential",
            )
        ]


def test_environment_builder_repairs_failed_block_and_persists_patch(tmp_path: Path) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="test-run",
        max_repair_attempts=1,
    )

    result = EnvironmentBuilder(
        request,
        repair_planner=RepairPlanner(llm_planner=BuildEssentialLLMRepairPlanner()),
        runtime_factory=FakeRuntime,
    ).build()

    assert result.ok
    python_block = next(block for block in result.blocks if block.id == "01-python-deps")
    assert python_block.status == "succeeded"
    assert "build-essential" in (result.scripts_dir / "01-python-deps.sh").read_text(
        encoding="utf-8"
    )
    assert any(execution.phase == "repair" for execution in result.executions)
    runtime = FakeRuntime.instances[-1]
    assert runtime.recreated.count("fake:00-preflight-success") == 2
    first_log = Path(result.executions[0].log_path or "")
    assert first_log.is_file()
    assert '"phase": "docker_build"' in first_log.read_text(encoding="utf-8")
    assert '"log_path"' in (result.state_dir / "executions.jsonl").read_text(encoding="utf-8")


def test_environment_builder_passes_probe_results_to_llm_repair(tmp_path: Path) -> None:
    class ProbeRuntime(FakeRuntime):
        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            script = script_path.read_text(encoding="utf-8")
            if "cmake" not in script:
                return CommandResult(exit_code=1, stderr="cmake: not found")
            return CommandResult(exit_code=0, stdout="ok")

        def execute_command(self, command: str, *, timeout: float) -> CommandResult:
            del timeout
            if "container preflight" in command:
                return CommandResult(exit_code=0, stdout="tool:python3=/usr/bin/python3\n")
            if "command -v cmake" in command:
                return CommandResult(exit_code=0, stdout="cmake missing\n")
            if "cmake" in command:
                return CommandResult(exit_code=0, stdout="installed cmake")
            return CommandResult(exit_code=0, stdout="ok")

    class ProbeAwareLLMRepairPlanner:
        def __init__(self) -> None:
            self.repair_contexts: list[RepairContext | None] = []
            self.last_probe_raw_response = (
                '{"probes":[{"title":"Check cmake",'
                '"command":"command -v cmake || echo cmake missing"}]}'
            )
            self.last_probe_parse_diagnostics: list[str] = []
            self.last_raw_response = (
                '{"repairs":[{"title":"Install cmake",'
                '"command":"apt-get update && apt-get install -y cmake",'
                '"patch_script":"apt-get update && apt-get install -y cmake"}]}'
            )
            self.last_parse_diagnostics: list[str] = []

        def propose_probes(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
            heuristic_hints: list[RepairCommand] | None = None,
        ) -> list[RepairProbeCommand]:
            del block, result, context, heuristic_hints
            return [
                RepairProbeCommand(
                    title="Check cmake",
                    command="command -v cmake || echo cmake missing",
                )
            ]

        def suggest(
            self,
            block: CommandBlock,
            result: CommandResult,
            *,
            context: RepairContext | None = None,
            heuristic_hints: list[RepairCommand] | None = None,
        ) -> list[RepairCommand]:
            del block, result, heuristic_hints
            self.repair_contexts.append(context)
            assert context is not None
            assert context.probe_results
            assert "cmake missing" in context.probe_results[0].stdout_tail
            return [
                RepairCommand(
                    title="Install cmake",
                    command="apt-get update && apt-get install -y cmake",
                    patch_script="apt-get update && apt-get install -y cmake",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="probe-repair",
        max_repair_attempts=1,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-python-deps",
                title="Python Dependencies",
                goal="install",
                script="#!/bin/sh\necho python-deps\n",
                order=1,
            )
        ]
    )
    llm_planner = ProbeAwareLLMRepairPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=llm_planner),
        runtime_factory=ProbeRuntime,
    ).build()

    assert result.ok
    assert llm_planner.repair_contexts
    assert any(execution.phase == "llm_probe" for execution in result.executions)
    assert any(execution.phase == "probe" for execution in result.executions)


class StaticPlanner:
    def __init__(self, blocks: list[CommandBlock]):
        self.blocks = blocks
        self.calls = 0
        self.contexts: list[RepoContext] = []

    def plan(self, context: RepoContext) -> list[CommandBlock]:
        self.calls += 1
        self.contexts.append(context)
        return self.blocks


class FailingPlanner:
    def plan(self, context: RepoContext) -> list[CommandBlock]:
        del context
        raise AssertionError("resume should reuse existing block scripts")


def test_environment_builder_plans_with_container_preflight_context(tmp_path: Path) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    planner = StaticPlanner(
        [
            CommandBlock(
                id="00-tooling",
                title="Tooling",
                goal="inspect",
                script="#!/bin/sh\necho ok\n",
                order=0,
            )
        ]
    )
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="runtime-context",
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    assert result.ok
    assert planner.calls == 1
    assert "tool:python3=/usr/bin/python3" in planner.contexts[0].runtime_notes
    runtime = FakeRuntime.instances[-1]
    assert runtime.recreated == []
    assert any(execution.phase == "container_preflight" for execution in result.executions)
    assert "python.version=3.12.0" in (result.state_dir / "context.json").read_text(
        encoding="utf-8"
    )


def test_environment_builder_logs_failed_llm_repair_attempt(tmp_path: Path) -> None:
    class UnknownFailureRuntime(FakeRuntime):
        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del script_path, timeout
            return CommandResult(exit_code=1, stderr="mystery failure")

    class FailingLLMRepairPlanner:
        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            raise RuntimeError("proxy unavailable")

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="llm-repair-log",
        max_repair_attempts=1,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-custom",
                title="Custom",
                goal="install",
                script="#!/bin/sh\necho custom\n",
                order=1,
            )
        ]
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=FailingLLMRepairPlanner()),
        runtime_factory=UnknownFailureRuntime,
    ).build()

    assert not result.ok
    llm_execution = next(
        execution for execution in result.executions if execution.phase == "llm_repair"
    )
    assert "proxy unavailable" in Path(llm_execution.log_path or "").read_text(encoding="utf-8")


def test_environment_builder_retries_empty_llm_repair_suggestions(
    tmp_path: Path,
) -> None:
    class UnknownFailureRuntime(FakeRuntime):
        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del script_path, timeout
            return CommandResult(exit_code=1, stderr="mystery failure")

    class EmptyLLMRepairPlanner:
        def __init__(self) -> None:
            self.calls = 0
            self.last_raw_response = '{"repairs": []}'
            self.last_parse_diagnostics = ["repairs list is empty"]

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.calls += 1
            return []

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="llm-repair-empty",
        max_repair_attempts=3,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-custom",
                title="Custom",
                goal="install",
                script="#!/bin/sh\necho custom\n",
                order=1,
            )
        ]
    )
    llm_planner = EmptyLLMRepairPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=llm_planner),
        runtime_factory=UnknownFailureRuntime,
    ).build()

    assert not result.ok
    assert llm_planner.calls == 3
    llm_executions = [
        execution for execution in result.executions if execution.phase == "llm_repair"
    ]
    assert [execution.attempt for execution in llm_executions] == [1, 2, 3]
    first_log = Path(llm_executions[0].log_path or "").read_text(encoding="utf-8")
    assert "--- raw_llm_response ---" in first_log
    assert '{"repairs": []}' in first_log
    assert "repairs list is empty" in first_log


def test_environment_builder_resumes_from_checkpoint_without_replanning(
    tmp_path: Path,
) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    blocks = [
        CommandBlock(
            id="00-preflight",
            title="Preflight",
            goal="inspect",
            script="#!/bin/sh\necho preflight\n",
            order=0,
        ),
        CommandBlock(
            id="01-tooling",
            title="Tooling",
            goal="install tools",
            script="#!/bin/sh\necho tooling\n",
            order=1,
        ),
    ]
    state_dir = tmp_path / ".pheragent"
    run_dir = state_dir / "runs" / "resume-run"
    BlockStore(run_dir).write_blocks(blocks)
    resume_image = "pheragent:resume-run-002-00-preflight-success"
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=None,
        state_dir=state_dir,
        run_id="resume-run",
        resume_from=resume_image,
    )

    result = EnvironmentBuilder(
        request,
        planner=FailingPlanner(),
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    runtime = FakeRuntime.instances[-1]
    assert result.ok
    assert result.final_image == "fake:01-tooling-success"
    assert runtime.started[0] == resume_image
    assert "seed_repo" not in runtime.started
    assert not any(execution.phase == "docker_build" for execution in result.executions)
    assert result.blocks[0].status == "skipped"
    assert result.blocks[1].status == "succeeded"


def test_environment_builder_start_at_block_overrides_resume_tag(tmp_path: Path) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    blocks = [
        CommandBlock(
            id="00-preflight",
            title="Preflight",
            goal="inspect",
            script="#!/bin/sh\necho preflight\n",
            order=0,
        ),
        CommandBlock(
            id="01-tooling",
            title="Tooling",
            goal="install tools",
            script="#!/bin/sh\necho tooling\n",
            order=1,
        ),
    ]
    planner = StaticPlanner(blocks)
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=None,
        state_dir=tmp_path / ".pheragent",
        run_id="resume-explicit",
        resume_from="custom:image",
        start_at_block="01-tooling",
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    assert result.ok
    assert planner.calls == 1
    assert result.blocks[0].status == "skipped"
    assert result.blocks[1].status == "succeeded"
