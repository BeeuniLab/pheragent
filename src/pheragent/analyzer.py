from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .models import RepoContext


class RepoAnalyzer:
    def analyze(self, repo_path: Path) -> RepoContext:
        repo = repo_path.expanduser().resolve()
        if not repo.is_dir():
            raise ValueError(f"repo path is not a directory: {repo}")

        context = RepoContext(repo_path=repo)
        self._detect_python(repo, context)
        self._detect_node(repo, context)
        self._detect_go(repo, context)
        self._detect_rust(repo, context)
        self._detect_java(repo, context)

        if not context.package_files:
            context.notes.append("No common dependency manifest was found.")
        return context

    def _record_file(self, repo: Path, context: RepoContext, relative: str) -> bool:
        if (repo / relative).exists():
            context.package_files.append(relative)
            return True
        return False

    def _add_unique(self, values: list[str], value: str) -> None:
        if value not in values:
            values.append(value)

    def _detect_python(self, repo: Path, context: RepoContext) -> None:
        found = False
        for filename in (
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            "uv.lock",
            "poetry.lock",
            "Pipfile",
            "tox.ini",
        ):
            found = self._record_file(repo, context, filename) or found
        if not found:
            return
        self._add_unique(context.languages, "python")
        if (repo / "uv.lock").exists():
            self._add_unique(context.package_managers, "uv")
        if (repo / "poetry.lock").exists():
            self._add_unique(context.package_managers, "poetry")
        self._add_unique(context.package_managers, "pip")
        if (repo / "tests").is_dir():
            context.test_commands.append("python -m pytest -q")
        pyproject = repo / "pyproject.toml"
        if pyproject.exists():
            self._read_pyproject(pyproject, context)

    def _read_pyproject(self, path: Path, context: RepoContext) -> None:
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            context.notes.append(f"Could not parse pyproject.toml: {exc}")
            return
        tool = payload.get("tool", {})
        if (
            isinstance(tool, dict)
            and "pytest" in tool
            and "python -m pytest -q" not in context.test_commands
        ):
            context.test_commands.append("python -m pytest -q")
        project = payload.get("project", {})
        if isinstance(project, dict) and project.get("scripts"):
            context.notes.append("pyproject.toml defines project scripts.")

    def _detect_node(self, repo: Path, context: RepoContext) -> None:
        if not self._record_file(repo, context, "package.json"):
            return
        self._add_unique(context.languages, "node")
        package_json = repo / "package.json"
        for filename, manager in (
            ("pnpm-lock.yaml", "pnpm"),
            ("yarn.lock", "yarn"),
            ("package-lock.json", "npm"),
        ):
            if self._record_file(repo, context, filename):
                self._add_unique(context.package_managers, manager)
        if not any(manager in context.package_managers for manager in ("pnpm", "yarn", "npm")):
            self._add_unique(context.package_managers, "npm")
        try:
            payload = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            context.notes.append(f"Could not parse package.json: {exc}")
            return
        scripts = payload.get("scripts", {})
        if isinstance(scripts, dict):
            if "build" in scripts:
                context.build_commands.append("npm run build")
            if "test" in scripts:
                context.test_commands.append("npm test")

    def _detect_go(self, repo: Path, context: RepoContext) -> None:
        if self._record_file(repo, context, "go.mod"):
            self._add_unique(context.languages, "go")
            self._add_unique(context.package_managers, "go")
            context.test_commands.append("go test ./...")

    def _detect_rust(self, repo: Path, context: RepoContext) -> None:
        if self._record_file(repo, context, "Cargo.toml"):
            self._add_unique(context.languages, "rust")
            self._add_unique(context.package_managers, "cargo")
            context.test_commands.append("cargo test")

    def _detect_java(self, repo: Path, context: RepoContext) -> None:
        found = False
        for filename in ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"):
            found = self._record_file(repo, context, filename) or found
        if not found:
            return
        self._add_unique(context.languages, "java")
        if (repo / "pom.xml").exists():
            self._add_unique(context.package_managers, "maven")
            context.test_commands.append("mvn test")
        if (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists():
            self._add_unique(context.package_managers, "gradle")
            context.test_commands.append("./gradlew test || gradle test")
