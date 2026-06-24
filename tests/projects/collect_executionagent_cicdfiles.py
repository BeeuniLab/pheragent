#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DIRECTORY_TARGETS = (
    ".github/workflows",
    ".circleci",
    ".buildkite",
    ".gitlab-ci",
)

FILE_TARGET_GLOBS = (
    ".gitlab-ci.yml",
    ".gitlab-ci.yaml",
    ".travis.yml",
    ".appveyor.yml",
    ".drone.yml",
    ".drone.yaml",
    ".woodpecker.yml",
    ".woodpecker.yaml",
    "Jenkinsfile",
    "Jenkinsfile.*",
    "azure-pipelines.yml",
    "azure-pipelines.yaml",
    "azure-pipeline.yml",
    "azure-pipeline.yaml",
    "bitrise.yml",
    "bitrise.yaml",
    "buildspec.yml",
    "buildspec.yaml",
)


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    owner_repo: str
    commit: str
    checkout_dir_name: str

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.owner_repo}.git"

    @property
    def repo_name(self) -> str:
        return self.owner_repo.rsplit("/", 1)[-1]

    @property
    def owner_repo_dir(self) -> str:
        return self.owner_repo.replace("/", "__")


def slugify(value: str) -> str:
    chars: list[str] = []
    for char in value:
        if char.isalnum():
            chars.append(char.lower())
        else:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "project"


def parse_projects_file(path: Path) -> list[ProjectSpec]:
    raw: list[tuple[str, str]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            raise ValueError(f"invalid line {line_no}: expected 'owner/repo commit'")
        owner_repo, commit = parts[0], parts[1]
        if "/" not in owner_repo:
            raise ValueError(f"invalid line {line_no}: repository must be owner/repo")
        raw.append((owner_repo, commit))

    repo_name_counts = Counter(owner_repo.rsplit("/", 1)[-1] for owner_repo, _ in raw)
    specs: list[ProjectSpec] = []
    used_dir_names: set[str] = set()
    for owner_repo, commit in raw:
        repo_name = owner_repo.rsplit("/", 1)[-1]
        base_name = repo_name if repo_name_counts[repo_name] == 1 else slugify(owner_repo)
        dir_name = base_name
        suffix = 2
        while dir_name in used_dir_names:
            dir_name = f"{base_name}-{suffix}"
            suffix += 1
        used_dir_names.add(dir_name)
        specs.append(ProjectSpec(owner_repo=owner_repo, commit=commit, checkout_dir_name=dir_name))
    return specs


def run_git(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def ensure_repo(spec: ProjectSpec, repo_cache_dir: Path) -> Path:
    repo_path = repo_cache_dir / spec.checkout_dir_name
    if not repo_path.exists():
        result = run_git(
            [
                "git",
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                spec.repo_url,
                str(repo_path),
            ]
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"clone failed for {spec.owner_repo}: {result.stderr.strip() or result.stdout.strip()}"
            )
    elif not (repo_path / ".git").exists():
        raise RuntimeError(f"path exists but is not a git repository: {repo_path}")
    else:
        result = run_git(["git", "remote", "set-url", "origin", spec.repo_url], cwd=repo_path)
        if result.returncode != 0:
            raise RuntimeError(
                f"failed to update remote for {spec.owner_repo}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
    return repo_path


def looks_like_short_sha(value: str) -> bool:
    return 4 <= len(value) < 40 and all(char in "0123456789abcdefABCDEF" for char in value)


def fetch_checkout_ref(spec: ProjectSpec, repo_path: Path) -> str:
    result = run_git(["git", "fetch", "--depth", "1", "origin", spec.commit], cwd=repo_path)
    if result.returncode == 0:
        return spec.commit

    result = run_git(["git", "fetch", "origin", spec.commit], cwd=repo_path)
    if result.returncode == 0:
        return spec.commit

    if looks_like_short_sha(spec.commit):
        refs_result = run_git(
            [
                "git",
                "fetch",
                "--filter=blob:none",
                "origin",
                "+refs/heads/*:refs/remotes/origin/*",
                "+refs/tags/*:refs/tags/*",
            ],
            cwd=repo_path,
        )
        if refs_result.returncode == 0:
            resolve_result = run_git(
                ["git", "rev-parse", "--verify", "--quiet", f"{spec.commit}^{{commit}}"],
                cwd=repo_path,
            )
            if resolve_result.returncode == 0 and resolve_result.stdout.strip():
                return resolve_result.stdout.strip().splitlines()[0]

    fallback = run_git(["git", "fetch", "--depth", "1", "origin", "HEAD"], cwd=repo_path)
    if fallback.returncode == 0:
        return "FETCH_HEAD"

    raise RuntimeError(
        f"failed to fetch {spec.owner_repo}@{spec.commit}: "
        f"{result.stderr.strip() or result.stdout.strip()}"
    )


def checkout_ref(repo_path: Path, ref: str) -> str:
    result = run_git(["git", "checkout", "--detach", ref], cwd=repo_path)
    if result.returncode != 0:
        raise RuntimeError(f"checkout failed for {repo_path.name}@{ref}: {result.stderr.strip()}")
    head = run_git(["git", "rev-parse", "--verify", "HEAD"], cwd=repo_path)
    if head.returncode != 0 or not head.stdout.strip():
        raise RuntimeError(f"failed to resolve HEAD for {repo_path}")
    return head.stdout.strip().splitlines()[0]


def iter_target_paths(repo_path: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for relative in DIRECTORY_TARGETS:
        candidate = repo_path / relative
        if candidate.exists():
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate
    for pattern in FILE_TARGET_GLOBS:
        for candidate in repo_path.glob(pattern):
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield candidate


def reset_destination(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy_targets(repo_path: Path, destination_root: Path) -> list[str]:
    copied: list[str] = []
    for source in sorted(iter_target_paths(repo_path), key=lambda item: item.as_posix()):
        relative = source.relative_to(repo_path)
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            reset_destination(destination)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copied.append(relative.as_posix())
    return copied


def collect_one(spec: ProjectSpec, repo_cache_dir: Path, output_root: Path) -> dict[str, object]:
    repo_path = ensure_repo(spec, repo_cache_dir)
    ref = fetch_checkout_ref(spec, repo_path)
    actual_commit = checkout_ref(repo_path, ref)
    destination = output_root / spec.checkout_dir_name / spec.owner_repo_dir
    destination.mkdir(parents=True, exist_ok=True)
    copied = copy_targets(repo_path, destination)
    metadata = {
        "owner_repo": spec.owner_repo,
        "requested_commit": spec.commit,
        "actual_commit": actual_commit,
        "repo_cache_path": str(repo_path),
        "output_path": str(destination),
        "copied_paths": copied,
        "copied_count": len(copied),
    }
    (destination / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return metadata


def main(argv: list[str]) -> int:
    input_path = (
        Path(argv[1]).expanduser().resolve()
        if len(argv) > 1
        else Path("/home/lix/EnvAgent/love/lix_pheragent/tests/projects/executionAgent.txt")
    )
    base_dir = Path.cwd()
    output_root = base_dir / "cicdfiles"
    repo_cache_dir = base_dir / ".executionagent_repo_cache"
    jobs = int(argv[2]) if len(argv) > 2 else 4

    specs = parse_projects_file(input_path)
    output_root.mkdir(parents=True, exist_ok=True)
    repo_cache_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        future_to_spec = {
            executor.submit(collect_one, spec, repo_cache_dir, output_root): spec for spec in specs
        }
        for future in as_completed(future_to_spec):
            spec = future_to_spec[future]
            try:
                result = future.result()
                results.append(result)
                print(
                    f"[ok] {spec.owner_repo} {result['actual_commit']} copied={result['copied_count']}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "owner_repo": spec.owner_repo,
                        "requested_commit": spec.commit,
                        "error": str(exc),
                    }
                )
                print(f"[fail] {spec.owner_repo} {spec.commit}: {exc}", file=sys.stderr, flush=True)

    results.sort(key=lambda item: str(item["owner_repo"]))
    failures.sort(key=lambda item: item["owner_repo"])
    summary = {
        "input_file": str(input_path),
        "output_root": str(output_root),
        "repo_cache_dir": str(repo_cache_dir),
        "project_count": len(specs),
        "success_count": len(results),
        "failure_count": len(failures),
        "results": results,
        "failures": failures,
    }
    summary_path = base_dir / "cicdfiles_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"[done] summary -> {summary_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
