# pheragent

`pheragent` is a command-driven environment builder agent.

The core loop is intentionally block-oriented:

1. Analyze the repository on disk.
2. Build a base image from an input Dockerfile.
3. Start an isolated Docker container and copy the target repository into
   `/workspace/repo`.
4. Run a container preflight to capture OS, toolchain, package manager, Python,
   and repo marker facts from the actual runtime image.
5. Render setup blocks as shell scripts from repository and runtime context.
6. Commit the copied workspace as the first checkpoint.
7. Execute one block at a time.
8. After each successful block, create a Docker checkpoint with `docker commit`.
9. Continue in the current container on the success path to avoid unnecessary
   container restarts.
10. If a block fails, roll back to the block baseline checkpoint, apply a local repair, and
   replay the block.
11. Persist the final set of block scripts and the build manifest.

The default planner mode is `auto`: it uses the LLM planner when
`OPENAI_API_KEY` is present, otherwise it falls back to deterministic rules.

## Usage

Plan scripts without Docker:

```bash
uv run pheragent plan --repo /path/to/repo
```

Use the LLM planner with an OpenAI Responses API endpoint:

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://codex-byering.com:8317/v1"
export PHERAGENT_MODEL="gpt-5.5"

uv run pheragent plan --repo /path/to/repo --planner llm
```

For a Chat Completions compatible endpoint, switch the API surface:

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://example.test/v1/chat/completions"

uv run pheragent plan \
  --repo /path/to/repo \
  --planner llm \
  --llm-api chat-completions
```

You can force the deterministic planner with:

```bash
uv run pheragent plan --repo /path/to/repo --planner rules
```

Run a checkpointed build:

```bash
uv run pheragent build \
  --repo /path/to/repo \
  --base-dockerfile /path/to/Dockerfile \
  --planner llm \
  --llm-retries 3 \
  --llm-retry-delay 1 \
  --stream-logs
```

Run a progress-control ablation:

```bash
uv run pheragent build \
  --repo /path/to/repo \
  --base-dockerfile /path/to/Dockerfile \
  --planner llm \
  --ablation full \
  --stream-logs
```

Available ablation modes are `full`, `single-command-forward`,
`single-command-recovery`, `without-local-repair`,
`whole-script-forward`, `whole-script-recovery`,
`without-checkpoint-rollback`, and `without-final-clean-replay`. The default is
`full`, the paper-style setting that replays the final block scripts from a
clean workspace checkpoint before reporting success.

Clone and build multiple projects from an `owner/repo commit` file:

```bash
uv run pheragent build-projects \
  --projects-file tests/projects/executionAgent.txt \
  --projects-dir projects \
  --oracles-dir oracles \
  --base-dockerfile tests/dockerfile/Dockerfile.heragent-thin \
  --run-id-prefix execution-agent \
  --planner llm \
  --command-timeout 1800 \
  --llm-timeout 180 \
  --stream-logs
```

Use `--limit N` for a small smoke run, and `--stop-on-failure` when you want the
batch to stop at the first clone/build failure.

When comparing ablation modes, use distinct `--run-id-prefix` values, such as
`repo2run-full` and `repo2run-no-rollback`, so manifests, Docker images, and
success-skip decisions do not mix across variants. `build-projects` records the
ablation mode in `llm-usage-projects.jsonl` and will only skip an existing
successful run when its manifest was produced by the same ablation mode.

Use `--stream-logs` when you want live Docker, git, block, validation, repair,
and oracle command output in the terminal while still keeping complete logs
under `logs/`.

LLM planning and repair use the OpenAI Python SDK. The default `--llm-api
responses` mode calls the Responses API with `stream=True` and reconstructs JSON
from `response.output_text.delta` events. `--llm-api chat-completions` calls
`client.chat.completions.create(...)` with `response_format={"type":
"json_object"}`. LLM repair request failures or empty repair responses are
recorded as `llm_repair` executions under the failed block's logs.

Project checkout first tries to fetch the requested commit/ref directly. If a
short commit hash cannot be fetched as a remote ref, `pheragent` fetches remote
heads/tags with blob filtering and resolves the short hash locally before
checkout. Failed projects are written to:

```text
<projects-dir>/failed-projects.log
```

Each line is tab-separated: owner/repo, commit/ref, checkout directory, repo
path, and a short failure stage such as `prepare_failed` or `build_failed`.

For `build-projects`, `.github` is treated as oracle data instead of build
context. After checkout, if a cloned project contains `.github`, it is moved to
`<oracles-dir>/<project-name>/.github` before the environment build starts. This
keeps CI/CD validation hints out of the agent's repo context while preserving
them for later manual or oracle-based validation.

Validate the final checkpoint image with an oracle file:

```bash
uv run pheragent build \
  --repo /path/to/repo \
  --base-dockerfile /path/to/Dockerfile \
  --oracle-file /path/to/project.oracle.json \
  --oracle-timeout 1800
```

Resume from an existing checkpoint image:

```bash
uv run pheragent build \
  --repo /path/to/repo \
  --resume-from pheragent:previous-run-003-30-python-deps-success \
  --start-at-block 50-test-tooling
```

When `--start-at-block` is omitted, `pheragent` tries to infer the completed
block from checkpoint image tags ending in `<block-id>-success` or
`<block-id>-repaired`. If the same `--run-id` is reused and the run directory
still contains `blocks/*.json`, resume mode reuses those block scripts instead
of asking the planner to regenerate them.

Useful options:

```bash
uv run pheragent build \
  --repo /path/to/repo \
  --base-dockerfile /path/to/Dockerfile \
  --state-dir /path/to/repo/.pheragent \
  --image-prefix pheragent-local \
  --max-repair-attempts 2 \
  --command-timeout 900 \
  --keep-container
```

Outputs are written under:

```text
<state-dir>/runs/<run-id>/
  context.json
  blocks/*.json
  scripts/*.sh
  logs/<block-id>/*.log
  executions.jsonl
  manifest.json
```

When using `build-projects`, quarantined oracle data is written under:

```text
<oracles-dir>/<project-name>/.github/
```

The important artifact is `scripts/*.sh`: those files are the final block-by-block
setup plan, including any repair snippets that were committed back into a failed
block.

`executions.jsonl` stores one record per Docker build, block, validation, repair,
finalize, or oracle command. Each record points at a full log file under
`logs/`, so failures can be debugged with complete stdout/stderr instead of only
the manifest tails.

`context.json` includes both static repository analysis and `runtime_notes` from
the container preflight. Those runtime notes are included in LLM planning and in
LLM-assisted block repair.

Repair is part of the agent loop. Deterministic local repairs are tried first,
and when the overall planner is running with LLM support the agent can append
LLM-generated local repairs for the same failed block. The container is still
rolled back to the block baseline before each repair/replay attempt.

## Current scope

- Repository context analysis is deterministic and file-based.
- Docker execution uses the Docker CLI directly.
- Checkpoints are Docker images created with `docker commit`.
- Successful blocks keep using the current container after committing a
  checkpoint; checkpoints are used for resume and failure/repair rollback.
- Block planning in build mode uses both repository context and container
  preflight runtime context.
- Repair is local to the failed block. When LLM support is active, the failed
  block, stdout/stderr tails, runtime context, and heuristic hints are sent to
  the configured OpenAI SDK repair planner. Deterministic heuristics are prompt
  guidance only and are not executed directly.
- LLM planning uses the OpenAI Python SDK and does not store API keys on disk.
  Transient LLM request failures are retried; `auto` mode falls back to
  deterministic rules if the LLM planner cannot produce a plan.
