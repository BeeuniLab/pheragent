from __future__ import annotations

from typing import Protocol

from .models import CommandBlock, RepoContext
from .utils import shell_script, slugify


class BlockPlanner(Protocol):
    def plan(self, context: RepoContext) -> list[CommandBlock]:
        ...


class RuleBasedBlockPlanner:
    """Deterministic bootstrap planner.

    This is intentionally conservative: it emits install-oriented command
    blocks from repo manifests, and leaves richer synthesis to future LLM
    planners that implement the same interface.
    """

    def plan(self, context: RepoContext) -> list[CommandBlock]:
        blocks: list[CommandBlock] = [
            CommandBlock(
                id="00-preflight",
                order=0,
                title="Preflight",
                goal="Capture basic OS, toolchain, and repository context.",
                script=shell_script(_preflight_script()),
                validation_command="test -d .",
            )
        ]
        order = 1
        for language in context.languages:
            builder = getattr(self, f"_plan_{language}", None)
            if builder is None:
                continue
            block = builder(order, context)
            if block is not None:
                blocks.append(block)
                order += 1
        if len(blocks) == 1:
            blocks.append(
                CommandBlock(
                    id="10-generic-inspect",
                    order=1,
                    title="Generic Inspect",
                    goal="Provide a minimal generic repository inspection block.",
                    script=shell_script(
                        """
echo "[pheragent] no known package manager detected"
find . -maxdepth 2 -type f | sort | sed -n '1,120p'
"""
                    ),
                    validation_command="test -d .",
                )
            )
        return blocks

    def _plan_python(self, order: int, context: RepoContext) -> CommandBlock:
        python_validation = (
            'python3 -c "import sys; print(sys.version)" '
            '|| python -c "import sys; print(sys.version)"'
        )
        return CommandBlock(
            id=_ordered_id(order, "python-deps"),
            order=order,
            title="Python Dependencies",
            goal="Install Python project dependencies from detected manifests.",
            script=shell_script(_python_script(use_uv="uv" in context.package_managers)),
            validation_command=_safe_python_validation_command(context, python_validation),
        )

    def _plan_node(self, order: int, context: RepoContext) -> CommandBlock:
        return CommandBlock(
            id=_ordered_id(order, "node-deps"),
            order=order,
            title="Node Dependencies",
            goal="Install Node.js dependencies from detected lockfiles.",
            script=shell_script(_node_script(context.package_managers)),
            validation_command=_first_present(
                context.test_commands,
                prefix="npm",
                fallback="node --version && npm --version",
            ),
        )

    def _plan_go(self, order: int, context: RepoContext) -> CommandBlock:
        return CommandBlock(
            id=_ordered_id(order, "go-deps"),
            order=order,
            title="Go Dependencies",
            goal="Download Go module dependencies.",
            script=shell_script(_go_script()),
            validation_command=_safe_go_validation_command(),
        )

    def _plan_rust(self, order: int, context: RepoContext) -> CommandBlock:
        return CommandBlock(
            id=_ordered_id(order, "rust-deps"),
            order=order,
            title="Rust Dependencies",
            goal="Fetch Rust crate dependencies.",
            script=shell_script(
                """
echo "[pheragent] fetching rust dependencies"
cargo --version
cargo fetch
"""
            ),
            validation_command=_first_present(
                context.test_commands,
                prefix="cargo",
                fallback="cargo test --no-run",
            ),
        )

    def _plan_java(self, order: int, context: RepoContext) -> CommandBlock:
        return CommandBlock(
            id=_ordered_id(order, "java-deps"),
            order=order,
            title="Java Dependencies",
            goal="Warm Maven or Gradle dependencies.",
            script=shell_script(_java_script(context.package_managers)),
            validation_command=_first_present(
                context.test_commands,
                prefix="mvn",
                fallback="mvn -q -DskipTests test || ./gradlew testClasses || gradle testClasses",
            ),
        )


def _ordered_id(order: int, title: str) -> str:
    return f"{order:02d}-{slugify(title)}"


def _first_present(values: list[str], *, prefix: str, fallback: str) -> str:
    for value in values:
        if value.startswith(prefix):
            return value
    return fallback


def _safe_python_validation_command(context: RepoContext, fallback: str) -> str:
    command = _first_present(context.test_commands, prefix="python", fallback=fallback)
    normalized = " ".join(command.split()).lower()
    if "pytest" in normalized:
        return _pytest_collect_validation_command()
    return command


def _pytest_collect_validation_command() -> str:
    return (
        "if [ -x .venv/bin/python ]; then PYTHON_BIN=./.venv/bin/python; "
        "elif command -v python >/dev/null 2>&1; then PYTHON_BIN=python; "
        "else PYTHON_BIN=python3; fi; "
        '"$PYTHON_BIN" -m pytest --collect-only -q; '
        "status=$?; "
        'if [ "$status" -eq 5 ]; then '
        'echo "[pheragent] no pytest tests collected"; exit 0; '
        "fi; "
        'exit "$status"'
    )


def _safe_go_validation_command() -> str:
    return (
        'PATH="/usr/local/go/bin:$PATH" '
        'GOFLAGS="${GOFLAGS:-} -buildvcs=false" '
        "go list -mod=mod ./... >/dev/null"
    )


def _preflight_script() -> str:
    return """
echo "[pheragent] preflight"
pwd
uname -a || true
cat /etc/os-release 2>/dev/null || true
find . -maxdepth 2 -type f | sort | sed -n '1,120p'
command -v sh >/dev/null 2>&1 && sh --version 2>/dev/null || true
command -v python3 >/dev/null 2>&1 && python3 --version || true
command -v python >/dev/null 2>&1 && python --version || true
command -v node >/dev/null 2>&1 && node --version || true
command -v npm >/dev/null 2>&1 && npm --version || true
command -v go >/dev/null 2>&1 && go version || true
command -v cargo >/dev/null 2>&1 && cargo --version || true
"""


def _go_script() -> str:
    return """
echo "[pheragent] installing go module dependencies"
export PATH="/usr/local/go/bin:$PATH"
go version
go mod download
"""


def _python_script(*, use_uv: bool) -> str:
    uv_branch = ""
    if use_uv:
        uv_branch = """
if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then
  echo "[pheragent] uv.lock detected; running uv sync"
  uv sync --all-extras --dev || uv sync
  exit 0
fi
"""
    return (
        """
echo "[pheragent] installing python dependencies"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "python executable not found" >&2
  exit 127
fi
"""
        + uv_branch
        + """
"$PYTHON_BIN" -m pip --version >/dev/null 2>&1 || "$PYTHON_BIN" -m ensurepip --upgrade || true
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
if [ -f requirements.txt ]; then
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi
if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ]; then
  "$PYTHON_BIN" -m pip install -e '.[dev]' || "$PYTHON_BIN" -m pip install -e .
fi
"$PYTHON_BIN" -m pytest --version >/dev/null 2>&1 || "$PYTHON_BIN" -m pip install pytest
"""
    )


def _node_script(package_managers: list[str]) -> str:
    prefers_pnpm = "pnpm" in package_managers
    prefers_yarn = "yarn" in package_managers
    return f"""
echo "[pheragent] installing node dependencies"
node --version
npm --version
ensure_pnpm() {{
  if command -v pnpm >/dev/null 2>&1 && pnpm --version >/dev/null 2>&1; then
    return 0
  fi
  PNPM_PACKAGE=pnpm@9
  NODE_VERSION=$(node -p "process.versions.node" 2>/dev/null || echo 0.0.0)
  NODE_MAJOR=${{NODE_VERSION%%.*}}
  NODE_REST=${{NODE_VERSION#*.}}
  NODE_MINOR=${{NODE_REST%%.*}}
  if [ "$NODE_MAJOR" -gt 22 ] || \
     {{ [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -ge 13 ]; }}; then
    PNPM_PACKAGE=pnpm
  fi
  npm install -g "$PNPM_PACKAGE"
  pnpm --version
}}
if command -v corepack >/dev/null 2>&1; then
  corepack enable || true
fi
if [ -f pnpm-lock.yaml ] && {"true" if prefers_pnpm else "false"}; then
  ensure_pnpm
  pnpm install --frozen-lockfile || pnpm install
elif [ -f yarn.lock ] && {"true" if prefers_yarn else "false"}; then
  if command -v yarn >/dev/null 2>&1; then
    yarn install --frozen-lockfile || yarn install
  else
    npm install -g yarn
    yarn install --frozen-lockfile || yarn install
  fi
elif [ -f package-lock.json ]; then
  npm ci || npm install
else
  npm install
fi
"""


def _java_script(package_managers: list[str]) -> str:
    has_maven = "maven" in package_managers
    has_gradle = "gradle" in package_managers
    gradle_enabled = "true" if has_gradle else "false"
    return f"""
echo "[pheragent] warming java dependencies"
if [ -f pom.xml ] && {"true" if has_maven else "false"}; then
  mvn -q -DskipTests dependency:go-offline
fi
if {{ [ -f build.gradle ] || [ -f build.gradle.kts ]; }} && {gradle_enabled}; then
  if [ -x ./gradlew ]; then
    ./gradlew dependencies --no-daemon || true
  elif [ -f ./gradlew ]; then
    chmod +x ./gradlew
    ./gradlew dependencies --no-daemon || true
  else
    gradle dependencies || true
  fi
fi
"""
