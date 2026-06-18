# SetupBench Failure Triage

Date: 2026-06-18

Scope: server run at `/home/lix/EnvAgent/love/lix_pheragent`.

## Current Status

| Area | Status | Notes |
| --- | --- | --- |
| Failure triage | Done | `setupbench-runs-oracle-rerun` has 25 projects: 8 ok, 17 failed. |
| Rerun triage | Done | After rerun on commit `80f6fac`, 17 selected failures became 6 ok and 11 failed. The remaining failures were grouped into stale Docker containers, unsafe generated blocks, broken requirements include handling, and oracle commands that run full application/test validation. |
| Runner result accounting | Fixed | `scripts/run_setupbench.py` now preserves result files unless `--fresh-results` is set, finds nested manifests, records manifest summary fields, and supports `--rerun-failures` with failed workspace reset. |
| SetupBench task context | Fixed | Per-project task descriptions are passed into pheragent via `--task-description`; planner and repair LLM payloads receive them through `repo_context.task_description`. |
| Interrupted reruns | Fixed | Failure records are now updated per completed project, so interrupting `--rerun-failures` does not erase unprocessed failures. |
| Stale Docker containers | Fixed | Docker runtime removes a same-name pheragent container before `docker run`, avoiding conflicts after interrupted runs. |
| SetupBench oracle scope | Fixed | Full-suite `pytest` and `tox` SetupBench oracle commands are normalized to environment-level collect/config checks; web-server oracles get bounded `setsid` startup and cleanup. |
| Python venv handling | Fixed | Generated Python dependency scripts expose `.venv` as `python/python3/pip/pip3`; build-test validation now prefers `.venv/bin/python` and treats no collected pytest tests as a non-environment failure. Repair hints discourage system pip on PEP 668. |
| Python requirements includes | Fixed | Sanitized requirements are installed from a temp mirror that preserves relative include paths such as `-r requirements/base.txt`. |
| Go toolchain handling | Fixed | Go dependency blocks now install an official Go release when `go.mod` requires Go >= 1.24 and validate with `GOFLAGS=-buildvcs=false`. |
| LLM block hardening | Fixed | Go install commands embedded in `system-deps` are recognized as Go dependency blocks; build/test prep blocks that start dev servers or run project generators are replaced with lightweight tool checks. |
| Oracle command safety | Fixed | Oracle loading rewrites known unsafe process cleanup; web-server oracles now run in their own session and clean up child processes. |
| Oracle command correctness | Fixed | `python -m wagtail start` is normalized to `wagtail start`; Prometheus metrics oracles now start Prometheus before curling; full-suite pytest/tox oracles are reduced to environment-level checks. |
| Latest rerun failures | Fixed locally | After commit `a793a92`, `setupbench-runs-oracle-rerun` had 11 projects: 7 ok, 4 oracle failures. Local fixes cover Prometheus VCS stamping, Caddy binary lookup/build, and web-oracle cleanup self-termination. |

## Observed Failures

### Environment Build Failures

- `prometheus/prometheus`: interrupted run left a deterministic container name in Docker, causing a later `docker run --name ...` conflict.
- `caddyserver/caddy`: LLM placed Go install into `01-system-deps`; the parser did not recognize `go version >/dev/null` validation as a Go dependency block, so Ubuntu Go 1.22 was installed for a repo requiring Go 1.24.
- `laramies/theHarvester`: sanitized `requirements.txt` was installed from `/tmp`, breaking nested relative includes such as `-r requirements/base.txt`.
- `wagtail/wagtail`: LLM build/test prep ran `python -m wagtail ...`, but Wagtail exposes a CLI entry point rather than a `__main__` module; the block also tried to create a generated project during setup.
- `melt-ui/melt-ui`: LLM build/test prep started a Vite dev server; low file-descriptor/watch limits caused `EMFILE`, which should not be part of environment setup validation.
- `bolsote/isoduration`: `03-build-test-prep` uses `/usr/bin/python3`; `.venv` has pytest, but system Python does not. Repair then uses system pip and hits PEP 668.
- `fsspec/filesystem_spec`: same `.venv` vs system Python problem.
- `pypa/packaging`: package installed into `.venv`; validation/repair import with system Python and report `ModuleNotFoundError: No module named 'packaging'`.
- `psf/black`: package installed into `.venv`; validation starts with system Python. Later `.venv` can run `black --version`, but pytest collect still exits nonzero.
- `nedbat/coveragepy`: pytest config requires plugins/options such as xdist/flaky; validation suppresses stderr in later attempts, hiding the final reason.
- `caddyserver/caddy`: Go 1.24 is required, but apt installs Go 1.22. Also needs `-buildvcs=false` for validation/build commands that trigger VCS stamping.

### Oracle Failures Likely Caused By Oracle Commands

- `fsspec/filesystem_spec`, `dstl/Stone-Soup`, `psf/black`, `pallets/flask`: oracle ran the full pytest suite; failures were application/test dependency compatibility, not missing environment setup. These are now normalized to `pytest --collect-only`.
- `nedbat/coveragepy`: oracle ran a full tox env (`python -m tox -e py310`) on a Python 3.12 base. This is now normalized to `tox --showconfig` for environment/config readiness.
- `hoodiehq/hoodie`, `melt-ui/melt-ui`: web oracle process cleanup could leave child Node/Vite processes alive and later cause port conflicts. Web oracles now use `setsid`, bounded polling, and cleanup.
- `prometheus/prometheus`: oracle curled metrics without starting Prometheus. The oracle command now builds/starts Prometheus before curling `/metrics`.
- `DanWahlin/Angular-JumpStart`, `hoodiehq/hoodie`, `lhartikk/naivechain`, `microsoft/vscode-remote-try-python`: oracle exits 143 with little output. The oracle commands use `kill -TERM -$pgid`, which can kill the running oracle shell/process group.
- `prometheus/prometheus`: oracle curls `localhost:9090/metrics` without starting Prometheus.
- `wagtail/wagtail`: oracle uses `python -m wagtail start mysite`, but `wagtail` is a package without `__main__`; should use the `wagtail` CLI.
- Latest rerun `prometheus/prometheus`: Prometheus oracle started the binary, but `go build` failed with VCS stamping (`Use -buildvcs=false`). The oracle now sets `GOFLAGS=-buildvcs=false`.
- Latest rerun `caddyserver/caddy`: build/test prep produced a usable `./caddy`, but oracle ran `caddy list-modules` from PATH and failed with `caddy: not found`. The oracle now uses PATH `caddy`, `./caddy`, or builds `/tmp/pheragent-caddy`.
- Latest rerun `hoodiehq/hoodie` and `melt-ui/melt-ui`: web oracle exited `143` immediately because cleanup matched the current `sh -lc` oracle process. Cleanup now records `$$` and excludes that PID.

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
   - Build Prometheus with `GOFLAGS=-buildvcs=false`.
   - Rewrite Caddy `list-modules` validation to use an available or temporary binary.
   - Exclude the running oracle shell from web-process cleanup.
   - Status: fixed in `src/pheragent/oracle.py`.

5. Re-run focused validation:
   - Unit tests for runner manifest lookup and oracle validation.
   - Unit tests for SetupBench task description extraction and CLI/context propagation.
   - Focused SetupBench reruns for a small set of previously failing projects.
   - Status: unit tests added and passing; focused server reruns remain for the next experiment.

## Verification

- `uv run pytest -q`: 109 passed.
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
