from __future__ import annotations

import re
import subprocess
from pathlib import Path


class UnsafePatch(ValueError):
    pass


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def normalize_patch(patch: str) -> str:
    """Repair model-generated hunk counts without altering paths or changed content."""
    if patch and not patch.endswith(("\n", "\r")):
        patch += "\n"
    lines = patch.splitlines(keepends=True)
    normalized: list[str] = []
    index = 0
    while index < len(lines):
        match = HUNK.match(lines[index].rstrip("\r\n"))
        if not match:
            normalized.append(lines[index])
            index += 1
            continue
        header_index = index
        index += 1
        body: list[str] = []
        while index < len(lines) and not HUNK.match(lines[index].rstrip("\r\n")) and not lines[index].startswith(("--- ", "diff --git ")):
            body.append(lines[index])
            index += 1
        old_count = sum(line.startswith(("-", " ")) for line in body)
        new_count = sum(line.startswith(("+", " ")) for line in body)
        old_start, new_start, suffix = match.group(1), match.group(3), match.group(5)
        old_range = f"{old_start},{old_count}" if old_count != 1 else old_start
        new_range = f"{new_start},{new_count}" if new_count != 1 else new_start
        ending = "\r\n" if lines[header_index].endswith("\r\n") else "\n"
        normalized.append(f"@@ -{old_range} +{new_range} @@{suffix}{ending}")
        normalized.extend(body)
    return "".join(normalized)


def _targets(patch: str) -> list[str]:
    targets: list[str] = []
    for raw_path in re.findall(r"^\+\+\+ (.+?)(?:\t.*)?$", patch, flags=re.MULTILINE):
        if raw_path != "/dev/null":
            targets.append(raw_path[2:] if raw_path.startswith("b/") else raw_path)
    return targets


def validate_patch(patch: str, repo: Path) -> None:
    if not patch.startswith(("diff --git ", "--- ")):
        raise UnsafePatch("Agent response was not a unified diff")
    paths = _targets(patch)
    if not paths:
        raise UnsafePatch("Patch contains no target files")
    root = repo.resolve()
    for path in paths:
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root) or ".git" in candidate.parts:
            raise UnsafePatch(f"Patch targets unsafe path: {path}")


def apply_patch(patch: str, repo: Path, check_only: bool = False) -> None:
    """Apply a validated patch without requiring the disposable copy to be a Git repo."""
    patch = normalize_patch(patch)
    validate_patch(patch, repo)
    git_style = patch.startswith("diff --git ")
    command = ["git", "-C", str(repo), "apply", "--no-index", "-p1" if git_style else "-p0"]
    if check_only:
        command.append("--check")
    result = subprocess.run(command, input=patch, text=True, capture_output=True, check=False)
    if result.returncode:
        raise UnsafePatch(result.stderr.strip() or "git apply rejected patch")
