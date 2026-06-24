#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = Path("executionagent-runs/results/block_validation_summary.json")
DEFAULT_ARTIFACT_ROOT = Path("tests/projects/success_output_multi-oracles")

MANUAL_PROJECT_MAP = {
    "commons-csv": "commonscsv",
    "json-c": "jsonc",
    "spring-security": "spring",
    "vue": "Vue",
}

TOOL_FAMILY_ALIASES = {
    "mvn": "maven",
    "mvnw": "maven",
    "gradle": "gradle",
    "gradlew": "gradle",
    "python": "python",
    "python3": "python",
    "pip": "pip",
    "pip3": "pip",
    "pytest": "pytest",
    "tox": "tox",
    "npm": "npm",
    "npx": "npm",
    "node": "node",
    "pnpm": "pnpm",
    "yarn": "yarn",
    "cargo": "cargo",
    "rustc": "rust",
    "java": "java",
    "javac": "java",
    "cmake": "cmake",
    "ninja": "ninja",
    "make": "make",
    "meson": "meson",
    "bazel": "bazel",
    "gcc": "gcc",
    "g++": "gcc",
    "gfortran": "gfortran",
    "git": "git",
    "autoconf": "autotools",
    "automake": "autotools",
    "libtoolize": "autotools",
    "autoreconf": "autotools",
}

GENERIC_PREFIXES = (
    "cd /workspace/repo && ",
    "cd /workspace/repo &&",
)

LOG_REF_RE = re.compile(r"^(?P<path>[^:]+?)(?::(?P<lines>.*))?$")
TOKEN_RE = re.compile(r"[A-Za-z0-9_.:+/@-]+")


@dataclass(frozen=True)
class ClauseFeature:
    clause: str
    families: frozenset[str]
    categories: frozenset[str]


@dataclass(frozen=True)
class RuntimeRow:
    command: str
    workflow: str
    step: str
    result: str
    evidence: str
    log_path: str | None
    clauses: tuple[str, ...]
    features: tuple[ClauseFeature, ...]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary_path = resolve_path(args.summary)
    artifact_root = resolve_path(args.artifact_root)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    artifact_dirs = {
        path.name: path for path in sorted(artifact_root.iterdir()) if path.is_dir()
    }
    normalized_artifact_names = {normalize_name(name): name for name in artifact_dirs}

    matched_projects = 0
    matched_validations = 0
    exact_match_count: Counter[str] = Counter()
    project_without_matches: list[str] = []

    for project in summary.get("projects", []):
        artifact_dir = resolve_project_artifact_dir(
            project,
            artifact_dirs=artifact_dirs,
            normalized_artifact_names=normalized_artifact_names,
        )
        runtime_rows = load_runtime_rows(artifact_dir)

        project_match_count = 0
        project_exact_count = 0
        project_related_count = 0
        for validation in project.get("validations", []):
            match = match_validation(validation, runtime_rows)
            validation["ci_log_match"] = match
            if match["matched"]:
                project_match_count += 1
                matched_validations += 1
                exact_match_count[match["match_kind"]] += 1
                if match["match_kind"] == "exact":
                    project_exact_count += 1
                elif match["match_kind"] == "related":
                    project_related_count += 1

        project["ci_artifact_dir"] = str(artifact_dir) if artifact_dir else None
        project["ci_runtime_command_record_count"] = len(runtime_rows)
        project["ci_matched_validation_count"] = project_match_count
        project["ci_exact_match_count"] = project_exact_count
        project["ci_related_match_count"] = project_related_count
        project["ci_unmatched_validation_count"] = (
            project.get("validation_count", 0) - project_match_count
        )

        if project_match_count > 0:
            matched_projects += 1
        else:
            project_without_matches.append(project.get("project_name", "<unknown>"))

    enrichment = {
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_root": str(artifact_root),
        "matched_project_count": matched_projects,
        "unmatched_project_count": len(project_without_matches),
        "matched_validation_count": matched_validations,
        "exact_match_count": exact_match_count.get("exact", 0),
        "related_match_count": exact_match_count.get("related", 0),
        "no_command_match_projects": sorted(project_without_matches),
    }
    summary["ci_log_enrichment"] = enrichment

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    print(summary_path)
    print(json.dumps(enrichment, ensure_ascii=True))
    if project_without_matches:
        print("Projects with zero CI command matches:")
        for name in sorted(project_without_matches):
            print(name)
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich block_validation_summary.json with CI log command matches."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY,
        help="Path to block_validation_summary.json.",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=DEFAULT_ARTIFACT_ROOT,
        help="Directory that contains per-project CI artifacts and combined_command_results.json.",
    )
    return parser.parse_args(argv)


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def resolve_project_artifact_dir(
    project: dict[str, Any],
    *,
    artifact_dirs: dict[str, Path],
    normalized_artifact_names: dict[str, str],
) -> Path | None:
    project_name = project.get("project_name")
    if project_name in MANUAL_PROJECT_MAP:
        return artifact_dirs.get(MANUAL_PROJECT_MAP[project_name])

    owner_repo = str(project.get("owner_repo", ""))
    candidates = [
        str(project_name or ""),
        owner_repo.split("-", 1)[-1] if "-" in owner_repo else owner_repo,
        owner_repo.rsplit("-", 1)[-1],
    ]
    for candidate in candidates:
        normalized = normalize_name(candidate)
        artifact_name = normalized_artifact_names.get(normalized)
        if artifact_name:
            return artifact_dirs[artifact_name]
    return None


def load_runtime_rows(artifact_dir: Path | None) -> list[RuntimeRow]:
    if artifact_dir is None:
        return []
    combined_path = artifact_dir / "combined_command_results.json"
    if not combined_path.is_file():
        return []

    data = json.loads(combined_path.read_text(encoding="utf-8"))
    rows: list[RuntimeRow] = []
    for entry in data.get("entries", []):
        row = entry.get("row", {})
        command = row.get("命令")
        if not isinstance(command, str):
            continue
        command = strip_markdown_code(command)
        clauses = tuple(extract_clauses(command))
        features = tuple(feature for clause in clauses if (feature := build_feature(clause)))
        if not features:
            continue
        evidence = strip_markdown_code(str(row.get("证据行号", "")))
        rows.append(
            RuntimeRow(
                command=command,
                workflow=strip_markdown_code(str(row.get("workflow", ""))),
                step=strip_markdown_code(str(row.get("step", ""))),
                result=str(row.get("结果", "")),
                evidence=evidence,
                log_path=resolve_log_path(artifact_dir, evidence),
                clauses=clauses,
                features=features,
            )
        )
    return rows


def strip_markdown_code(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    return value.replace(" [multiline]", "")


def canonicalize_command(value: str) -> str:
    value = strip_markdown_code(value)
    replacements = {
        "./.venv/bin/python": "python",
        ".venv/bin/python": "python",
        "/tmp/pheragent-venv-check/bin/python": "python",
        ".pheragent-tools/bin/node": "node",
        ".pheragent-tools/bin/npm": "npm",
        "./gradlew": "gradlew",
        "./mvnw": "mvnw",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"/opt/[^\s]*/bin/mvn", "mvn", value)
    value = value.replace("/workspace/repo/", "")
    for prefix in GENERIC_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix) :]
    value = re.sub(r"\s+>/dev/null(?:\s+2>&1)?", "", value)
    value = re.sub(r"\s+2>/dev/null", "", value)
    value = re.sub(r"\s+1>/dev/null", "", value)
    value = re.sub(r"\s+", " ", value.strip())
    return value.strip("() ")


def extract_clauses(value: str) -> list[str]:
    text = canonicalize_command(value).replace("\n", "; ")
    for keyword in (" then ", " else ", " fi", " do ", " done"):
        text = text.replace(keyword, "; ")
    parts = re.split(r"\s*(?:&&|\|\||;)\s*", text)
    clauses: list[str] = []
    for part in parts:
        clause = re.sub(r"\s+", " ", part.strip("() ")).strip()
        if clause:
            clauses.append(clause)
    return clauses


def build_feature(clause: str) -> ClauseFeature | None:
    ordered_tokens = [token.lower() for token in TOKEN_RE.findall(clause)]
    tokens = set(ordered_tokens)
    families: set[str] = set()
    if ordered_tokens:
        head = ordered_tokens[0]
        if head in TOOL_FAMILY_ALIASES:
            families.add(TOOL_FAMILY_ALIASES[head])
        elif head in {"command", "test"}:
            for token in ordered_tokens[1:]:
                if token in TOOL_FAMILY_ALIASES:
                    families.add(TOOL_FAMILY_ALIASES[token])

    for index, token in enumerate(ordered_tokens[:-1]):
        if token == "-m" and ordered_tokens[index + 1] == "pytest":
            families.add("pytest")
        if token == "-e" and ordered_tokens[0] == "tox":
            families.add("tox")

    if not families:
        return None

    categories: set[str] = set()
    lowered = clause.lower()
    if "command -v " in lowered or re.search(r"\btest -x\b", lowered):
        categories.add("presence")
    if "--version" in lowered or " -version" in lowered or "print(sys.version)" in lowered:
        categories.add("version")
    if any(marker in lowered for marker in ("pytest", "collect-only", " test", "verify", "testclasses")):
        categories.add("test")
    if any(marker in lowered for marker in ("build", "package", "compile", "install", "help", "effective-pom")):
        categories.add("build")
    if any(marker in lowered for marker in ("dependency:resolve", "dependency:go-offline", "npm ls", "cargo metadata", "pip check", "node_modules")):
        categories.add("deps")

    if not categories:
        categories.add("runtime")

    return ClauseFeature(
        clause=clause,
        families=frozenset(families),
        categories=frozenset(categories),
    )


def match_validation(validation: dict[str, Any], runtime_rows: list[RuntimeRow]) -> dict[str, Any]:
    candidate_sources = [
        value
        for value in (
            validation.get("command"),
            validation.get("declared_validation_command"),
        )
        if isinstance(value, str) and value.strip()
    ]

    candidate_clauses = {
        canonicalize_command(clause)
        for source in candidate_sources
        for clause in extract_clauses(source)
    }
    candidate_features = [
        feature
        for source in candidate_sources
        for clause in extract_clauses(source)
        if (feature := build_feature(clause))
    ]

    best_exact: RuntimeRow | None = None
    for row in runtime_rows:
        row_clauses = {canonicalize_command(clause) for clause in row.clauses}
        if candidate_clauses & row_clauses:
            best_exact = row
            break
    if best_exact is not None:
        return build_match_payload(best_exact, match_kind="exact")

    best_related: tuple[int, RuntimeRow, ClauseFeature, ClauseFeature] | None = None
    for candidate in candidate_features:
        for row in runtime_rows:
            for runtime_feature in row.features:
                common_families = candidate.families & runtime_feature.families
                if not common_families:
                    continue

                common_categories = candidate.categories & runtime_feature.categories
                if common_categories:
                    score = 100 + len(common_categories) * 10 + len(common_families)
                elif candidate.categories & {"presence", "version"}:
                    score = 50 + len(common_families)
                else:
                    continue

                result_bonus = 5 if row.result else 0
                if row.log_path:
                    result_bonus += 5
                candidate_tuple = (score + result_bonus, row, candidate, runtime_feature)
                if best_related is None or candidate_tuple[0] > best_related[0]:
                    best_related = candidate_tuple

    if best_related is not None:
        _, row, candidate_feature, runtime_feature = best_related
        return build_match_payload(
            row,
            match_kind="related",
            matched_families=sorted(candidate_feature.families & runtime_feature.families),
            validation_categories=sorted(candidate_feature.categories),
            runtime_categories=sorted(runtime_feature.categories),
        )

    return {
        "matched": False,
        "match_kind": None,
        "matched_families": [],
        "validation_categories": [],
        "runtime_categories": [],
        "workflow": None,
        "step": None,
        "ci_command": None,
        "result": None,
        "evidence": None,
        "log_path": None,
    }


def build_match_payload(
    row: RuntimeRow,
    *,
    match_kind: str,
    matched_families: list[str] | None = None,
    validation_categories: list[str] | None = None,
    runtime_categories: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "matched": True,
        "match_kind": match_kind,
        "matched_families": matched_families or [],
        "validation_categories": validation_categories or [],
        "runtime_categories": runtime_categories or [],
        "workflow": row.workflow or None,
        "step": row.step or None,
        "ci_command": row.command,
        "result": row.result or None,
        "evidence": row.evidence or None,
        "log_path": row.log_path,
    }


def resolve_log_path(artifact_dir: Path, evidence: str) -> str | None:
    if not evidence:
        return None
    match = LOG_REF_RE.match(evidence)
    if match is None:
        return None
    relative_path = match.group("path")
    if not relative_path or relative_path.endswith(":?"):
        return None
    absolute_path = artifact_dir / relative_path
    if absolute_path.is_file():
        return str(absolute_path)
    for candidate in artifact_dir.rglob(Path(relative_path).name):
        if str(candidate).endswith(relative_path):
            return str(candidate)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
