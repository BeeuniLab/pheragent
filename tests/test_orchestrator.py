from __future__ import annotations

import json
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
from pheragent.orchestrator import EnvironmentBuilder, _split_shell_script_commands
from pheragent.repair import (
    FailureLocalization,
    RepairCommand,
    RepairPlanner,
    RepairProbeCommand,
)


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
        self.command_sequences: list[list[str]] = []
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

    def execute_command_sequence(
        self,
        commands: list[str],
        *,
        timeout: float,
    ) -> list[CommandResult]:
        del timeout
        self.command_sequences.append(commands)
        return [
            CommandResult(
                exit_code=0,
                stdout="ok",
                command=["pheragent-command-forward-persistent", str(index), command],
            )
            for index, command in enumerate(commands, start=1)
        ]

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
    python_block = next(block for block in result.blocks if block.id == "30-python-deps")
    assert python_block.status == "succeeded"
    assert "build-essential" in (result.scripts_dir / "30-python-deps.sh").read_text(
        encoding="utf-8"
    )
    assert any(execution.phase == "repair" for execution in result.executions)
    runtime = FakeRuntime.instances[-1]
    assert runtime.recreated.count("fake:20-python-runtime-success") == 2
    first_log = Path(result.executions[0].log_path or "")
    assert first_log.is_file()
    assert '"phase": "docker_build"' in first_log.read_text(encoding="utf-8")
    assert '"log_path"' in (result.state_dir / "executions.jsonl").read_text(encoding="utf-8")


def test_environment_builder_repairs_earlier_localized_block_and_replays_suffix(
    tmp_path: Path,
) -> None:
    class EarlierRootRuntime(FakeRuntime):
        def __init__(self, request: BuildRequest, run_id: str):
            super().__init__(request, run_id)
            self.has_correct_runtime = False
            self.script_runs: list[str] = []

        def recreate_from(self, image_ref: str) -> str:
            self.has_correct_runtime = False
            return super().recreate_from(image_ref)

        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            self.script_runs.append(script_path.name)
            script = script_path.read_text(encoding="utf-8")
            if script_path.name == "20-runtime.sh":
                if "install-correct-runtime" in script:
                    self.has_correct_runtime = True
                return CommandResult(exit_code=0, stdout="runtime ok")
            if script_path.name == "50-validation.sh" and not self.has_correct_runtime:
                return CommandResult(exit_code=1, stderr="wrong runtime selected")
            return CommandResult(exit_code=0, stdout="ok")

    class EarlierRootLLMRepairPlanner:
        def __init__(self) -> None:
            self.localized_blocks: list[str] = []
            self.repaired_blocks: list[str] = []

        def localize_failure(self, block, result, *, context=None, heuristic_hints=None):
            del result, heuristic_hints
            assert context is not None
            self.localized_blocks.append(block.id)
            return FailureLocalization(
                root_cause_block_id="20-runtime",
                rationale="validation failure came from runtime choice",
            )

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del result, context, heuristic_hints
            self.repaired_blocks.append(block.id)
            return [
                RepairCommand(
                    title="Install correct runtime",
                    command="install-correct-runtime",
                    patch_script="echo install-correct-runtime",
                )
            ]

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
            id="20-runtime",
            title="Runtime",
            goal="install runtime",
            script="#!/bin/sh\necho runtime\n",
            order=20,
        ),
        CommandBlock(
            id="30-deps",
            title="Dependencies",
            goal="install deps",
            script="#!/bin/sh\necho deps\n",
            order=30,
        ),
        CommandBlock(
            id="50-validation",
            title="Validation",
            goal="validate runtime",
            script="#!/bin/sh\necho validate\n",
            order=50,
        ),
    ]
    llm_planner = EarlierRootLLMRepairPlanner()
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="earlier-root",
        max_repair_attempts=1,
        ablation_mode="without-final-clean-replay",
    )

    result = EnvironmentBuilder(
        request,
        planner=StaticPlanner(blocks),
        repair_planner=RepairPlanner(llm_planner=llm_planner),
        runtime_factory=EarlierRootRuntime,
    ).build()

    assert result.ok
    assert llm_planner.localized_blocks == ["50-validation"]
    assert llm_planner.repaired_blocks == ["20-runtime"]
    runtime = FakeRuntime.instances[-1]
    assert runtime.recreated.count("fake:00-preflight-success") == 2
    assert runtime.script_runs == [
        "00-preflight.sh",
        "20-runtime.sh",
        "30-deps.sh",
        "50-validation.sh",
        "20-runtime.sh",
        "30-deps.sh",
        "50-validation.sh",
    ]
    assert "install-correct-runtime" in (
        result.scripts_dir / "20-runtime.sh"
    ).read_text(encoding="utf-8")


def test_environment_builder_full_ablation_runs_final_clean_replay(tmp_path: Path) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="full-ablation",
        ablation_mode="full",
    )
    planner = StaticPlanner(
        [
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
                goal="install",
                script="#!/bin/sh\necho tooling\n",
                order=1,
            ),
        ]
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    runtime = FakeRuntime.instances[-1]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.ok
    assert result.ablation_mode == "full"
    assert manifest["ablation_mode"] == "full"
    assert manifest["progress_control"]["final_clean_replay"] is True
    assert manifest["final_clean_replay_enabled"] is True
    assert manifest["final_clean_replay_ok"] is True
    assert manifest["final_clean_replay_image"] == "fake:final-clean-replay-clean-replay"
    assert manifest["final_clean_replay_failure_stage"] is None
    assert "fake:final-clean-replay-clean-replay" in runtime.commits
    assert result.final_image == "fake:final-clean-replay-clean-replay"
    assert result.final_clean_replay_ok is True
    assert result.final_clean_replay_image == "fake:final-clean-replay-clean-replay"
    assert any(execution.phase == "clean_replay" for execution in result.executions)
    assert runtime.recreated[-1] == "fake:None-workspace"


def test_split_shell_script_commands_preserves_structured_chunks() -> None:
    script = """#!/bin/sh
set -eu
export PATH="/opt/bin:$PATH"
cd src
if [ -f requirements.txt ]; then
  python -m pip install -r requirements.txt
fi
cat > /tmp/demo.txt <<'EOF'
hello
EOF
build_docs() {
  echo docs
}
build_docs
"""

    commands = _split_shell_script_commands(script)

    assert commands[0] == 'export PATH="/opt/bin:$PATH"'
    assert commands[1] == "cd src"
    assert commands[2].startswith("if [ -f requirements.txt ]; then")
    assert commands[2].endswith("fi")
    assert "python -m pip install -r requirements.txt" in commands[2]
    assert commands[3] == "cat > /tmp/demo.txt <<'EOF'\nhello\nEOF"
    assert commands[4] == "build_docs() {\n  echo docs\n}"
    assert commands[5] == "build_docs"


def test_environment_builder_single_command_forward_executes_commands(
    tmp_path: Path,
) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="single-command-forward",
        ablation_mode="single-command-forward",
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-tooling",
                title="Tooling",
                goal="install",
                script=(
                    "#!/bin/sh\n"
                    "set -eu\n"
                    "export DEMO_FLAG=1\n"
                    "cd src\n"
                    "echo one\n"
                    "echo two\n"
                    "build_docs() {\n"
                    "  echo docs\n"
                    "}\n"
                    "build_docs\n"
                ),
                order=1,
            ),
        ]
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    command_forward = [
        execution for execution in result.executions if execution.phase == "command_forward"
    ]
    command_texts = [execution.command[-1] for execution in command_forward if execution.command]
    runtime = next(instance for instance in FakeRuntime.instances if instance.command_sequences)

    assert result.ok
    assert result.progress_control is not None
    assert result.progress_control.forward_granularity == "command"
    assert result.final_clean_replay_ok is True
    assert len(command_forward) == 6
    assert runtime.command_sequences == [
        [
            "export DEMO_FLAG=1",
            "cd src",
            "echo one",
            "echo two",
            "build_docs() {\n  echo docs\n}",
            "build_docs",
        ]
    ]
    assert command_texts == runtime.command_sequences[0]
    assert not any(execution.phase == "block" for execution in result.executions)
    assert any(execution.phase == "clean_replay" for execution in result.executions)


def test_environment_builder_single_command_recovery_repairs_live_container(
    tmp_path: Path,
) -> None:
    class CommandRecoveryRuntime(FakeRuntime):
        def __init__(self, request: BuildRequest, run_id: str):
            super().__init__(request, run_id)
            self.block_script_runs = 0
            self.repaired = False

        def recreate_from(self, image_ref: str) -> str:
            self.repaired = False
            return super().recreate_from(image_ref)

        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            if script_path.name == "01-tooling.sh":
                self.block_script_runs += 1
                if self.block_script_runs == 1:
                    return CommandResult(exit_code=1, stderr="missing cli")
                self.repaired = True
            return CommandResult(exit_code=0, stdout="block ok")

        def execute_command(self, command: str, *, timeout: float) -> CommandResult:
            del timeout
            if "container preflight" in command:
                return CommandResult(exit_code=0, stdout="tool:python3=/usr/bin/python3\n")
            if command == "install-missing-cli":
                self.repaired = True
                return CommandResult(exit_code=0, stdout="installed")
            if command == "validate-live":
                if self.repaired:
                    return CommandResult(exit_code=0, stdout="validation ok")
                return CommandResult(exit_code=1, stderr="still missing")
            return CommandResult(exit_code=0, stdout="ok")

    class CommandRecoveryPlanner:
        def __init__(self) -> None:
            self.contexts: list[RepairContext | None] = []

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, heuristic_hints
            self.contexts.append(context)
            return [
                RepairCommand(
                    title="Install missing CLI",
                    command="install-missing-cli",
                    patch_script="echo should-not-be-patched",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="single-command-recovery",
        ablation_mode="single-command-recovery",
        max_repair_attempts=1,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-tooling",
                title="Tooling",
                goal="install",
                script="#!/bin/sh\necho install\n",
                validation_command="validate-live",
                order=1,
            ),
        ]
    )
    repair_llm = CommandRecoveryPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=repair_llm),
        runtime_factory=CommandRecoveryRuntime,
    ).build()

    runtime = FakeRuntime.instances[-1]
    script = (result.scripts_dir / "01-tooling.sh").read_text(encoding="utf-8")
    phases = [execution.phase for execution in result.executions]

    assert result.ok
    assert result.progress_control is not None
    assert result.progress_control.recovery_granularity == "command"
    assert result.progress_control.patch_back is False
    assert result.progress_control.checkpoint_rollback is False
    assert "should-not-be-patched" not in script
    assert phases.count("block") == 1
    assert "command_recovery" in phases
    assert "repair" not in phases
    assert "repair_prep" not in phases
    assert runtime.recreated == ["fake:None-workspace"]
    assert repair_llm.contexts
    assert repair_llm.contexts[0] is not None
    assert repair_llm.contexts[0].strategy_notes
    assert result.final_clean_replay_ok is True


def test_environment_builder_whole_script_forward_executes_one_artifact(
    tmp_path: Path,
) -> None:
    class WholeScriptRuntime(FakeRuntime):
        def __init__(self, request: BuildRequest, run_id: str):
            super().__init__(request, run_id)
            self.script_names: list[str] = []

        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            self.script_names.append(script_path.name)
            return super().execute_script(script_path, timeout=timeout)

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="whole-script-forward",
        ablation_mode="whole-script-forward",
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-system",
                title="System",
                goal="install system deps",
                script="#!/bin/sh\ncd subdir\necho system\n",
                order=1,
            ),
            CommandBlock(
                id="02-python",
                title="Python",
                goal="install python deps",
                script="#!/bin/sh\nset -eu\necho python\n",
                validation_command="python -m pytest --collect-only",
                order=2,
            ),
        ]
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(),
        runtime_factory=WholeScriptRuntime,
    ).build()

    runtime = FakeRuntime.instances[-1]
    whole_script = (result.scripts_dir / "whole-setup.sh").read_text(encoding="utf-8")
    phases = [execution.phase for execution in result.executions]

    assert result.ok
    assert result.progress_control is not None
    assert result.progress_control.forward_granularity == "whole-script"
    assert result.progress_control.local_repair is False
    assert result.progress_control.checkpoint_rollback is False
    assert runtime.script_names == ["whole-setup.sh", "whole-setup.sh"]
    assert whole_script.count("cd /workspace/repo") == 3
    assert (
        "cd subdir\n"
        "echo system\n\n"
        "cd /workspace/repo\n"
        "echo '[pheragent] whole-script block 02-python: Python'"
    ) in whole_script
    assert "echo system" in whole_script
    assert "echo python" in whole_script
    assert "whole_script" in phases
    assert "block" not in phases
    assert "fake:whole-script-success" in runtime.commits
    assert "fake:01-system-success" not in runtime.commits
    assert "fake:02-python-success" not in runtime.commits
    assert {block.success_checkpoint for block in result.blocks} == {
        "fake:whole-script-success"
    }
    assert result.final_clean_replay_ok is True
    assert result.final_image == "fake:final-clean-replay-clean-replay"


def test_environment_builder_whole_script_recovery_replays_from_workspace(
    tmp_path: Path,
) -> None:
    class WholeScriptRecoveryRuntime(FakeRuntime):
        def __init__(self, request: BuildRequest, run_id: str):
            super().__init__(request, run_id)
            self.script_names: list[str] = []

        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            self.script_names.append(script_path.name)
            self.block_runs += 1
            if script_path.name == "02-python.sh":
                return CommandResult(exit_code=1, stderr="missing package")
            return CommandResult(exit_code=0, stdout="script ok")

        def execute_command(self, command: str, *, timeout: float) -> CommandResult:
            del timeout
            if "container preflight" in command:
                return CommandResult(exit_code=0, stdout="tool:python3=/usr/bin/python3\n")
            return CommandResult(exit_code=0, stdout="ok")

    class WholeScriptRecoveryPlanner:
        def __init__(self) -> None:
            self.contexts: list[RepairContext | None] = []

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, heuristic_hints
            self.contexts.append(context)
            return [
                RepairCommand(
                    title="Install missing package",
                    command="install-package",
                    patch_script="echo install-package",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="whole-script-recovery",
        ablation_mode="whole-script-recovery",
        max_repair_attempts=1,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-system",
                title="System",
                goal="install system deps",
                script="#!/bin/sh\necho system\n",
                order=1,
            ),
            CommandBlock(
                id="02-python",
                title="Python",
                goal="install python deps",
                script="#!/bin/sh\necho python\n",
                order=2,
            ),
            CommandBlock(
                id="03-final",
                title="Final",
                goal="finish setup",
                script="#!/bin/sh\necho final\n",
                order=3,
            ),
        ]
    )
    repair_llm = WholeScriptRecoveryPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=repair_llm),
        runtime_factory=WholeScriptRecoveryRuntime,
    ).build()

    runtime = FakeRuntime.instances[-1]
    whole_script = (result.scripts_dir / "whole-setup.sh").read_text(encoding="utf-8")
    phases = [execution.phase for execution in result.executions]

    assert result.ok
    assert result.progress_control is not None
    assert result.progress_control.recovery_granularity == "whole-script"
    assert result.progress_control.patch_back is False
    assert runtime.script_names == [
        "01-system.sh",
        "02-python.sh",
        "whole-setup.sh",
        "whole-setup.sh",
    ]
    assert "03-final.sh" not in runtime.script_names
    assert "echo install-package" in whole_script
    assert "whole_script_recovery" in phases
    assert "repair" not in phases
    assert "fake:01-system-success" in runtime.commits
    assert "fake:whole-script-repaired" in runtime.commits
    assert "fake:03-final-success" not in runtime.commits
    assert {block.success_checkpoint for block in result.blocks} == {
        "fake:whole-script-repaired"
    }
    assert repair_llm.contexts
    assert repair_llm.contexts[0] is not None
    assert repair_llm.contexts[0].strategy_notes
    assert result.final_clean_replay_ok is True


def test_environment_builder_rejects_final_clean_replay_resume(
    tmp_path: Path,
) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=None,
        state_dir=tmp_path / ".pheragent",
        run_id="resume-full",
        resume_from="pheragent:previous",
        ablation_mode="full",
    )

    result = EnvironmentBuilder(
        request,
        planner=StaticPlanner([]),
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert not result.ok
    assert "resume-from" in (result.error or "")
    assert result.final_clean_replay_enabled is True
    assert result.final_clean_replay_ok is False
    assert result.final_clean_replay_failure_stage == "resume-from"
    assert manifest["final_clean_replay_failure_stage"] == "resume-from"
    assert FakeRuntime.instances == []


def test_environment_builder_without_local_repair_does_not_call_repair(
    tmp_path: Path,
) -> None:
    class FailingRuntime(FakeRuntime):
        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del script_path, timeout
            return CommandResult(exit_code=1, stderr="missing dependency")

    class UnexpectedRepairPlanner:
        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            raise AssertionError("local repair should be disabled")

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="no-local-repair",
        ablation_mode="without-local-repair",
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

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=UnexpectedRepairPlanner()),
        runtime_factory=FailingRuntime,
    ).build()

    assert not result.ok
    assert result.error == "block failed: 01-custom"
    assert not any(execution.phase == "repair" for execution in result.executions)
    assert not any(execution.phase == "llm_repair" for execution in result.executions)
    assert result.progress_control is not None
    assert result.progress_control.local_repair is False


def test_environment_builder_without_checkpoint_rollback_repairs_in_live_container(
    tmp_path: Path,
) -> None:
    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="no-rollback",
        ablation_mode="without-checkpoint-rollback",
        max_repair_attempts=1,
    )

    result = EnvironmentBuilder(
        request,
        repair_planner=RepairPlanner(llm_planner=BuildEssentialLLMRepairPlanner()),
        runtime_factory=FakeRuntime,
    ).build()

    runtime = FakeRuntime.instances[-1]

    assert result.ok
    assert "fake:00-preflight-success" not in runtime.recreated
    assert runtime.recreated == ["fake:None-workspace"]
    assert any(execution.phase == "repair" for execution in result.executions)
    assert any(execution.phase == "clean_replay" for execution in result.executions)
    assert result.progress_control is not None
    assert result.progress_control.checkpoint_rollback is False


def test_environment_builder_records_llm_usage_in_manifest(tmp_path: Path) -> None:
    class UsagePlanner:
        def plan(self, context: RepoContext) -> list[CommandBlock]:
            del context
            return [
                CommandBlock(
                    id="00-preflight",
                    title="Preflight",
                    goal="inspect",
                    script="#!/bin/sh\necho ok\n",
                    order=0,
                )
            ]

        def usage_summary(self) -> dict[str, dict[str, int]]:
            return {
                "planner": {
                    "requests": 1,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "reasoning_tokens": 2,
                    "total_tokens": 15,
                },
                "total": {
                    "requests": 1,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "reasoning_tokens": 2,
                    "total_tokens": 15,
                },
            }

    class UsageRepairPlanner(RepairPlanner):
        def usage_summary(self) -> dict[str, dict[str, int]]:
            return {
                "repair": {
                    "requests": 2,
                    "input_tokens": 20,
                    "output_tokens": 8,
                    "reasoning_tokens": 6,
                    "total_tokens": 28,
                },
                "total": {
                    "requests": 2,
                    "input_tokens": 20,
                    "output_tokens": 8,
                    "reasoning_tokens": 6,
                    "total_tokens": 28,
                },
            }

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="usage-run",
    )

    result = EnvironmentBuilder(
        request,
        planner=UsagePlanner(),
        repair_planner=UsageRepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.ok
    assert result.llm_usage_path == result.state_dir / "llm-usage.json"
    usage_file = json.loads(result.llm_usage_path.read_text(encoding="utf-8"))
    assert usage_file["total"]["total_tokens"] == 43
    assert usage_file["total"]["reasoning_tokens"] == 8
    assert manifest["llm_usage"]["planner"]["total_tokens"] == 15
    assert manifest["llm_usage"]["repair"]["total_tokens"] == 28
    assert manifest["llm_usage"]["total"] == {
        "requests": 3,
        "input_tokens": 30,
        "output_tokens": 13,
        "reasoning_tokens": 8,
        "total_tokens": 43,
    }


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


def test_environment_builder_stops_probing_after_empty_llm_probe_response(
    tmp_path: Path,
) -> None:
    class EmptyProbeRuntime(FakeRuntime):
        def __init__(self, request: BuildRequest, run_id: str):
            super().__init__(request, run_id)
            self.current_has_second_fix = False

        def recreate_from(self, image_ref: str) -> str:
            self.current_has_second_fix = False
            return super().recreate_from(image_ref)

        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            script = script_path.read_text(encoding="utf-8")
            if "first-fix" not in script:
                return CommandResult(exit_code=1, stderr="first missing")
            self.current_has_second_fix = "second-fix" in script
            return CommandResult(exit_code=0, stdout="block ok")

        def execute_command(self, command: str, *, timeout: float) -> CommandResult:
            del timeout
            if "container preflight" in command:
                return CommandResult(exit_code=0, stdout="tool:python3=/usr/bin/python3\n")
            if command == "validate":
                if self.current_has_second_fix:
                    return CommandResult(exit_code=0, stdout="validation ok")
                return CommandResult(exit_code=1, stderr="validation needs second fix")
            if command in {"first-repair", "second-repair"}:
                return CommandResult(exit_code=0, stdout="repaired")
            return CommandResult(exit_code=0, stdout="ok")

    class EmptyProbeLLMRepairPlanner:
        def __init__(self) -> None:
            self.probe_calls = 0
            self.repair_calls = 0
            self.last_probe_raw_response: str | None = None
            self.last_probe_parse_diagnostics: list[str] = []
            self.last_raw_response: str | None = None
            self.last_parse_diagnostics: list[str] = []

        def propose_probes(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.probe_calls += 1
            self.last_probe_raw_response = '{"probes":[]}'
            self.last_probe_parse_diagnostics = ["probes list is empty"]
            return []

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.repair_calls += 1
            if self.repair_calls == 1:
                self.last_raw_response = '{"repairs":[{"title":"First fix"}]}'
                return [
                    RepairCommand(
                        title="First fix",
                        command="first-repair",
                        patch_script="echo first-fix",
                    )
                ]
            self.last_raw_response = '{"repairs":[{"title":"Second fix"}]}'
            return [
                RepairCommand(
                    title="Second fix",
                    command="second-repair",
                    patch_script="echo second-fix",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="empty-probe",
        max_repair_attempts=2,
        max_probe_failures=5,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-python-deps",
                title="Python Dependencies",
                goal="install",
                script="#!/bin/sh\necho python-deps\n",
                validation_command="validate",
                order=1,
            )
        ]
    )
    llm_planner = EmptyProbeLLMRepairPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=llm_planner),
        runtime_factory=EmptyProbeRuntime,
    ).build()

    assert result.ok
    assert llm_planner.probe_calls == 1
    assert llm_planner.repair_calls == 2
    llm_probe_executions = [
        execution for execution in result.executions if execution.phase == "llm_probe"
    ]
    assert [execution.attempt for execution in llm_probe_executions] == [1]


def test_environment_builder_tests_later_repairs_after_existing_patches(
    tmp_path: Path,
) -> None:
    class LayeredRuntime(FakeRuntime):
        def __init__(self, request: BuildRequest, run_id: str):
            super().__init__(request, run_id)
            self.current_has_first_fix = False
            self.current_has_second_fix = False

        def recreate_from(self, image_ref: str) -> str:
            self.current_has_first_fix = False
            self.current_has_second_fix = False
            return super().recreate_from(image_ref)

        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            script = script_path.read_text(encoding="utf-8")
            if "first-fix" not in script:
                return CommandResult(exit_code=1, stderr="first missing")
            self.current_has_first_fix = True
            self.current_has_second_fix = "second-fix" in script
            return CommandResult(exit_code=0, stdout="block ok")

        def execute_command(self, command: str, *, timeout: float) -> CommandResult:
            del timeout
            if "container preflight" in command:
                return CommandResult(exit_code=0, stdout="tool:python3=/usr/bin/python3\n")
            if command == "validate":
                if self.current_has_second_fix:
                    return CommandResult(exit_code=0, stdout="validation ok")
                return CommandResult(exit_code=1, stderr="second missing")
            if command == "first-repair":
                return CommandResult(exit_code=0, stdout="first repaired")
            if command == "second-repair":
                if self.current_has_first_fix:
                    return CommandResult(exit_code=0, stdout="second repaired")
                return CommandResult(exit_code=1, stderr="first fix not applied")
            return CommandResult(exit_code=0, stdout="ok")

    class LayeredRepairPlanner:
        def __init__(self) -> None:
            self.calls = 0

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.calls += 1
            if self.calls == 1:
                return [
                    RepairCommand(
                        title="First fix",
                        command="first-repair",
                        patch_script="echo first-fix",
                    )
                ]
            return [
                RepairCommand(
                    title="Second fix",
                    command="second-repair",
                    patch_script="echo second-fix",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="layered-repair",
        max_repair_attempts=2,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-python-deps",
                title="Python Dependencies",
                goal="install",
                script="#!/bin/sh\necho python-deps\n",
                validation_command="validate",
                order=1,
            )
        ]
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=LayeredRepairPlanner()),
        runtime_factory=LayeredRuntime,
    ).build()

    assert result.ok
    assert any(execution.phase == "repair_prep" for execution in result.executions)
    script = (result.scripts_dir / "01-python-deps.sh").read_text(encoding="utf-8")
    assert "first-fix" in script
    assert "second-fix" in script


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
        task_description="Setup target: import demo and run the demo CLI.",
        ablation_mode="without-final-clean-replay",
    )

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    ).build()

    assert result.ok
    assert planner.calls == 1
    assert planner.contexts[0].task_description == (
        "Setup target: import demo and run the demo CLI."
    )
    assert "tool:python3=/usr/bin/python3" in planner.contexts[0].runtime_notes
    runtime = FakeRuntime.instances[-1]
    assert runtime.recreated == []
    assert any(execution.phase == "container_preflight" for execution in result.executions)
    assert "python.version=3.12.0" in (result.state_dir / "context.json").read_text(
        encoding="utf-8"
    )
    assert "Setup target: import demo" in (result.state_dir / "context.json").read_text(
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


def test_environment_builder_continues_repair_after_transient_llm_failure(
    tmp_path: Path,
) -> None:
    class UnknownFailureRuntime(FakeRuntime):
        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            script = script_path.read_text(encoding="utf-8")
            if "build-essential" not in script:
                return CommandResult(exit_code=1, stderr="mystery failure")
            return CommandResult(exit_code=0, stdout="ok")

    class FlakyLLMRepairPlanner:
        def __init__(self) -> None:
            self.calls = 0

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError(
                    "LLM repair request failed: HTTP 408: request timed out"
                )
            return [
                RepairCommand(
                    title="Install build tools",
                    command="apt-get update && apt-get install -y build-essential",
                    patch_script="apt-get update && apt-get install -y build-essential",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="llm-repair-transient",
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
    llm_planner = FlakyLLMRepairPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=llm_planner),
        runtime_factory=UnknownFailureRuntime,
    ).build()

    assert result.ok
    assert llm_planner.calls == 3
    llm_executions = [
        execution for execution in result.executions if execution.phase == "llm_repair"
    ]
    assert [execution.attempt for execution in llm_executions] == [1, 2]
    assert "HTTP 408" in Path(llm_executions[0].log_path or "").read_text(
        encoding="utf-8"
    )
    assert any(execution.phase == "repair" for execution in result.executions)


def test_environment_builder_continues_repair_after_probe_failure_budget(
    tmp_path: Path,
) -> None:
    class UnknownFailureRuntime(FakeRuntime):
        def execute_script(self, script_path: Path, *, timeout: float) -> CommandResult:
            del timeout
            self.block_runs += 1
            script = script_path.read_text(encoding="utf-8")
            if "build-essential" not in script:
                return CommandResult(exit_code=1, stderr="mystery failure")
            return CommandResult(exit_code=0, stdout="ok")

    class FailingProbeLLMRepairPlanner:
        def __init__(self) -> None:
            self.probe_calls = 0
            self.repair_calls = 0

        def propose_probes(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.probe_calls += 1
            raise RuntimeError("HTTP 429: rate limit")

        def suggest(self, block, result, *, context=None, heuristic_hints=None):
            del block, result, context, heuristic_hints
            self.repair_calls += 1
            return [
                RepairCommand(
                    title="Install build tools",
                    command="apt-get update && apt-get install -y build-essential",
                    patch_script="apt-get update && apt-get install -y build-essential",
                )
            ]

    FakeRuntime.instances = []
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="probe-failure",
        max_repair_attempts=3,
        max_probe_failures=2,
    )
    planner = StaticPlanner(
        [
            CommandBlock(
                id="01-custom",
                title="Custom",
                goal="install",
                script="#!/bin/sh\necho python-deps\n",
                order=1,
            )
        ]
    )
    llm_planner = FailingProbeLLMRepairPlanner()

    result = EnvironmentBuilder(
        request,
        planner=planner,
        repair_planner=RepairPlanner(llm_planner=llm_planner),
        runtime_factory=UnknownFailureRuntime,
    ).build()

    assert result.ok
    assert llm_planner.probe_calls == 2
    assert llm_planner.repair_calls == 1
    llm_probe_executions = [
        execution for execution in result.executions if execution.phase == "llm_probe"
    ]
    assert [execution.attempt for execution in llm_probe_executions] == [1, 2]
    assert "HTTP 429" in Path(llm_probe_executions[-1].log_path or "").read_text(
        encoding="utf-8"
    )


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
        ablation_mode="without-final-clean-replay",
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


def test_environment_builder_infers_resume_block_from_hashed_checkpoint_tag(
    tmp_path: Path,
) -> None:
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
    request = BuildRequest(
        repo_path=tmp_path,
        base_dockerfile=tmp_path / "Dockerfile",
        state_dir=tmp_path / ".pheragent",
        run_id="resume-run",
    )
    builder = EnvironmentBuilder(
        request,
        planner=FailingPlanner(),
        repair_planner=RepairPlanner(),
        runtime_factory=FakeRuntime,
    )

    image_ref = "pheragent:resume-run-a1b2c3d4e5f6-002-01-tooling-success"

    assert builder._infer_resume_block_id(blocks, image_ref) == "01-tooling"
    assert builder._resume_start_index(blocks, image_ref) == 2


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
        ablation_mode="without-final-clean-replay",
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
