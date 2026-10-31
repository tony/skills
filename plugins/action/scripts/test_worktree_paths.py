"""Tests for worktree_paths.py against throwaway repositories."""

# ruff: noqa: PLR2004, S108, S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false
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


@pytest.mark.integration(reason="executes the worktree-path CLI")
def test_slug_truncates_at_word_boundary(tmp_path: Path) -> None:
    title = tmp_path / "t.txt"
    title.write_text("Handle the extremely long webhook retry timeout configuration case\n")
    done = run(tmp_path, "slug", "--file", str(title), "--prefix", "tea-123")
    name = done.stdout.strip()
    assert done.returncode == 0
    assert len(name) <= 60
    assert name == "tea-123-handle-the-extremely-long-webhook-retry-timeout"


@pytest.mark.integration(reason="executes the worktree-path CLI")
def test_slug_hostile_title_is_inert(tmp_path: Path) -> None:
    title = tmp_path / "t.txt"
    title.write_text("$(touch pwned); `id` Fix\n")
    done = run(tmp_path, "slug", "--file", str(title))
    assert done.stdout.strip() == "touch-pwned-id-fix"
    assert not (tmp_path / "pwned").exists()


def test_slug_long_single_word() -> None:
    assert len(wp.branch_name("x" * 100, "tea-1")) == 60


@pytest.mark.integration(reason="compares against the native cksum CLI")
@pytest.mark.parametrize("data", [b"", b"a", b"123456789", b"/home/user/work/shop"])
def test_cksum_matches_system(data: bytes) -> None:
    out = subprocess.run(["cksum"], input=data, capture_output=True, check=True)
    assert wp.posix_cksum(data) == int(out.stdout.split()[0])


@pytest.mark.integration(reason="uses owned Git worktrees and the worktree-path CLI")
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


@pytest.mark.integration(reason="uses an owned Git repository and the worktree-path CLI")
def test_path_temp(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "shop")
    done = run(repo, "path", "--branch", "a/b", "--temp", env={**ENV, "TMPDIR": "/var/tmp/x/"})
    digest = wp.posix_cksum(str(repo).encode())
    assert done.stdout.strip() == f"/var/tmp/x/action-worktrees/shop-{digest}/a-b"


@pytest.mark.integration(reason="uses an owned Git repository and the worktree-path CLI")
def test_guard_refuses_repo_at_or_above_home(tmp_path: Path) -> None:
    real_home = tmp_path / "real" / "home"
    repo = make_repo(real_home)
    link = tmp_path / "link"
    link.symlink_to(real_home)
    done = run(repo, "guard", env={**ENV, "HOME": str(link)})
    assert done.returncode == wp.REFUSED
    assert done.stdout.startswith("refuse:")


@pytest.mark.integration(reason="uses an owned Git repository and the worktree-path CLI")
def test_guard_refuses_repo_above_home(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "dots")
    (repo / "u").mkdir()
    done = run(repo, "guard", env={**ENV, "HOME": str(repo / "u")})
    assert done.returncode == wp.REFUSED


@pytest.mark.integration(reason="uses an owned Git repository and the worktree-path CLI")
def test_guard_allows_project_under_home(tmp_path: Path) -> None:
    (tmp_path / "home").mkdir()
    repo = make_repo(tmp_path / "home" / "app")
    done = run(repo, "guard", env={**ENV, "HOME": str(tmp_path / "home")})
    assert done.returncode == 0
    assert done.stdout == ""


@pytest.mark.integration(
    reason="executes the worktree-path CLI and native Git outside a repository"
)
def test_guard_outside_repo_exits_1(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    done = run(
        tmp_path / "plain",
        "guard",
        env={**ENV, "GIT_CEILING_DIRECTORIES": str(tmp_path)},
    )
    assert done.returncode == 1
    assert "not a git repository" in done.stderr


@pytest.mark.parametrize(
    "name",
    ["feat/a$(id)b", "x`id`", "a;b", "a b", "-rf", "../x", "a..b"],
)
def test_check_refuses_unsafe_names(tmp_path: Path, name: str) -> None:
    f = tmp_path / "name"
    f.write_text(name)
    assert wp.main(["check", "--file", str(f)]) == wp.REFUSED


def test_check_prints_safe_name(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "name"
    f.write_text("tea-123/fix-login\n")
    assert wp.main(["check", "--file", str(f)]) == 0
    assert capsys.readouterr().out.strip() == "tea-123/fix-login"


def test_slug_non_ascii_title_is_not_empty(tmp_path: Path) -> None:
    name = wp.branch_name("日本語の目標")
    assert name.startswith("goal-")
    f = tmp_path / "name"
    f.write_text(name)
    assert wp.main(["check", "--file", str(f)]) == 0
