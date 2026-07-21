from __future__ import annotations

import subprocess
from pathlib import Path

IGNORED_DIRECTORIES = {".git", ".agent", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _repository_files(repo: Path) -> list[str]:
    """Prefer Git's file list, but support a freshly initialized repository too."""
    tracked = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=False).stdout.splitlines()
    if tracked:
        return tracked
    return sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file() and not any(part in IGNORED_DIRECTORIES for part in path.relative_to(repo).parts))


def _relevance(repo: Path, relative: str, words: set[str]) -> int:
    score = 5 * sum(word in relative.lower() for word in words)
    path = repo / relative
    if not path.is_file() or path.stat().st_size > 30_000:
        return score
    try:
        content = path.read_text(encoding="utf-8").lower()
    except UnicodeDecodeError:
        return score
    return score + 20 * sum(content.count(word) for word in words)


def build_context(repo: Path, issue: str, max_files: int = 12, max_context_chars: int = 8_000) -> str:
    """Build a compact, content-relevant context slice within a strict token budget."""
    tree = _repository_files(repo)
    words = {word.lower() for word in issue.replace("/", " ").split() if len(word) > 3}
    ranked = sorted(tree, key=lambda name: (-_relevance(repo, name, words), name))[:max_files]
    tree_text = "\n".join(tree[:100])
    prefix = f"ISSUE:\n{issue}\n\nREPOSITORY TREE:\n{tree_text}\n\nRELEVANT FILES:\n"[:max_context_chars]
    remaining = max(0, max_context_chars - len(prefix))
    snippets: list[str] = []
    for relative in ranked:
        if remaining <= 0:
            break
        path = repo / relative
        if not path.is_file() or path.stat().st_size > 30_000:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        snippet = f"--- {relative} ---\n{content[:max(0, remaining - len(relative) - 10)]}\n"
        snippets.append(snippet[:remaining])
        remaining -= len(snippets[-1])
    return (prefix + "\n".join(snippets))[:max_context_chars]
