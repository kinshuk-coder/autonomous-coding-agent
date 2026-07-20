from __future__ import annotations

import subprocess
from pathlib import Path

IGNORED_DIRECTORIES = {".git", ".agent", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _repository_files(repo: Path) -> list[str]:
    """Prefer Git's file list, but support a freshly initialized repository too."""
    tracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=False
    ).stdout.splitlines()
    if tracked:
        return tracked
    return sorted(
        path.relative_to(repo).as_posix()
        for path in repo.rglob("*")
        if path.is_file() and not any(part in IGNORED_DIRECTORIES for part in path.relative_to(repo).parts)
    )


def build_context(repo: Path, issue: str, max_files: int = 12) -> str:
    """Build a compact repository slice; avoid feeding the entire codebase to the model."""
    tree = _repository_files(repo)
    words = {w.lower() for w in issue.replace("/", " ").split() if len(w) > 3}
    ranked = sorted(tree, key=lambda name: -sum(w in name.lower() for w in words))[:max_files]
    snippets = []
    for relative in ranked:
        path = repo / relative
        if not path.is_file() or path.stat().st_size > 30_000:
            continue
        try:
            snippets.append(f"--- {relative} ---\n{path.read_text(encoding='utf-8')[:4_000]}")
        except UnicodeDecodeError:
            continue
    return f"ISSUE:\n{issue}\n\nREPOSITORY TREE:\n" + "\n".join(tree[:200]) + "\n\nRELEVANT FILES:\n" + "\n\n".join(snippets)
