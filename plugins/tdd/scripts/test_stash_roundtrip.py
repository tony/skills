"""Tests for stash_roundtrip.py using an owned repository and linked worktree."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "stash_roundtrip.py"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True, check=True
    )
    return done.stdout


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def shas(cwd: Path) -> list[str]:
    return [line.split()[0] for line in git(cwd, "stash", "list", "--format=%H %gs").splitlines()]


@pytest.fixture
def trees(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    (main / "a.py").write_text("x = 1\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "init")
    peer = tmp_path / "peer"
    git(main, "worktree", "add", "-q", "-b", "peer", str(peer))
    return main, peer


@pytest.mark.integration(reason="uses an owned Git repository and linked worktree")
def test_restore_ignores_peer_stash_pushed_in_between(trees: tuple[Path, Path]) -> None:
    main, peer = trees
    (main / "a.py").write_text("x = 2\n")
    (main / "new.py").write_text("n = 1\n")
    pushed = run(main, "push")
    assert pushed.returncode == 0
    mine = pushed.stdout.strip()
    assert (main / "a.py").read_text() == "x = 1\n"

    (peer / "a.py").write_text("x = 99\n")
    git(peer, "stash", "push", "--message", "peer work")
    theirs = shas(peer)[0]
    assert theirs != mine

    restored = run(main, "restore", mine)
    assert restored.returncode == 0
    assert (main / "a.py").read_text() == "x = 2\n"
    assert (main / "new.py").read_text() == "n = 1\n"
    assert shas(main) == [theirs]
    assert (peer / "a.py").read_text() == "x = 1\n"


@pytest.mark.integration(reason="uses an owned Git repository")
def test_push_without_changes_creates_nothing(trees: tuple[Path, Path]) -> None:
    main, _ = trees
    pushed = run(main, "push")
    assert pushed.returncode == 1
    assert pushed.stdout == ""
    assert shas(main) == []


@pytest.mark.integration(reason="uses an owned Git repository")
def test_failed_apply_and_unknown_sha_keep_every_entry(trees: tuple[Path, Path]) -> None:
    main, _ = trees
    (main / "a.py").write_text("x = 2\n")
    mine = run(main, "push").stdout.strip()
    (main / "a.py").write_text("x = 3\n")
    conflict = run(main, "restore", mine)
    assert conflict.returncode == 1
    assert shas(main) == [mine]
    assert (main / "a.py").read_text() == "x = 3\n"
    unknown = run(main, "restore", "0" * 40)
    assert unknown.returncode != 0
    assert shas(main) == [mine]
