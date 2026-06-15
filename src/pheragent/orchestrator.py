from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from .analyzer import RepoAnalyzer
from .block_store import BlockStore
from .docker_runtime import DockerRuntime
from .llm_planner import make_planner
from .models import (
    BlockExecution,
    BuildRequest,
    BuildResult,
    Checkpoint,
    CommandBlock,
    CommandResult,
    RepairContext,
    RepairProbeResult,
    RepoContext,
)
from .oracle import load_oracle_commands
from .planner import BlockPlanner
from .repair import RepairPlanner, RepairProbeCommand, make_repair_planner
from .utils import new_run_id, tail_text

RuntimeFactory = Callable[[BuildRequest, str], DockerRuntime]


class EnvironmentBuilder:
    def __init__(
        self,
        request: BuildRequest,
        *,
        analyzer: RepoAnalyzer | None = None,
        planner: BlockPlanner | None = None,
        repair_planner: RepairPlanner | None = None,
        runtime_factory: RuntimeFactory = DockerRuntime,
    ):
        self.request = request.normalized()
        self.run_id = self.request.run_id or new_run_id()
        self.run_dir = (self.request.state_dir or Path(".pheragent")) / "runs" / self.run_id
        self.store = BlockStore(self.run_dir)
        self.analyzer = analyzer or RepoAnalyzer()
        self.planner = planner or make_planner(
            mode=self.request.planner_mode,
            model=self.request.llm_model,
            api_key_env=self.request.openai_api_key_env,
            base_url_env=self.request.openai_base_url_env,
            base_url=self.request.openai_base_url,
            timeout=self.request.llm_timeout,
            max_tokens=self.request.llm_max_tokens,
            retries=self.request.llm_retries,
            retry_delay=self.request.llm_retry_delay,
        )
        self.repair_planner = repair_planner or make_repair_planner(
            mode=self.request.planner_mode,
            model=self.request.llm_model,
            api_key_env=self.request.openai_api_key_env,
            base_url_env=self.request.openai_base_url_env,
            base_url=self.request.openai_base_url,
            timeout=self.request.llm_timeout,
            max_tokens=self.request.llm_max_tokens,
            retries=self.request.llm_retries,
            retry_delay=self.request.llm_retry_delay,
        )
        self.runtime_factory = runtime_factory

    def plan_only(self) -> BuildResult:
        self._emit(f"run {self.run_id}: analyze repo {self.request.repo_path}")
        context = self.analyzer.analyze(self.request.repo_path)
        self.store.save_context(context)
        self._emit(f"run {self.run_id}: plan blocks")
        blocks = self.store.write_blocks(self.planner.plan(context))
        result = BuildResult(
            ok=True,
            run_id=self.run_id,
            state_dir=self.run_dir,
            scripts_dir=self.store.scripts_dir,
            manifest_path=self.store.manifest_path,
            blocks=blocks,
        )
        self.store.save_manifest(result)
        return result

    def build(self) -> BuildResult:
        self._emit(f"run {self.run_id}: analyze repo {self.request.repo_path}")
        context = self.analyzer.analyze(self.request.repo_path)
        self.store.save_context(context)
        runtime = self.runtime_factory(self.request, self.run_id)
        checkpoints: list[Checkpoint] = []
        executions: list[BlockExecution] = []
        blocks: list[CommandBlock] = []
        current_image: str | None = None
        result = BuildResult(
            ok=False,
            run_id=self.run_id,
            state_dir=self.run_dir,
            scripts_dir=self.store.scripts_dir,
            manifest_path=self.store.manifest_path,
            blocks=blocks,
            checkpoints=checkpoints,
            executions=executions,
        )

        try:
            start_index = 0
            if self.request.resume_from:
                current_image = self.request.resume_from
                self._emit(f"run {self.run_id}: resume from {current_image}")
                runtime.start(image_ref=current_image, seed_repo=False)
                self._collect_container_context(
                    runtime=runtime,
                    context=context,
                    executions=executions,
                    checkpoint_before=current_image,
                )
                blocks = self._load_or_plan_blocks(context)
                result.blocks = blocks
                checkpoints.append(
                    Checkpoint(
                        id="resume-from",
                        image_ref=current_image,
                        block_id=self._infer_resume_block_id(blocks, current_image),
                        parent_image_ref=None,
                        kind="resume",
                    )
                )
                start_index = self._resume_start_index(blocks, current_image)
                self._mark_resume_skipped_blocks(blocks, start_index, current_image)
            else:
                self._emit(f"run {self.run_id}: build base image")
                build_result = runtime.build_base_image()
                executions.append(
                    self._execution_from_result(
                        block_id="base-image",
                        phase="docker_build",
                        attempt=1,
                        command_result=build_result,
                        checkpoint_before=None,
                    )
                )
                self.store.append_execution(executions[-1])
                if not build_result.ok:
                    self._emit(f"run {self.run_id}: base image build failed")
                    result.error = "base Docker image build failed"
                    self.store.save_manifest(result)
                    return result

                self._emit(f"run {self.run_id}: start container and copy repo")
                runtime.start(seed_repo=True)
                self._collect_container_context(
                    runtime=runtime,
                    context=context,
                    executions=executions,
                    checkpoint_before=runtime.base_image,
                )
                blocks = self._load_or_plan_blocks(context)
                result.blocks = blocks
                workspace_checkpoint = runtime.commit(
                    block_id=None,
                    parent_image_ref=runtime.base_image,
                    kind="workspace",
                )
                checkpoints.append(workspace_checkpoint)
                current_image = workspace_checkpoint.image_ref

            for block_index, block in enumerate(blocks[start_index:], start=start_index):
                self._emit(f"run {self.run_id}: block {block.id} start")
                block.baseline_checkpoint = current_image
                self.store.update_block(block)
                block_ok, current_image = self._run_block_with_repair(
                    runtime=runtime,
                    block=block,
                    baseline_image=current_image,
                    repo_context=context,
                    completed_blocks=blocks[:block_index],
                    checkpoints=checkpoints,
                    executions=executions,
                )
                if not block_ok:
                    self._emit(f"run {self.run_id}: block {block.id} failed")
                    result.error = f"block failed: {block.id}"
                    result.final_image = current_image
                    self.store.save_manifest(result)
                    return result

            if self.request.oracle_file is not None:
                self._emit(f"run {self.run_id}: oracle validation")
                oracle_ok = self._run_oracle_validation(
                    runtime=runtime,
                    checkpoint_image=current_image,
                    executions=executions,
                )
                if not oracle_ok:
                    self._emit(f"run {self.run_id}: oracle validation failed")
                    result.error = "oracle validation failed"
                    result.final_image = current_image
                    self.store.save_manifest(result)
                    return result

            result.ok = True
            result.final_image = current_image
            self.store.save_manifest(result)
            self._emit(f"run {self.run_id}: ok")
            return result
        except Exception as exc:
            self._emit(f"run {self.run_id}: failed: {exc}")
            result.error = str(exc)
            result.final_image = current_image
            self.store.save_manifest(result)
            return result
        finally:
            runtime.cleanup()

    def _load_or_plan_blocks(self, context: RepoContext) -> list[CommandBlock]:
        if self.request.resume_from:
            existing_blocks = self.store.list_blocks()
            if existing_blocks:
                self._emit(f"run {self.run_id}: reuse existing block scripts")
                return self.store.write_blocks(existing_blocks)
        self._emit(f"run {self.run_id}: plan blocks")
        return self.store.write_blocks(self.planner.plan(context))

    def _collect_container_context(
        self,
        *,
        runtime: DockerRuntime,
        context: RepoContext,
        executions: list[BlockExecution],
        checkpoint_before: str | None,
    ) -> None:
        self._emit(f"run {self.run_id}: collect container context")
        result = runtime.execute_command(
            _CONTAINER_PREFLIGHT_COMMAND,
            timeout=min(self.request.command_timeout, 120.0),
        )
        execution = self._execution_from_result(
            block_id="container-preflight",
            phase="container_preflight",
            attempt=1,
            command_result=result,
            checkpoint_before=checkpoint_before,
        )
        executions.append(execution)
        self.store.append_execution(execution)
        context.runtime_notes = _runtime_notes_from_preflight(result)
        self.store.save_context(context)

    def _resume_start_index(self, blocks: list[CommandBlock], image_ref: str) -> int:
        if self.request.start_at_block:
            for index, block in enumerate(blocks):
                if block.id == self.request.start_at_block:
                    return index
            raise ValueError(f"start block not found: {self.request.start_at_block}")

        completed_index = self._infer_completed_block_index(blocks, image_ref)
        if completed_index is None:
            return 0
        return completed_index + 1

    def _mark_resume_skipped_blocks(
        self,
        blocks: list[CommandBlock],
        start_index: int,
        resume_image: str,
    ) -> None:
        for block in blocks[:start_index]:
            block.status = "skipped"
            block.success_checkpoint = block.success_checkpoint or resume_image
            self.store.update_block(block)

    def _infer_resume_block_id(self, blocks: list[CommandBlock], image_ref: str) -> str | None:
        completed_index = self._infer_completed_block_index(blocks, image_ref)
        if completed_index is None:
            return None
        return blocks[completed_index].id

    def _infer_completed_block_index(
        self,
        blocks: list[CommandBlock],
        image_ref: str,
    ) -> int | None:
        image_tag = image_ref.rsplit(":", 1)[-1]
        for index in range(len(blocks) - 1, -1, -1):
            block = blocks[index]
            if image_tag.endswith(f"-{block.id}-success") or image_tag.endswith(
                f"-{block.id}-repaired"
            ):
                return index
        return None

    def _run_block_with_repair(
        self,
        *,
        runtime: DockerRuntime,
        block: CommandBlock,
        baseline_image: str,
        repo_context: RepoContext,
        completed_blocks: list[CommandBlock],
        checkpoints: list[Checkpoint],
        executions: list[BlockExecution],
    ) -> tuple[bool, str]:
        attempt = 1
        last_result = self._execute_block(runtime, block, attempt, baseline_image, executions)
        validation_result = self._validate_block(
            runtime,
            block,
            attempt,
            baseline_image,
            executions,
        )
        if last_result.ok and (validation_result is None or validation_result.ok):
            finalize_result = self._finalize_checkpoint_tools(
                runtime=runtime,
                block=block,
                attempt=attempt,
                baseline_image=baseline_image,
                executions=executions,
            )
            if not finalize_result.ok:
                block.status = "failed"
                block.last_error = tail_text(finalize_result.combined_output, max_chars=4000)
                self.store.update_block(block)
                runtime.recreate_from(baseline_image)
                return False, baseline_image
            checkpoint = runtime.commit(
                block_id=block.id,
                parent_image_ref=baseline_image,
                kind="success",
            )
            checkpoints.append(checkpoint)
            block.success_checkpoint = checkpoint.image_ref
            block.status = "succeeded"
            self.store.update_block(block)
            self._emit(f"run {self.run_id}: block {block.id} checkpoint {checkpoint.image_ref}")
            return True, checkpoint.image_ref
        if last_result.ok and validation_result is not None:
            last_result = validation_result

        for repair_attempt in range(1, self.request.max_repair_attempts + 1):
            repair_context = self._repair_context(
                repo_context=repo_context,
                baseline_image=baseline_image,
                completed_blocks=completed_blocks,
                executions=executions,
            )
            probes = self.repair_planner.propose_probes(
                block,
                last_result,
                context=repair_context,
            )
            self._record_llm_probe_status(
                block=block,
                attempt=repair_attempt,
                baseline_image=baseline_image,
                executions=executions,
            )
            probe_results = self._run_repair_probes(
                runtime=runtime,
                block=block,
                baseline_image=baseline_image,
                attempt=repair_attempt,
                probes=probes,
                executions=executions,
            )
            if probe_results:
                repair_context = self._repair_context(
                    repo_context=repo_context,
                    baseline_image=baseline_image,
                    completed_blocks=completed_blocks,
                    executions=executions,
                    probe_results=probe_results,
                )
            suggestions = self.repair_planner.suggest(
                block,
                last_result,
                context=repair_context,
            )
            self._record_llm_repair_status(
                block=block,
                attempt=repair_attempt,
                baseline_image=baseline_image,
                executions=executions,
                ok=bool(suggestions),
            )
            if not suggestions:
                error = getattr(self.repair_planner, "last_llm_error", None)
                if error:
                    self._emit(
                        f"run {self.run_id}: block {block.id} LLM repair attempt "
                        f"{repair_attempt} failed: {tail_text(error, max_chars=500)}"
                    )
                if error == "LLM repair returned no usable suggestions":
                    continue
                break
            repair = suggestions[min(repair_attempt - 1, len(suggestions) - 1)]
            self._emit(f"run {self.run_id}: block {block.id} repair attempt {repair_attempt}")
            runtime.recreate_from(baseline_image)
            repair_result = runtime.execute_command(
                repair.command,
                timeout=self.request.command_timeout,
            )
            execution = self._execution_from_result(
                block_id=block.id,
                phase="repair",
                attempt=repair_attempt,
                command_result=repair_result,
                checkpoint_before=baseline_image,
                repair_command=repair.command,
            )
            executions.append(execution)
            self.store.append_execution(execution)
            if not repair_result.ok:
                last_result = repair_result
                continue

            block = self.repair_planner.patch_block(block, repair)
            self.store.update_block(block)
            runtime.recreate_from(baseline_image)
            attempt += 1
            last_result = self._execute_block(runtime, block, attempt, baseline_image, executions)
            validation_result = self._validate_block(
                runtime, block, attempt, baseline_image, executions
            )
            if last_result.ok and (validation_result is None or validation_result.ok):
                finalize_result = self._finalize_checkpoint_tools(
                    runtime=runtime,
                    block=block,
                    attempt=attempt,
                    baseline_image=baseline_image,
                    executions=executions,
                )
                if not finalize_result.ok:
                    block.status = "failed"
                    block.last_error = tail_text(finalize_result.combined_output, max_chars=4000)
                    self.store.update_block(block)
                    runtime.recreate_from(baseline_image)
                    return False, baseline_image
                checkpoint = runtime.commit(
                    block_id=block.id,
                    parent_image_ref=baseline_image,
                    kind="repaired",
                )
                checkpoints.append(checkpoint)
                block.success_checkpoint = checkpoint.image_ref
                block.status = "succeeded"
                self.store.update_block(block)
                self._emit(
                    f"run {self.run_id}: block {block.id} repaired checkpoint "
                    f"{checkpoint.image_ref}"
                )
                return True, checkpoint.image_ref
            if last_result.ok and validation_result is not None:
                last_result = validation_result

        block.status = "failed"
        block.last_error = tail_text(last_result.combined_output, max_chars=4000)
        self.store.update_block(block)
        runtime.recreate_from(baseline_image)
        return False, baseline_image

    def _repair_context(
        self,
        *,
        repo_context: RepoContext,
        baseline_image: str,
        completed_blocks: list[CommandBlock],
        executions: list[BlockExecution],
        probe_results: list[RepairProbeResult] | None = None,
    ) -> RepairContext:
        return RepairContext(
            repo_context=repo_context,
            checkpoint_before=baseline_image,
            previous_blocks=[
                block
                for block in completed_blocks
                if block.status in {"succeeded", "repaired", "skipped"}
            ],
            recent_executions=executions[-8:],
            probe_results=probe_results or [],
        )

    def _run_repair_probes(
        self,
        *,
        runtime: DockerRuntime,
        block: CommandBlock,
        baseline_image: str,
        attempt: int,
        probes: list[RepairProbeCommand],
        executions: list[BlockExecution],
    ) -> list[RepairProbeResult]:
        if not probes:
            return []
        self._emit(
            f"run {self.run_id}: block {block.id} probe attempt {attempt} "
            f"({len(probes)} commands)"
        )
        runtime.recreate_from(baseline_image)
        probe_results: list[RepairProbeResult] = []
        timeout = min(self.request.command_timeout, 60.0)
        for index, probe in enumerate(probes, start=1):
            self._emit(f"run {self.run_id}: block {block.id} probe {index}/{len(probes)}")
            command_result = runtime.execute_command(probe.command, timeout=timeout)
            execution = self._execution_from_result(
                block_id=block.id,
                phase="probe",
                attempt=attempt,
                command_result=command_result,
                checkpoint_before=baseline_image,
                repair_command=probe.command,
            )
            executions.append(execution)
            self.store.append_execution(execution)
            probe_results.append(
                RepairProbeResult(
                    title=probe.title,
                    command=probe.command,
                    exit_code=command_result.exit_code,
                    timed_out=command_result.timed_out,
                    stdout_tail=tail_text(command_result.stdout, max_chars=4000),
                    stderr_tail=tail_text(command_result.stderr, max_chars=4000),
                    duration_s=command_result.duration_s,
                )
            )
        runtime.recreate_from(baseline_image)
        return probe_results

    def _execute_block(
        self,
        runtime: DockerRuntime,
        block: CommandBlock,
        attempt: int,
        baseline_image: str,
        executions: list[BlockExecution],
    ) -> CommandResult:
        block.status = "running"
        self.store.update_block(block)
        self._emit(f"run {self.run_id}: block {block.id} execute attempt {attempt}")
        result = runtime.execute_script(
            self.store.script_path(block.id),
            timeout=self.request.command_timeout,
        )
        execution = self._execution_from_result(
            block_id=block.id,
            phase="block",
            attempt=attempt,
            command_result=result,
            checkpoint_before=baseline_image,
        )
        executions.append(execution)
        self.store.append_execution(execution)
        return result

    def _finalize_checkpoint_tools(
        self,
        *,
        runtime: DockerRuntime,
        block: CommandBlock,
        attempt: int,
        baseline_image: str,
        executions: list[BlockExecution],
    ) -> CommandResult:
        self._emit(f"run {self.run_id}: block {block.id} finalize")
        result = runtime.execute_command(
            _CHECKPOINT_TOOL_EXPORT_COMMAND,
            timeout=min(self.request.command_timeout, 120.0),
        )
        execution = self._execution_from_result(
            block_id=block.id,
            phase="finalize",
            attempt=attempt,
            command_result=result,
            checkpoint_before=baseline_image,
        )
        executions.append(execution)
        self.store.append_execution(execution)
        return result

    def _validate_block(
        self,
        runtime: DockerRuntime,
        block: CommandBlock,
        attempt: int,
        baseline_image: str,
        executions: list[BlockExecution],
    ) -> CommandResult | None:
        if not block.validation_command:
            return None
        self._emit(f"run {self.run_id}: block {block.id} validate")
        result = runtime.execute_command(
            block.validation_command,
            timeout=self.request.command_timeout,
        )
        execution = self._execution_from_result(
            block_id=block.id,
            phase="validation",
            attempt=attempt,
            command_result=result,
            checkpoint_before=baseline_image,
        )
        executions.append(execution)
        self.store.append_execution(execution)
        return result

    def _run_oracle_validation(
        self,
        *,
        runtime: DockerRuntime,
        checkpoint_image: str,
        executions: list[BlockExecution],
    ) -> bool:
        if self.request.oracle_file is None:
            return True
        commands = load_oracle_commands(self.request.oracle_file)
        if not commands:
            raise ValueError(
                f"oracle file did not contain test commands: {self.request.oracle_file}"
            )
        timeout = self.request.oracle_timeout or self.request.command_timeout
        for index, command in enumerate(commands, start=1):
            self._emit(f"run {self.run_id}: oracle command {index}/{len(commands)}")
            result = runtime.execute_command(command, timeout=timeout)
            execution = self._execution_from_result(
                block_id="oracle",
                phase="oracle",
                attempt=index,
                command_result=result,
                checkpoint_before=checkpoint_image,
            )
            executions.append(execution)
            self.store.append_execution(execution)
            if not result.ok:
                return False
        return True

    def _record_llm_repair_status(
        self,
        *,
        block: CommandBlock,
        attempt: int,
        baseline_image: str,
        executions: list[BlockExecution],
        ok: bool = False,
    ) -> None:
        error = getattr(self.repair_planner, "last_llm_error", None)
        raw_response = getattr(self.repair_planner, "last_llm_raw_response", None)
        diagnostics = getattr(self.repair_planner, "last_llm_parse_diagnostics", [])
        stdout = _llm_repair_debug_output(raw_response, diagnostics)
        if not error and not stdout:
            return
        result = CommandResult(
            exit_code=0 if ok and not error else 1,
            stdout=stdout,
            stderr=error or "",
            command=["llm-repair", block.id],
        )
        execution = self._execution_from_result(
            block_id=block.id,
            phase="llm_repair",
            attempt=attempt,
            command_result=result,
            checkpoint_before=baseline_image,
        )
        executions.append(execution)
        self.store.append_execution(execution)

    def _record_llm_probe_status(
        self,
        *,
        block: CommandBlock,
        attempt: int,
        baseline_image: str,
        executions: list[BlockExecution],
    ) -> None:
        error = getattr(self.repair_planner, "last_probe_error", None)
        raw_response = getattr(self.repair_planner, "last_probe_raw_response", None)
        diagnostics = getattr(self.repair_planner, "last_probe_parse_diagnostics", [])
        stdout = _llm_repair_debug_output(raw_response, diagnostics)
        if not error and not stdout:
            return
        result = CommandResult(
            exit_code=0 if not error else 1,
            stdout=stdout,
            stderr=error or "",
            command=["llm-probe", block.id],
        )
        execution = self._execution_from_result(
            block_id=block.id,
            phase="llm_probe",
            attempt=attempt,
            command_result=result,
            checkpoint_before=baseline_image,
        )
        executions.append(execution)
        self.store.append_execution(execution)

    def _execution_from_result(
        self,
        *,
        block_id: str,
        phase: str,
        attempt: int,
        command_result: CommandResult,
        checkpoint_before: str | None,
        checkpoint_after: str | None = None,
        repair_command: str | None = None,
    ) -> BlockExecution:
        log_path = self.store.write_execution_log(
            block_id=block_id,
            phase=phase,
            attempt=attempt,
            command_result=command_result,
            checkpoint_before=checkpoint_before,
            checkpoint_after=checkpoint_after,
            repair_command=repair_command,
        )
        return BlockExecution(
            block_id=block_id,
            phase=phase,
            attempt=attempt,
            exit_code=command_result.exit_code,
            timed_out=command_result.timed_out,
            stdout_tail=tail_text(command_result.stdout),
            stderr_tail=tail_text(command_result.stderr),
            checkpoint_before=checkpoint_before,
            checkpoint_after=checkpoint_after,
            repair_command=repair_command,
            duration_s=command_result.duration_s,
            command=command_result.command,
            log_path=str(log_path),
        )

    def _emit(self, message: str) -> None:
        if self.request.stream_logs:
            print(f"[pheragent] {message}", file=sys.stderr, flush=True)


def _llm_repair_debug_output(raw_response: object, diagnostics: object) -> str:
    parts: list[str] = []
    if isinstance(raw_response, str):
        parts.append("--- raw_llm_response ---\n" + raw_response)
    if diagnostics:
        if isinstance(diagnostics, str):
            diagnostic_lines = [diagnostics]
        else:
            try:
                diagnostic_lines = [str(item) for item in diagnostics]
            except TypeError:
                diagnostic_lines = [str(diagnostics)]
        parts.append("--- parse_diagnostics ---\n" + "\n".join(diagnostic_lines))
    return "\n\n".join(parts)


_CONTAINER_PREFLIGHT_COMMAND = r"""
echo "[pheragent] container preflight"
printf 'workdir=%s\n' "$(pwd -P)" || true
printf 'user=%s uid=%s gid=%s\n' \
  "$(id -un 2>/dev/null || true)" \
  "$(id -u 2>/dev/null || true)" \
  "$(id -g 2>/dev/null || true)" || true
uname -a || true
cat /etc/os-release 2>/dev/null || true

for cmd in \
  sh bash python python3 pip pip3 uv gcc g++ make cmake ninja bazel node npm \
  java go rustc cargo nvidia-smi nvcc apt-get yum apk
do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf 'tool:%s=%s\n' "$cmd" "$(command -v "$cmd")"
    "$cmd" --version 2>&1 | sed -n '1,2p' || true
  else
    printf 'tool:%s=missing\n' "$cmd"
  fi
done

if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3 2>/dev/null || command -v python)"
  "$PYTHON_BIN" - <<'PY' || true
import os
import platform
import sys
print(f"python.executable={sys.executable}")
print(f"python.version={sys.version}")
print(f"python.platform={platform.platform()}")
print(f"python.prefix={sys.prefix}")
print(f"python.base_prefix={getattr(sys, 'base_prefix', '')}")
print(f"env.PATH={os.environ.get('PATH', '')}")
PY
fi

printf '[pheragent] repo markers\n'
find . -maxdepth 2 -type f \
  \( -name 'pyproject.toml' \
     -o -name 'setup.py' \
     -o -name 'setup.cfg' \
     -o -name 'requirements*.txt' \
     -o -name 'uv.lock' \
     -o -name 'WORKSPACE' \
     -o -name 'WORKSPACE.bazel' \
     -o -name 'MODULE.bazel' \
     -o -name '.bazelrc' \
     -o -name 'package.json' \
     -o -name 'go.mod' \
     -o -name 'Cargo.toml' \) \
  | sort | sed -n '1,120p' || true

exit 0
""".strip()


def _runtime_notes_from_preflight(result: CommandResult) -> list[str]:
    notes: list[str] = []
    if result.timed_out:
        notes.append("container preflight timed out")
    if not result.ok:
        notes.append(f"container preflight exit_code={result.exit_code}")
    output = tail_text(result.combined_output, max_chars=12000)
    for line in output.splitlines():
        clean = line.strip()
        if not clean:
            continue
        notes.append(clean[:300])
        if len(notes) >= 160:
            notes.append("container preflight output truncated")
            break
    return notes


_CHECKPOINT_TOOL_EXPORT_COMMAND = """
repo_dir="$(pwd -P)"
if ! command -v uv >/dev/null 2>&1; then
  for rel in \
    .pheragent/uv-bootstrap/bin/uv \
    .pheragent-tools/bin/uv \
    .venv/bin/uv
  do
    candidate="$repo_dir/$rel"
    if [ -x "$candidate" ]; then
      if [ -w /usr/local/bin ] || [ "$(id -u)" = "0" ]; then
        ln -sf "$candidate" /usr/local/bin/uv
        echo "[pheragent] exported uv to /usr/local/bin/uv"
        exit 0
      fi
      echo "[pheragent] uv found at $candidate but /usr/local/bin is not writable" >&2
      exit 1
    fi
  done
fi
exit 0
""".strip()
