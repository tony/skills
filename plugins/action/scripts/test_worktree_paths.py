"""Tests for worktree_paths.py against throwaway repositories."""

# ruff: noqa: PLR2004, S108, S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("worktree_paths.py")
sys.path.insert(0, str(SCRIPT.parent))
import worktree_paths as wp  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def run(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env or ENV,
        capture_output=True,
        text=True,
        check=False,
    )


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, env=ENV, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=path,
        env=ENV,
        check=True,
    )
    return path


def test_slug_truncates_at_word_boundary(tmp_path: Path) -> None:
    title = tmp_path / "t.txt"
    title.write_text("Handle the extremely long webhook retry timeout configuration case\n")
    done = run(tmp_path, "slug", "--file", str(title), "--prefix", "tea-123")
    name = done.stdout.strip()
    assert done.returncode == 0
    assert len(name) <= 60
    assert name == "tea-123-handle-the-extremely-long-webhook-retry-timeout"


def test_slug_hostile_title_is_inert(tmp_path: Path) -> None:
    title = tmp_path / "t.txt"
    title.write_text("$(touch pwned); `id` Fix\n")
    done = run(tmp_path, "slug", "--file", str(title))
    assert done.stdout.strip() == "touch-pwned-id-fix"
    assert not (tmp_path / "pwned").exists()


def test_slug_long_single_word() -> None:
    assert len(wp.branch_name("x" * 100, "tea-1")) == 60


@pytest.mark.parametrize("data", [b"", b"a", b"123456789", b"/home/user/work/shop"])
def test_cksum_matches_system(data: bytes) -> None:
    out = subprocess.run(["cksum"], input=data, capture_output=True, check=True)
    assert wp.posix_cksum(data) == int(out.stdout.split()[0])


def test_path_local_from_linked_worktree(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "shop")
    linked = tmp_path / "shop-other"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "other", str(linked)],
        cwd=repo,
        env=ENV,
        check=True,
    )
    done = run(linked, "path", "--branch", "feat/tea-1-login")
    assert done.stdout.strip() == f"{repo}-feat-tea-1-login"


def test_path_temp(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "shop")
    done = run(repo, "path", "--branch", "a/b", "--temp", env={**ENV, "TMPDIR": "/var/tmp/x/"})
    digest = wp.posix_cksum(str(repo).encode())
    assert done.stdout.strip() == f"/var/tmp/x/action-worktrees/shop-{digest}/a-b"


def test_guard_refuses_repo_at_or_above_home(tmp_path: Path) -> None:
    real_home = tmp_path / "real" / "home"
    repo = make_repo(real_home)
    link = tmp_path / "link"
    link.symlink_to(real_home)
    done = run(repo, "guard", env={**ENV, "HOME": str(link)})
    assert done.returncode == wp.REFUSED
    assert done.stdout.startswith("refuse:")


def test_guard_refuses_repo_above_home(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "dots")
    (repo / "u").mkdir()
    done = run(repo, "guard", env={**ENV, "HOME": str(repo / "u")})
    assert done.returncode == wp.REFUSED


def test_guard_allows_project_under_home(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    repo = make_repo(tmp_path / "home" / "app")
    done = run(repo, "guard", env={**ENV, "HOME": str(tmp_path / "home")})
    assert done.returncode == 0
    assert done.stdout == ""
