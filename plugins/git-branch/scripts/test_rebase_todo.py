"""Tests for rebase-todo.sh against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001, D103

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration(reason="uses owned Git repositories and the rebase shell CLI")

SCRIPT = Path(__file__).with_name("rebase-todo.sh")
REFUSED = 2

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


def toolkit(
    repo: Path, *args: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SCRIPT), *args],
        cwd=repo,
        env={**ENV, **(extra_env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def commit(repo: Path, name: str, message: str | None = None) -> None:
    (repo / name).write_text(f"{name}\n")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message or f"add {name}")


def make_repo(tmp_path: Path, files: tuple[str, ...] = ("one", "two", "three")) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base")
    base = git(repo, "rev-parse", "HEAD")
    for name in files:
        commit(repo, name)
    return repo, base


def subjects(repo: Path, base: str) -> list[str]:
    return git(repo, "log", "--reverse", "--format=%s", f"{base}..HEAD").splitlines()


def test_status_clean_and_in_progress(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    assert toolkit(repo, "status").stdout.startswith("clean")
    (repo / ".git" / "MERGE_HEAD").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    assert toolkit(repo, "status").stdout == "in progress: MERGE_HEAD\n"


def test_show_lists_picks_oldest_first(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    lines = toolkit(repo, "show", base).stdout.splitlines()
    assert [ln.split(" ", 2)[2] for ln in lines] == ["add one", "add two", "add three"]
    assert all(ln.startswith("pick ") for ln in lines)


def test_show_rejects_bad_base(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    assert toolkit(repo, "show", "no-such-ref").returncode == REFUSED


def test_apply_reorders_and_drops_via_plan(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    picks = toolkit(repo, "show", base).stdout.splitlines()
    plan = tmp_path / "plan with 'quote.txt"
    plan.write_text("\n".join([picks[2], picks[0], picks[1]]) + "\n")
    done = toolkit(repo, "apply", base, str(plan))
    assert done.returncode == 0, done.stderr
    assert subjects(repo, base) == ["add three", "add one", "add two"]


def test_verify_passes_and_keeps_tip(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    tip = git(repo, "rev-parse", "HEAD")
    done = toolkit(repo, "verify", base, "true")
    assert done.returncode == 0, done.stderr
    assert git(repo, "rev-parse", "HEAD") == tip


def test_verify_failure_leaves_rebase_and_prints_abort(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    done = toolkit(repo, "verify", base, "test ! -e two")
    assert done.returncode == 1
    assert "git rebase --abort" in done.stderr
    assert toolkit(repo, "status").stdout.startswith("in progress")
    git(repo, "rebase", "--abort")
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_squash_folds_fixup(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path, ("one", "two"))
    (repo / "one").write_text("changed\n")
    git(repo, "commit", "-q", "-a", "--fixup", git(repo, "rev-parse", "HEAD~1"))
    done = toolkit(repo, "squash", base)
    assert done.returncode == 0, done.stderr
    assert subjects(repo, base) == ["add one", "add two"]
    assert (repo / "one").read_text() == "changed\n"


def test_preflight_refuses_dirty_tree(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "one").write_text("dirty\n")
    for args in (("verify", base, "true"), ("squash", base)):
        done = toolkit(repo, *args)
        assert done.returncode == REFUSED
        assert "uncommitted" in done.stderr


def test_preflight_refuses_operation_in_progress(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / ".git" / "rebase-merge").mkdir()
    done = toolkit(repo, "squash", base)
    assert done.returncode == REFUSED
    assert "rebase-merge" in done.stderr


def test_preflight_refuses_empty_repository(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    done = toolkit(repo, "verify", "HEAD", "true")
    assert done.returncode == REFUSED
    assert "no commits" in done.stderr


def test_usage_errors_exit_two(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    assert toolkit(repo).returncode == REFUSED
    assert toolkit(repo, "apply", "HEAD").returncode == REFUSED
    assert toolkit(repo, "apply", "HEAD", str(tmp_path / "missing")).returncode == REFUSED


def test_update_refs_moves_stacked_branch(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path, ("one", "two"))
    git(repo, "branch", "stack", "HEAD~1")
    old = git(repo, "rev-parse", "stack")
    picks = toolkit(repo, "show", base).stdout.splitlines()
    plan = tmp_path / "plan.txt"
    plan.write_text(f"{picks[1]}\nupdate-ref refs/heads/stack\n{picks[0]}\n")
    done = toolkit(repo, "apply", base, str(plan), extra_env={"RECUT_UPDATE_REFS": "1"})
    assert done.returncode == 0, done.stderr
    assert git(repo, "rev-parse", "stack") != old
    assert git(repo, "log", "-1", "--format=%s", "stack") == "add two"
