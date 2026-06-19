# Ablation Development Plan

Date: 2026-06-19

Scope: progress-control ablations for `pheragent build` and
`pheragent build-projects`.

This document tracks the implementation plan for the HerAgent ablation variants.
The goal is to keep all variants inside the normal `pheragent` entry points so
they share the same repository input format, Docker runtime, logs, token usage,
batch accounting, and manifest schema.

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| Development plan | Done | This document records the ablation design and task state. |
| Ablation CLI plumbing | Done locally | `build` and `build-projects` accept `--ablation`. |
| Progress-control config | Done locally | `BuildRequest` and `BuildResult` carry `ablation_mode`; manifests include `progress_control`. |
| Batch result isolation | Done locally | Existing successful runs are reused only when the manifest ablation mode matches the requested mode. |
| Full HerAgent clean replay | Done locally | `--ablation full` replays final block scripts from the workspace checkpoint and commits a clean replay image. |
| Component removal: w/o local repair | Done locally | Disables local repair and patch-back after a failed block. |
| Component removal: w/o checkpoint rollback | Done locally | Keeps local repair and patch-back, but does not restore the block checkpoint during repair. |
| Component removal: w/o final clean replay | Done locally | Preserves the current default behavior and disables final clean replay. |
| Single-command forward | Done locally | Forward execution splits block scripts into command-level steps while preserving block recovery. |
| Single-command recovery | Done locally | Forward remains block-level, but failure recovery is local command-level rather than block rollback. |
| Whole-script forward | Done locally | Combine planned blocks into one whole setup artifact and execute it as one forward unit. |
| Whole-script recovery | Done locally | Keep block forward, but on failure repair/rewrite the whole setup artifact instead of the failed block. |
| Experiment output fields | Done locally | Manifest and batch usage JSONL record ablation mode, progress-control settings, and final replay fields. |
| Resume guard | Done locally | `--resume-from` is rejected for modes that require final clean replay. |
| Verification | Done locally | `uv run pytest -q` passes with 134 tests; `uv run ruff check .` passes. |

## Ablation Modes

The implemented and planned user-facing modes are:

```text
full
without-local-repair
without-checkpoint-rollback
without-final-clean-replay
single-command-forward
single-command-recovery
whole-script-forward
whole-script-recovery
```

The current default remains:

```text
without-final-clean-replay
```

This keeps existing experiments compatible. The paper-style full progress-control
setting should be requested explicitly with:

```sh
--ablation full
```

## Control Dimensions

| Dimension | Full HerAgent | Purpose |
| --- | --- | --- |
| Block forward | Enabled | Execute setup as functional blocks rather than isolated commands or one script. |
| Block recovery | Enabled | Repair failures at the failed block boundary. |
| Local repair | Enabled | Ask the repair planner for bounded local fixes for the failed block. |
| Patch-back | Enabled | Persist successful repair snippets into the failed block script. |
| Checkpoint rollback | Enabled | Restore the block baseline checkpoint before repair/replay. |
| Final clean replay | Enabled | Rebuild final state by replaying final artifacts from a clean workspace checkpoint. |

## Phase 1: Component Removal Ablations

Status: implemented locally.

Implemented modes:

- `full`
- `without-local-repair`
- `without-checkpoint-rollback`
- `without-final-clean-replay`

Implementation notes:

- `ProgressControl` maps each mode to concrete feature switches.
- `full` enables final clean replay.
- `without-local-repair` disables repair planner calls and patch-back.
- `without-checkpoint-rollback` keeps repair but does not call checkpoint restore
  during repair/probe/replay attempts.
- `without-final-clean-replay` matches the previous runtime behavior and remains
  the default.
- `build-projects` checks manifest ablation mode before skipping an existing
  successful run.

Verification:

```sh
uv run pytest -q
uv run ruff check .
```

## Phase 2: Single-command Ablations

Status: implemented locally.

### `single-command-forward`

Goal: ablate only forward granularity.

Status: implemented locally.

Expected behavior:

- Keep block planning, block recovery, local repair, patch-back, checkpoint
  rollback, and final clean replay.
- During normal forward execution, split each block script into command-level
  steps and execute them one by one.
- Preserve the block as the recovery/checkpoint unit.

Main implementation tasks:

1. Done locally: added a conservative script splitter that preserves common
   structured shell chunks such as continuations, heredocs, `if`/`for`/`case`
   bodies, and function bodies.
2. Done locally: normal forward execution records per-command executions with
   phase `command_forward`.
3. Done locally: block-level validation, repair, patch-back, checkpoint
   rollback, and final clean replay are unchanged after all commands in a block
   pass.
4. Done locally: command execution logs record the actual shell command used.
   Shell context commands such as `cd`, `export`, `source`, and pure
   assignments are replayed before later commands so command-level execution
   does not lose basic script state.

### `single-command-recovery`

Goal: ablate recovery granularity while preserving block forward.

Status: implemented locally.

Expected behavior:

- Execute blocks normally.
- On failure, do not use block checkpoint rollback or block patch-back.
- Attempt local recovery around the last failed command/current live container.
- This mode is expected to expose cases where earlier block pollution is not
  recoverable from the last command alone.

Main implementation tasks:

1. Done locally: added a command-level recovery path in the orchestrator.
2. Done locally: repair context includes strategy notes explaining that recovery
   happens in the current live container without checkpoint rollback, block
   replay, or patch-back.
3. Done locally: block scripts are not patched in this mode.
4. Done locally: recovery attempts are recorded with phase `command_recovery`
   instead of the normal `repair` phase.

## Phase 3: Whole-script Ablations

Status: implemented locally.

### `whole-script-forward`

Goal: ablate block-level forward.

Status: implemented locally.

Expected behavior:

- Generate or combine one whole setup artifact.
- Execute the whole artifact as one unit.
- Do not create block checkpoints or block rollback points.
- Final clean replay can still run by replaying the whole setup artifact from a
  clean workspace checkpoint.

Main implementation tasks:

1. Done locally: added a `whole-setup.sh` artifact writer under the run
   scripts directory.
2. Done locally: deterministic block concatenation is used for a controlled
   variant while keeping the existing planner unchanged.
3. Done locally: forward execution runs the whole artifact once, then runs block
   validations and commits a single `whole-script` checkpoint.
4. Done locally: logs distinguish `whole_script` execution from normal block
   execution, and final clean replay replays the whole artifact.

### `whole-script-recovery`

Goal: ablate block-level recovery.

Status: implemented locally.

Expected behavior:

- Forward may still progress with blocks.
- If a block fails, do not repair only that block.
- Rewrite or regenerate the whole setup artifact and replay it.
- This tests whether whole-artifact recovery discards already validated progress
  and causes repeated work.

Main implementation tasks:

1. Done locally: reuse the existing repair planner response as a whole-artifact
   patch while passing strategy notes that tell the LLM this is whole-script
   recovery.
2. Done locally: convert all planned block scripts plus the repair patch into
   `whole-setup.sh`.
3. Done locally: replay the full artifact from the workspace checkpoint after
   repair, then stop later block forward because the whole artifact already
   covers the remaining setup.
4. Done locally: record repeated work with `whole_script_recovery` and
   `whole_script_recovery_finalize` execution phases.

## Phase 4: Experiment Accounting

Status: implemented locally.

Completed tasks:

- Added `ablation_mode` to `llm-usage-projects.jsonl`.
- Added `progress_control` to batch JSON output for each project when available.
- Added explicit final replay summary fields:
  - `final_clean_replay_enabled`
  - `final_clean_replay_ok`
  - `final_clean_replay_image`
  - `final_clean_replay_failure_stage`
- Added documentation examples for running each mode with a distinct
  `--run-id-prefix`, such as `repo2run-full` or `repo2run-no-rollback`.

Remaining optional task:

- Consider writing `ablation-results.jsonl` for table generation.

## Recommended Experiment Commands

Use distinct run id prefixes so variants do not share Docker images or run
directories:

```sh
uv run pheragent build-projects \
  --projects-file tests/projects/repo2run.txt \
  --projects-dir projects-repo2run \
  --base-dockerfile tests/dockerfile/Dockerfile.heragent-thin \
  --run-id-prefix repo2run-full \
  --planner llm \
  --model gpt-5.4-20260305 \
  --llm-api chat-completions \
  --ablation full \
  --jobs 2 \
  --max-repair-attempts 20 \
  --stream-logs
```

For a component-removal run:

```sh
uv run pheragent build-projects \
  --projects-file tests/projects/repo2run.txt \
  --projects-dir projects-repo2run-no-rollback \
  --base-dockerfile tests/dockerfile/Dockerfile.heragent-thin \
  --run-id-prefix repo2run-no-rollback \
  --planner llm \
  --model gpt-5.4-20260305 \
  --llm-api chat-completions \
  --ablation without-checkpoint-rollback \
  --jobs 2 \
  --max-repair-attempts 20 \
  --stream-logs
```

## Notes and Constraints

- Do not modify target repository source code.
- Keep default behavior compatible with previous experiments unless an ablation
  mode is explicitly requested.
- Prefer one `--ablation` mode flag over many low-level user-facing switches.
- Keep all variants inside the same manifest/log/token accounting path.
- `--resume-from` is rejected for modes that require final clean replay until
  replay has a reliable workspace checkpoint source for resume runs.
