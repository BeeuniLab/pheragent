# Agent Loop Optimization Plan

This document tracks the current optimization pass for the core environment
builder loop. The focus is not adding user-facing modes; it is improving the
agent's ability to build and repair a repository environment inside one
checkpointed run.

## Status

| Item | Status | Notes |
| --- | --- | --- |
| Record optimization plan | done | Captured scope and task state in this file. |
| Container preflight context | done | Runtime facts are collected from the started Docker container before block planning. |
| Repair context bundle | done | LLM repair receives the failed block, failure output, prior blocks, recent executions, runtime context, and heuristic hints. |
| Tests | done | Added coverage for planning with container context and repair context payloads without invoking Docker or a real LLM. |
| Verification | done | `uv run ruff check .` and `uv run --with-editable . python -m pytest -q` pass. |

## Intended Flow

1. Analyze the repository on disk.
2. Build the base Docker image.
3. Start an isolated container and copy the repo into `/workspace/repo`.
4. Run a container preflight command to capture OS, Python, package manager,
   toolchain, GPU/CUDA, and shell facts.
5. Add that runtime context to the repository context before generating blocks.
6. Execute generated blocks one by one, committing a checkpoint after each
   successful block.
7. On failure, build a local repair context from the failed block, error output,
   prior successful blocks, recent execution metadata, and container preflight.
8. When LLM repair is active, send the failure bundle to the LLM repair planner
   first and use deterministic local heuristics as hints/fallback repairs.
9. On the success path, continue in the current container; roll back to the block
   baseline checkpoint only for failure/repair or explicit resume.

## Non-Goals

- Do not expose a separate repair planner CLI option.
- Do not replace checkpoint/replay with Dockerfile generation.
- Do not make resume the main workflow; it remains an optional recovery helper.

## Completed Changes

- Build mode now collects container preflight facts before block planning.
- `RepoContext.runtime_notes` stores the preflight summary and is persisted in
  `context.json`.
- LLM repair payloads now include a `RepairContext` with repo/runtime context,
  prior successful blocks, recent execution records, the baseline checkpoint, and
  heuristic hints derived from the failure output.
- Successful blocks commit checkpoints but keep using the current container;
  Docker restore is reserved for failure/repair and resume paths.
- The public CLI remains centered on the overall agent planner; repair remains
  an internal part of the agent loop.
