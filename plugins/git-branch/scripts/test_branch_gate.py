"""Tests for branch_gate.py against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration(reason="uses owned Git repositories")

SCRIPT = Path(__file__).with_name("branch_gate.py")
REFUSED = 2
RUNS = 3

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**ENV, **(env or {})},
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def gate(repo: Path, *args: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**ENV, "HOME": str(home or repo.parent / "fakehome")}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def commit(repo: Path, name: str, text: str | None = None) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text is not None else f"{name}\n")
    git(repo, "add", "--", name)
    git(repo, "commit", "-q", "-m", f"add {name}")


def make_repo(tmp_path: Path) -> Path:
    """Build a repo on `feature/x` with two commits beyond `main`."""
    repo = tmp_path / "work" / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base")
    git(repo, "checkout", "-q", "-b", "feature/x")
    commit(repo, "one")
    commit(repo, "two")
    return repo


def codes(done: subprocess.CompletedProcess[str], kind: str = "refuse") -> list[str]:
    return re.findall(rf"^{kind} ([a-z-]+):", done.stdout, flags=re.MULTILINE)


def test_preflight_clean_passes(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    done = gate(repo, "preflight", "feature/x")
    assert done.returncode == 0, done.stdout
    assert done.stdout == ""


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("dirty", "dirty"),
        ("untracked", "dirty"),
        ("merge", "merge-commit"),
        ("progress", "in-progress"),
        ("other-branch", "not-checked-out"),
        ("empty", "empty-range"),
    ],
)
def test_preflight_refuses(tmp_path: Path, setup: str, code: str) -> None:
    repo = make_repo(tmp_path)
    if setup == "dirty":
        (repo / "one").write_text("edit\n")
    elif setup == "untracked":
        (repo / "stray").write_text("x\n")
    elif setup == "merge":
        git(repo, "checkout", "-q", "-b", "side", "main")
        commit(repo, "side")
        git(repo, "checkout", "-q", "feature/x")
        git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    elif setup == "progress":
        (repo / ".git" / "MERGE_HEAD").write_text(git(repo, "rev-parse", "HEAD") + "\n")
    elif setup == "other-branch":
        git(repo, "checkout", "-q", "main")
    elif setup == "empty":
        git(repo, "reset", "-q", "--hard", "main")
    done = gate(repo, "preflight", "feature/x")
    assert done.returncode == REFUSED
    assert code in codes(done)
    if setup == "other-branch":
        assert codes(done) == ["not-checked-out"]


def test_preflight_refuses_other_worktree_holder(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "main")
    git(repo, "worktree", "add", "-q", str(tmp_path / "wt"), "feature/x")
    assert {"worktree", "not-checked-out"} <= set(codes(gate(repo, "preflight", "feature/x")))


def test_preflight_refuses_unborn_and_home(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-q", "-b", "main")
    assert codes(gate(empty, "preflight", "main")) == ["unborn"]
    repo = make_repo(tmp_path)
    done = gate(repo, "preflight", "feature/x", home=repo)
    assert "home" in codes(done)


def test_preflight_refuses_shallow_clone(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    clone = tmp_path / "clone"
    git(
        tmp_path,
        "clone",
        "-q",
        "--depth",
        "1",
        "--branch",
        "feature/x",
        f"file://{repo}",
        str(clone),
    )
    assert "shallow" in codes(gate(clone, "preflight", "feature/x"))


def test_preflight_redo_mode(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "one").write_text("edit\n")
    done = gate(repo, "preflight", "feature/x", "--mode", "redo")
    assert done.returncode == 0
    assert codes(done, "note") == ["dirty"]
    git(repo, "checkout", "-q", "--", "one")
    missing = gate(repo, "preflight", "someones/fork-branch", "--mode", "redo")
    assert codes(missing) == ["branch-not-local"]


def test_base_trunk_and_parent_merge_base(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    trunk = git(repo, "rev-parse", "main")
    assert gate(repo, "base").stdout.strip() == trunk
    git(repo, "checkout", "-q", "-b", "child")
    commit(repo, "child")
    git(repo, "checkout", "-q", "feature/x")
    fork = git(repo, "rev-parse", "feature/x")
    commit(repo, "parent-advanced")
    git(repo, "checkout", "-q", "child")
    done = gate(repo, "base", "--parent", "feature/x")
    assert done.stdout.strip() == fork
    assert done.stdout.strip() != git(repo, "rev-parse", "feature/x")


def test_base_notes_remote_tracking_base_as_stale(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    done = gate(repo, "base")
    assert done.stdout.strip() == git(repo, "rev-parse", "main")
    assert "stale" in done.stderr


def test_base_refuses_two_merge_bases(tmp_path: Path) -> None:
    repo = tmp_path / "work" / "cross"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "root")
    git(repo, "checkout", "-q", "-b", "a")
    commit(repo, "a1")
    git(repo, "checkout", "-q", "-b", "b", "main")
    commit(repo, "b1")
    git(repo, "checkout", "-q", "a")
    git(repo, "merge", "-q", "--no-edit", "b")
    git(repo, "checkout", "-q", "b")
    git(repo, "merge", "-q", "--no-edit", "a~1")
    done = gate(repo, "base", "--parent", "a")
    assert done.returncode == REFUSED
    assert "found 2" in done.stdout


def test_base_branch_option_works_off_the_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "main")
    assert gate(repo, "base", "--branch", "feature/x").stdout.strip() == git(
        repo, "rev-parse", "main"
    )


def test_backup_names_reads_back_and_collapses(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    tip = git(repo, "rev-parse", "HEAD")
    base = git(repo, "rev-parse", "main")
    done = gate(repo, "backup", "feature/x", tip, "--soft-reset", base)
    name = done.stdout.strip()
    assert done.returncode == 0, done.stdout + done.stderr
    assert re.fullmatch(r"backup/feature-x-\d{8}T\d{6}Z", name)
    assert git(repo, "rev-parse", f"refs/heads/{name}") == tip
    assert git(repo, "rev-parse", "HEAD") == base
    assert git(repo, "diff", "--cached", "--name-only").splitlines() == ["one", "two"]


def test_backup_refuses_wrong_tip(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    done = gate(repo, "backup", "feature/x", git(repo, "rev-parse", "HEAD~1"))
    assert done.returncode == REFUSED
    assert "is not the tip of feature/x" in done.stdout
    assert git(repo, "branch", "--list", "backup/*") == ""


def test_backup_refuses_base_that_is_not_an_ancestor(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "elsewhere", "main")
    commit(repo, "elsewhere")
    git(repo, "checkout", "-q", "feature/x")
    tip = git(repo, "rev-parse", "HEAD")
    done = gate(
        repo, "backup", "feature/x", tip, "--soft-reset", git(repo, "rev-parse", "elsewhere")
    )
    assert done.returncode == REFUSED
    assert "not an ancestor of the tip" in done.stdout
    assert git(repo, "rev-parse", "HEAD") == tip


def push_setup(tmp_path: Path, *, upstream: bool) -> tuple[Path, Path]:
    repo = make_repo(tmp_path)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", *(["-u"] if upstream else []), "origin", "feature/x")
    return repo, remote


@pytest.mark.parametrize("upstream", [True, False])
def test_remote_tip_finds_pushed_branch_with_or_without_upstream(
    tmp_path: Path, upstream: bool
) -> None:
    repo, _ = push_setup(tmp_path, upstream=upstream)
    tip = git(repo, "rev-parse", "HEAD")
    done = gate(repo, "remote-tip", "feature/x")
    assert done.returncode == 0, done.stdout
    assert "pushed=yes" in done.stdout
    assert f"tip={tip}" in done.stdout
    assert (
        f"push=git push --force-with-lease=feature/x:{tip} origin feature/x:feature/x"
        in done.stdout
    )
    assert "--force-if-includes" not in done.stdout


def test_remote_tip_unpushed_and_no_remote(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert gate(repo, "remote-tip", "feature/x").stdout == "pushed=no\n"
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    done = gate(repo, "remote-tip", "feature/x")
    assert done.returncode == 0
    assert "pushed=no" in done.stdout


def test_remote_tip_refuses_when_someone_else_pushed(tmp_path: Path) -> None:
    repo, remote = push_setup(tmp_path, upstream=False)
    peer = tmp_path / "peer"
    git(tmp_path, "clone", "-q", "--branch", "feature/x", str(remote), str(peer))
    commit(peer, "theirs")
    git(peer, "push", "-q", "origin", "feature/x")
    done = gate(repo, "remote-tip", "feature/x")
    assert done.returncode == REFUSED
    assert "remote-ahead" in done.stdout
    assert git(repo, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/feature/x") == git(
        repo, "rev-parse", "HEAD"
    )


def test_remote_tip_refuses_unreachable_remote(tmp_path: Path) -> None:
    repo, remote = push_setup(tmp_path, upstream=True)
    remote.rename(tmp_path / "gone.git")
    assert "remote-unreachable" in gate(repo, "remote-tip", "feature/x").stdout


def test_staged_asserts_exact_set(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "a").write_text("a\n")
    (repo / "b").write_text("b\n")
    git(repo, "add", "a")
    assert gate(repo, "staged", "a").returncode == 0
    wrong = gate(repo, "staged", "a", "b")
    assert wrong.returncode == REFUSED
    assert "missing: b" in wrong.stdout
    git(repo, "add", "b")
    assert "unexpected: b" in gate(repo, "staged", "a").stdout
    assert gate(repo, "staged").returncode == REFUSED


def test_hunks_cli_keeps_header_and_chosen_hunks(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    commit(repo, "f", "".join(f"line {i}\n" for i in range(40)))
    lines = (repo / "f").read_text().splitlines()
    lines[1] = "changed top"
    lines[38] = "changed bottom"
    (repo / "f").write_text("\n".join(lines) + "\n")
    patch = tmp_path / "round.patch"
    patch.write_text(git(repo, "diff", "--", "f") + "\n")
    done = gate(repo, "hunks", str(patch), "2")
    assert done.returncode == 0
    assert "changed bottom" in done.stdout
    assert "changed top" not in done.stdout
    assert gate(repo, "hunks", str(patch), "3").returncode == REFUSED


def redo_fixture(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "work" / "redo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "tests/test_old.py", "old\n")
    commit(repo, "tests/test_gone.py", "gone\n")
    commit(repo, "tests/test_moved.py", "moved\n")
    commit(repo, "src/app.py", "app\n")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "feature/x")
    commit(repo, "tests/test_old.py", "old changed\n")
    git(repo, "rm", "-q", "tests/test_gone.py")
    git(repo, "mv", "tests/test_moved.py", "tests/test_renamed.py")
    commit(repo, "tests/conftest.py", "fixture\n")
    commit(repo, "tests/__snapshots__/s.txt", "snap\n")
    commit(repo, "src/app.py", "app changed\n")
    return repo, base, "feature/x"


def test_carry_applies_modifies_adds_deletes_and_renames(tmp_path: Path) -> None:
    repo, base, branch = redo_fixture(tmp_path)
    listing = gate(repo, "changed", base, branch).stdout
    assert "D\ttests/test_gone.py" in listing
    assert "A\ttests/test_renamed.py" in listing
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "--detach", str(wt), base)
    done = gate(wt, "carry", base, branch, "tests")
    assert done.returncode == 0, done.stdout + done.stderr
    assert (wt / "tests/test_old.py").read_text() == "old changed\n"
    assert not (wt / "tests/test_gone.py").exists()
    assert not (wt / "tests/test_moved.py").exists()
    assert (wt / "tests/test_renamed.py").read_text() == "moved\n"
    assert (wt / "tests/conftest.py").exists()
    assert (wt / "tests/__snapshots__/s.txt").exists()
    assert (wt / "src/app.py").read_text() == "app\n"
    staged = set(git(wt, "diff", "--cached", "--name-only").splitlines())
    assert "tests/test_gone.py" in staged
    assert "src/app.py" not in staged


def test_carry_refuses_off_base_and_empty_selection(tmp_path: Path) -> None:
    repo, base, branch = redo_fixture(tmp_path)
    done = gate(repo, "carry", base, branch, "tests")
    assert (done.returncode, "HEAD is not the base" in done.stdout) == (REFUSED, True)
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "--detach", str(wt), base)
    done = gate(wt, "carry", base, branch, "docs")
    assert (done.returncode, "no change under those pathspecs" in done.stdout) == (REFUSED, True)


def author_commit(repo: Path, name: str, who: str, date: str, body: str = "") -> None:
    (repo / name).write_text(f"{name}\n")
    git(repo, "add", "--", name)
    msg = f"add {name}\n\n{body}" if body else f"add {name}"
    git(
        repo,
        "commit",
        "-q",
        "-m",
        msg,
        env={
            "GIT_AUTHOR_NAME": who,
            "GIT_AUTHOR_EMAIL": f"{who}@example.com",
            "GIT_AUTHOR_DATE": date,
        },
    )


def test_series_compares_authors_and_dates(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "main")
    git(repo, "reset", "-q", "--hard", base)
    author_commit(repo, "a", "ada", "2026-10-01T09:30:00+00:00")
    author_commit(repo, "b", "bob", "2026-10-02T09:30:00+02:00")
    git(repo, "branch", "backup", "HEAD")
    git(repo, "reset", "-q", base)
    author_commit(repo, "a", "ada", "2026-10-01T09:30:00+00:00")
    wrong_date = gate(repo, "series", base, "HEAD", "--authors-of", "backup")
    assert wrong_date.returncode == REFUSED
    assert "original author lost: bob" in wrong_date.stdout
    author_commit(repo, "b", "bob", "2026-10-02T09:30:00+02:00")
    done = gate(repo, "series", base, "HEAD", "--authors-of", "backup")
    assert done.returncode == 0, done.stdout
    # %aI prints a UTC offset as +00:00, or as Z on newer git.
    assert re.search(r"ada <ada@example\.com> 2026-10-01T09:30:00(\+00:00|Z) add a", done.stdout)
    git(repo, "reset", "-q", "--soft", "HEAD~1")
    git(repo, "commit", "-q", "-m", "add b", "--date", "2026-10-09T00:00:00+00:00")
    forged = gate(repo, "series", base, "HEAD", "--authors-of", "backup")
    assert forged.returncode == REFUSED
    assert "not in the original: t <t@example.com>" in forged.stdout


def test_backup_soft_reset_refuses_when_not_checked_out(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    tip = git(repo, "rev-parse", "HEAD")
    base = git(repo, "rev-parse", "main")
    git(repo, "checkout", "-q", "main")
    done = gate(repo, "backup", "feature/x", tip, "--soft-reset", base)
    assert done.returncode == REFUSED
    assert "not-checked-out" in done.stdout
    assert git(repo, "branch", "--list", "backup/*") == ""


def test_backup_same_second_gets_numeric_suffix(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    tip = git(repo, "rev-parse", "HEAD")
    names = {gate(repo, "backup", "feature/x", tip).stdout.strip() for _ in range(RUNS)}
    assert len(names) == RUNS
    assert all(git(repo, "rev-parse", f"refs/heads/{n}") == tip for n in names)


def test_remote_tip_refuses_several_remotes_without_origin(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    for name in ("up", "fork"):
        bare = tmp_path / f"{name}.git"
        git(tmp_path, "init", "-q", "--bare", str(bare))
        git(repo, "remote", "add", name, str(bare))
    done = gate(repo, "remote-tip", "feature/x")
    assert done.returncode == REFUSED
    assert "remote-unknown" in done.stdout
    assert "pushed=no" not in done.stdout


def test_preflight_redo_checks_parent_resolves(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert (
        gate(repo, "preflight", "feature/x", "--mode", "redo", "--parent", "main").returncode == 0
    )
    bad = gate(repo, "preflight", "feature/x", "--mode", "redo", "--parent", "nope")
    assert codes(bad) == ["base"]
