from pathlib import Path
import pytest
from coding_agent.patches import UnsafePatch, apply_patch, validate_patch

def test_rejects_non_diff(tmp_path: Path) -> None:
    with pytest.raises(UnsafePatch, match="unified diff"): validate_patch("hello", tmp_path)
def test_rejects_path_escape(tmp_path: Path) -> None:
    patch = "--- /dev/null\n+++ ../../outside\n@@ -0,0 +1 @@\n+x\n"
    with pytest.raises(UnsafePatch, match="unsafe path"): validate_patch(patch, tmp_path)
def test_accepts_git_style_patch(tmp_path: Path) -> None:
    validate_patch("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n", tmp_path)
def test_applies_standard_new_file_patch(tmp_path: Path) -> None:
    patch = "--- /dev/null\n+++ utils/email.py\n@@ -0,0 +1 @@\n+value = 1\n"
    apply_patch(patch, tmp_path)
    assert (tmp_path / "utils" / "email.py").read_text() == "value = 1\n"
