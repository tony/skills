"""Smoke test: a rendered apply.sh creates a fixup on a temp repo."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import render_apply  # pyright: ignore[reportImplicitRelativeImport]

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
        ["git", *args],
        cwd=repo,
        env=ENV,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def run_sh(script: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(script)],
        cwd=repo,
        env=ENV,
        check=False,
        capture_output=True,
        text=True,
    )


def test_apply_creates_fixup_for_dotted_finding_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("robust line\nkeep\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "add a")
    target = git(repo, "rev-parse", "--short", "HEAD")
    base = git(repo, "rev-parse", "HEAD")

    registry = tmp_path / "signatures.yml"
    registry.write_text("version: 1\n")
    run_dir = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "deslop" / "t-1"
    run_dir.mkdir(parents=True)
    (run_dir / "0000-PLAN.md").write_text("plan\n")
    patch = run_dir / f"0001-fixup-{target}-ai-slop.flagship-phrases.patch"
    patch.write_text("--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n-robust line\n+line\n keep\n")

    rc = render_apply.main(
        [
            "--run-dir",
            str(run_dir),
            "--registry",
            str(registry),
            "--baseline",
            base,
            "--trunk-ref",
            "origin/main",
        ]
    )
    assert rc == 0
    script = run_dir / "apply.sh"
    assert "__REGISTRY" not in script.read_text()

    first = run_sh(script, repo)
    assert first.returncode == 0, first.stderr
    assert git(repo, "log", "-1", "--format=%s") == "fixup! add a"
    assert (repo / "a.txt").read_text() == "line\nkeep\n"
    assert git(repo, "status", "--porcelain") == ""

    again = run_sh(script, repo)
    assert again.returncode == 0, again.stderr
    assert git(repo, "rev-list", "--count", "HEAD") == "2"

    registry.write_text("version: 2\n")
    locked = run_sh(script, repo)
    assert locked.returncode == 1


def test_render_rejects_unsafe_value() -> None:
    try:
        render_apply.render("x", 'a"b', "h", "b", "t")
    except ValueError:
        return
    raise AssertionError
