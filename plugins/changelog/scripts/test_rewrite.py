"""Tests for rewrite.py against temporary repositories."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

SCRIPT = Path(__file__).resolve().parent / "rewrite.py"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, env=ENV, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        (repo / name).write_text(text)
    git(repo, "add", *files)
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def run(repo: Path, *args: str) -> tuple[int, dict[str, object]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, json.loads(done.stdout)


def changes(draft: bool = False, two: bool = False) -> str:
    return (
        "# Changes\n"
        + ("- draft\n" if draft else "")
        + "\n" * 6
        + "## Old\n"
        + ("- two\n" if two else "")
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    commit(tmp_path, {"CHANGES.md": changes(), "code.py": "a\n"}, "base")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(tmp_path, "switch", "-q", "-c", "feat")
    return tmp_path


def test_partition_marks_pure_and_mixed(repo: Path) -> None:
    commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"CHANGES.md": changes(draft=True, two=True), "code.py": "b\n"}, "feat: two")
    code, result = run(repo, "partition", "--base", "origin/main", "--file", "CHANGES.md")
    assert code == 0
    commits = cast("list[dict[str, object]]", result["commits"])
    assert [c["pure"] for c in commits] == [True, False]


def test_drop_removes_pure_commit_and_keeps_code(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"code.py": "b\n"}, "feat: code")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft[:7])
    assert code == 0
    assert result["dropped"] == 1
    backup = str(result["backup"])
    assert backup.startswith("changelog-rewrite-backup-")
    assert git(repo, "rev-parse", backup) == result["backup_tip"]
    assert git(repo, "show", "HEAD:CHANGES.md") == changes().strip()
    assert git(repo, "show", "HEAD:code.py") == "b"
    assert git(repo, "log", "--format=%s", "origin/main..HEAD") == "feat: code"


def test_drop_leaves_mixed_commit_intact(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    files = {"CHANGES.md": changes(draft=True, two=True), "code.py": "b\n"}
    commit(repo, files, "feat: two")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 0, result
    assert result["mixed_remaining"] is True
    assert git(repo, "log", "--format=%s", "origin/main..HEAD") == "feat: two"


def test_drop_refuses_mixed_commit(repo: Path) -> None:
    mixed = commit(repo, {"CHANGES.md": changes(two=True), "code.py": "b\n"}, "feat: x")
    before = git(repo, "rev-parse", "HEAD")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", mixed)
    assert code == 1
    assert result["ok"] is False
    assert git(repo, "rev-parse", "HEAD") == before
    assert "changelog-rewrite-backup-" not in git(repo, "branch", "--list")


def test_drop_refuses_dirty_tree(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    (repo / "code.py").write_text("dirty\n")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1
    assert "uncommitted" in str(result["reason"])


def test_conflict_restores_the_backup(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    tip = commit(repo, {"CHANGES.md": changes(draft=True) + "- later\n"}, "docs: later")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1
    assert result["backup"]
    assert git(repo, "rev-parse", "HEAD") == tip
    assert git(repo, "status", "--porcelain") == ""
