# SetupBench Failure Triage

Date: 2026-06-17

Scope: server run at `/home/lix/EnvAgent/love/lix_pheragent`.

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| Failure triage | Done | `setupbench-runs-oracle-rerun` has 25 projects: 8 ok, 17 failed. |
| Runner result accounting | Fixed | `scripts/run_setupbench.py` now preserves result files unless `--fresh-results` is set, finds nested manifests, records manifest summary fields, and supports `--rerun-failures` with failed workspace reset. |
| SetupBench task context | Fixed | Per-project task descriptions are passed into pheragent via `--task-description`; planner and repair LLM payloads receive them through `repo_context.task_description`. |
| Python venv handling | Fixed | Generated Python dependency scripts expose `.venv` as `python/python3/pip/pip3`; build-test validation now prefers `.venv/bin/python` and treats no collected pytest tests as a non-environment failure. Repair hints discourage system pip on PEP 668. |
| Go toolchain handling | Fixed | Go dependency blocks now install an official Go release when `go.mod` requires Go >= 1.24 and validate with `GOFLAGS=-buildvcs=false`. |
| Oracle command safety | Fixed | Oracle loading rewrites known unsafe `kill -TERM -$pgid*` cleanup to direct child PID cleanup. |
| Oracle command correctness | Partial | `python -m wagtail start` is normalized to `wagtail start`. Other project-specific oracle issues, such as missing Prometheus startup or full-suite failures, remain data/oracle quality issues. |

## Observed Failures

### Environment Build Failures

- `bolsote/isoduration`: `03-build-test-prep` uses `/usr/bin/python3`; `.venv` has pytest, but system Python does not. Repair then uses system pip and hits PEP 668.
- `fsspec/filesystem_spec`: same `.venv` vs system Python problem.
- `pypa/packaging`: package installed into `.venv`; validation/repair import with system Python and report `ModuleNotFoundError: No module named 'packaging'`.
- `psf/black`: package installed into `.venv`; validation starts with system Python. Later `.venv` can run `black --version`, but pytest collect still exits nonzero.
- `nedbat/coveragepy`: pytest config requires plugins/options such as xdist/flaky; validation suppresses stderr in later attempts, hiding the final reason.
- `caddyserver/caddy`: Go 1.24 is required, but apt installs Go 1.22. Also needs `-buildvcs=false` for validation/build commands that trigger VCS stamping.

### Oracle Failures Likely Caused By Oracle Commands

- `DanWahlin/Angular-JumpStart`, `hoodiehq/hoodie`, `lhartikk/naivechain`, `microsoft/vscode-remote-try-python`: oracle exits 143 with little output. The oracle commands use `kill -TERM -$pgid`, which can kill the running oracle shell/process group.
- `prometheus/prometheus`: oracle curls `localhost:9090/metrics` without starting Prometheus.
- `wagtail/wagtail`: oracle uses `python -m wagtail start mysite`, but `wagtail` is a package without `__main__`; should use the `wagtail` CLI.

### Oracle Failures That May Be Project/Test-Suite Issues

- `pallets/flask`: full pytest suite has old-code/new-dependency failures, not just missing setup.
- `dstl/Stone-Soup`: full pytest collection requires optional dependencies such as pandas readers.
- `laramies/theHarvester`: tests hit external API behavior/rate limits such as 403/429.
- `melt-ui/melt-ui`: dev server oracle hits `EMFILE: too many open files`; likely needs `ulimit -n` or non-watch validation.

## Fix Plan

1. Fix SetupBench runner accounting:
   - Preserve existing result files unless explicitly starting a fresh run.
   - Resolve manifest paths under `state/<slug>/*/runs/*/manifest.json`.
   - Store manifest-derived error/final image in `results.jsonl`.
   - Support `--rerun-failures` to rerun only repos currently listed in `results/failures.tsv` while keeping successful projects/results.
   - Reset selected failed project workspaces under `projects/<slug>` and `state/<slug>` before rerun to avoid stale repo/state logs.
   - Status: fixed in `scripts/run_setupbench.py`.

2. Fix Python block behavior:
   - Make generated validation commands prefer `.venv/bin/python`.
   - Make repair prompt/context strongly prefer `.venv/bin/python -m pip` over system `python3 -m pip`.
   - Avoid system pip repair commands that trigger PEP 668.
   - Status: fixed in `src/pheragent/llm_planner.py`, `src/pheragent/planner.py`, and `src/pheragent/repair.py`.

3. Fix Go block behavior:
   - Prefer a modern Go install path when `go.mod` requires a newer version than apt provides.
   - Use `GOFLAGS=-buildvcs=false` or `go list -buildvcs=false` in validation.
   - Status: fixed in LLM and rule-based Go dependency blocks.

4. Fix obvious oracle command bugs:
   - Replace unsafe negative-process-group termination with direct child cleanup or isolated `setsid` cleanup.
   - Start Prometheus before curling metrics.
   - Use `wagtail start` instead of `python -m wagtail`.
   - Status: unsafe cleanup and Wagtail CLI normalization are fixed in `src/pheragent/oracle.py`; Prometheus startup remains a project-specific oracle data fix.

5. Re-run focused validation:
   - Unit tests for runner manifest lookup and oracle validation.
   - Unit tests for SetupBench task description extraction and CLI/context propagation.
   - Focused SetupBench reruns for a small set of previously failing projects.
   - Status: unit tests added and passing; focused server reruns remain for the next experiment.

## Verification

- `uv run pytest -q`: 100 passed.
- `uv run ruff check .`: all checks passed.

## Rerun Failed Projects Only

Use the same `--run-root` as the original run and do not pass `--fresh-results`:

```sh
uv run python scripts/run_setupbench.py \
  --run-root setupbench-runs-oracle-rerun \
  --rerun-failures \
  --base-dockerfile tests/dockerfile/Dockerfile.heragent-thin \
  --planner llm \
  --model gpt-5.4-20260305 \
  --llm-api chat-completions \
  --openai-base-url http://127.0.0.1:4142/v1 \
  --llm-retries 3 \
  --llm-retry-delay 5 \
  --llm-timeout 180 \
  --max-repair-attempts 20 \
  --command-timeout 1800 \
  --docker-build-timeout 1800 \
  --oracle-timeout 1800 \
  --stream-logs
```

`--rerun-failures` reads `setupbench-runs-oracle-rerun/results/failures.tsv`, removes the selected old failures before rerun, deletes the selected failed workspaces under `projects/<slug>` and `state/<slug>`, and appends only projects that still fail. Existing successful projects are not selected or deleted.
