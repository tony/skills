"""Tests for jira_text.py."""

# ruff: noqa: S101, S603, INP001, D103, PLR2004
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("jira_text.py")


def run(tmp_path: Path, text: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "body.md").write_text(text)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "body.md")],
        capture_output=True,
        text=True,
        check=False,
    )


def test_converts_every_rule(tmp_path: Path) -> None:
    text = (
        "### Summary\n\nThe **export** drops a row, see [log](https://x.io/l).\n\n"
        "```\nKeyError: tenant_id\n```\n\n"
        "<details>\n<summary>Versions</summary>\n\nwidgets 2.4.1\n\n</details>\n"
    )
    result = run(tmp_path, text)
    assert result.returncode == 0
    assert result.stdout == (
        "Summary\n\nThe export drops a row, see log (https://x.io/l).\n\n"
        "    KeyError: tenant_id\n\nVersions\n\nwidgets 2.4.1\n"
    )


def test_list_markers_stay(tmp_path: Path) -> None:
    result = run(tmp_path, "- one\n- two\n\n1. a\n2. b\n")
    assert result.stdout == "- one\n- two\n\n1. a\n2. b\n"


def test_table_and_nested_list_are_refused(tmp_path: Path) -> None:
    for text in ("| a | b |\n|---|---|\n| 1 | 2 |\n", "- a\n  - b\n", "![s](u.png)\n"):
        result = run(tmp_path, text)
        assert result.returncode == 1
        assert "drop or flatten" in result.stdout


def test_table_inside_fence_is_kept(tmp_path: Path) -> None:
    assert run(tmp_path, "```\n| a | b |\n```\n").returncode == 0


def test_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
