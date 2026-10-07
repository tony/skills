"""Autosquash runner: completes over apply.sh output, aborts cleanly on a conflict."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import render_apply  # pyright: ignore[reportImplicitRelativeImport]

SCRIPT = Path(__file__).resolve().parent / "autosquash.py"
EXIT_CONFLICT = 10
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_EDITOR": "true",
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, env=ENV, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def autosquash(repo: Path, base: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--baseline", base, *extra],
        cwd=repo,
        env=ENV,
        check=False,
        capture_output=True,
        text=True,
    )


def make_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "seed.txt").write_text("seed\n")
    git(repo, "add", "seed.txt")
    git(repo, "commit", "-q", "-m", "seed")
    return repo, git(repo, "rev-parse", "HEAD")


def test_apply_then_autosquash_folds_the_fixup(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "a.txt").write_text("robust line\nkeep\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "add a")
    target = git(repo, "rev-parse", "--short", "HEAD")
    (repo / "b.txt").write_text("b\n")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "add b")

    registry = tmp_path / "signatures.yml"
    registry.write_text("version: 1\n")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    patch = run_dir / f"0001-fixup-{target}-x.y.patch"
    patch.write_text("--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n-robust line\n+line\n keep\n")
    argv = ["--run-dir", str(run_dir), "--registry", str(registry)]
    assert render_apply.main([*argv, "--baseline", base, "--trunk-ref", "origin/main"]) == 0
    applied = subprocess.run(
        ["sh", str(run_dir / "apply.sh")], cwd=repo, env=ENV, check=False, capture_output=True
    )
    assert applied.returncode == 0, applied.stderr
    assert git(repo, "rev-list", "--count", f"{base}..HEAD") == "3"

    done = autosquash(repo, base)
    assert done.returncode == 0, done.stderr
    assert git(repo, "log", "--format=%s", f"{base}..HEAD").split("\n") == ["add b", "add a"]
    assert (repo / "a.txt").read_text() == "line\nkeep\n"
    assert git(repo, "status", "--porcelain") == ""


def test_conflict_pauses_then_aborts_to_the_original_tip(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "a.txt").write_text("one\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "add a")
    (repo / "a.txt").write_text("two\n")
    git(repo, "commit", "-q", "-am", "edit a")
    (repo / "a.txt").write_text("uno\n")
    git(repo, "commit", "-q", "-a", "--fixup", "HEAD~1")
    tip = git(repo, "rev-parse", "HEAD")

    paused = autosquash(repo, base)
    assert paused.returncode == EXIT_CONFLICT, paused.stderr
    assert "a.txt" in paused.stdout
    assert git(repo, "diff", "--name-only", "--diff-filter=U") == "a.txt"
    git(repo, "rebase", "--abort")
    assert git(repo, "rev-parse", "HEAD") == tip

    aborted = autosquash(repo, base, "--abort-on-conflict")
    assert aborted.returncode == EXIT_CONFLICT
    assert "aborted" in aborted.stdout
    assert git(repo, "rev-parse", "HEAD") == tip
    assert git(repo, "status", "--porcelain") == ""
    assert not (repo / git(repo, "rev-parse", "--git-path", "rebase-merge")).exists()
