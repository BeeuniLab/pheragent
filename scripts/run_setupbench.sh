#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# LLM key, base URL, and default model are loaded by pheragent from .env.
# Pass --model or --openai-base-url after this script to override them.
#
# Optional controls:
#   SETUPBENCH_JOBS=2 scripts/run_setupbench.sh ...
#   SETUPBENCH_PROJECT_RETRIES=1 scripts/run_setupbench.sh ...
#   SETUPBENCH_JOBS=2 SETUPBENCH_PROJECT_RETRIES=1 scripts/run_setupbench.sh ...
#
# Keep the defaults conservative: parallel runs can increase Docker/container
# contention, and project retries increase LLM/token spend.
SETUPBENCH_JOBS="${SETUPBENCH_JOBS:-1}"
SETUPBENCH_PROJECT_RETRIES="${SETUPBENCH_PROJECT_RETRIES:-0}"

# Rerun the 26 projects that failed in setupbench-runs-all-gpt-4.1.
ONLY='^(TA-Lib/ta-lib-python|apache/cassandra|habitat-sh/habitat|servo/servo|monero-project/monero|aarora4/whisper|microsoft/TypeScript-Vue-Starter|openai/openai-node|celery/celery|fsspec/filesystem_spec|nedbat/coveragepy|public-apis/public-apis|python-hyper/rfc3986|pypa/packaging|Ousret/charset_normalizer|pallets/click|dstl/Stone-Soup|psf/black|testing-cabal/testtools|bolsote/isoduration|openstack/stevedore|nvbn/thefuck|falconry/falcon|dishait/tov-template|johnpapa/vscode-angular-snippets|reflex-dev/reflex)$'

args=(
  --run-root setupbench-runs-all-gpt-4.1-2rerun
  --fresh-results
  --only "$ONLY"
  --base-dockerfile tests/dockerfile/Dockerfile.heragent-thin
  --planner llm
  --llm-api responses
  --llm-retries 3
  --llm-retry-delay 5
  --llm-timeout 180
  --llm-max-tokens 4096
  --max-repair-attempts 20
  --max-probe-failures 5
  --project-retries "$SETUPBENCH_PROJECT_RETRIES"
  --jobs "$SETUPBENCH_JOBS"
  --command-timeout 1800
  --docker-build-timeout 7200
  --clone-timeout 1800
  --oracle-timeout 1800
  --stream-logs
)

args+=("$@")

uv run python scripts/run_setupbench.py "${args[@]}"
