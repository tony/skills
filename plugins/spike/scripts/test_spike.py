"""Run spike.sh against throwaway repositories under pytest."""

# ruff: noqa: S101, S603, S607, INP001, D103, PLR2004
# pyright: reportUnusedCallResult=false

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

SPIKE = pathlib.Path(__file__).with_name("spike.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="spike.sh needs bash and git",
)


def git(repo: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.rstrip("\n")


def spike(
    repo: pathlib.Path,
    *args: str,
    home: pathlib.Path | None = None,
    message: str | None = None,
    unset_home: bool = False,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HOME": str(home or repo.parent / "home")}
    if unset_home:
        env.pop("HOME")
    cmd = [str(SPIKE), *args]
    if message is not None:
        cmd += ["-F", "-"]
    return subprocess.run(
        cmd,
        cwd=repo,
        env=env,
        input=message,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "home").mkdir()
    root = tmp_path / "proj"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    (root / "notes.txt").write_text("base\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    return root


def dirty_user_work(root: pathlib.Path) -> None:
    (root / "notes.txt").write_text("base\nuser edit\n")
    (root / "scratch.txt").write_text("user scratch\n")


def test_guard_ok(repo: pathlib.Path) -> None:
    result = spike(repo, "guard")
    assert result.returncode == 0
    assert result.stdout.strip() == "ok"


def test_guard_refuses_no_commits(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    git(root, "init", "-q")
    result = spike(root, "guard", home=tmp_path)
    assert result.returncode == 1
    assert "no commits" in result.stderr


def test_guard_refuses_root_containing_home(repo: pathlib.Path) -> None:
    home = repo / "sub" / "home"
    home.mkdir(parents=True)
    result = spike(repo, "guard", home=home)
    assert result.returncode == 1
    assert "contains home" in result.stderr

    exact = spike(repo, "guard", home=repo)
    assert exact.returncode == 1


def test_stash_refuses_at_home_before_touching_files(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    result = spike(repo, "stash", message="m", home=repo)
    assert result.returncode == 1
    assert (repo / "scratch.txt").exists()
    assert git(repo, "stash", "list") == ""


def test_stash_prints_own_sha_and_cleans_tree(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    result = spike(repo, "stash", message="spike: demo")
    sha = result.stdout.strip()
    assert result.returncode == 0
    assert git(repo, "stash", "list", "--format=%H") == sha
    assert git(repo, "status", "--porcelain") == ""


def test_stash_keep_leaves_the_work_in_the_tree(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    sha = spike(repo, "stash", "--keep", message="spike: kept").stdout.strip()
    assert git(repo, "stash", "list", "--format=%H") == sha
    assert (repo / "notes.txt").read_text() == "base\nuser edit\n"
    status = git(repo, "status", "--porcelain").splitlines()
    assert " M notes.txt" in status
    assert "?? scratch.txt" in status
    assert "user edit" in git(repo, "stash", "show", "-p", sha)


def test_stash_unchanged_tree_reports_no_changes(repo: pathlib.Path) -> None:
    result = spike(repo, "stash", message="spike: nothing")
    assert result.stdout.strip() == "no changes"
    assert git(repo, "stash", "list") == ""


def test_stash_first_saves_and_restores_user_work(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "save-user").stdout.strip()
    assert len(user) == 40
    assert git(repo, "status", "--porcelain") == ""

    (repo / "notes.txt").write_text("base\nspiked\n")
    spike_sha = spike(repo, "stash", message="spike: s").stdout.strip()
    assert spike_sha != user

    restored = spike(repo, "restore", user)
    assert restored.returncode == 0
    assert (repo / "notes.txt").read_text() == "base\nuser edit\n"
    assert (repo / "scratch.txt").read_text() == "user scratch\n"
    assert git(repo, "stash", "list", "--format=%H").splitlines() == [spike_sha, user]


def test_restore_refusal_keeps_the_stash(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "save-user").stdout.strip()
    (repo / "scratch.txt").write_text("blocking untracked\n")
    result = spike(repo, "restore", user)
    assert result.returncode == 1
    assert user in result.stderr
    assert user in git(repo, "stash", "list", "--format=%H")


def probe_on_top(repo: pathlib.Path) -> tuple[str, str]:
    dirty_user_work(repo)
    user = spike(repo, "hold-user").stdout.strip()
    (repo / "notes.txt").write_text("base\nuser edit\nspike line\n")
    (repo / "feature.txt").write_text("spike file\n")
    spike_sha = spike(repo, "stash-on-top", user, message="spike: top").stdout.strip()
    return user, spike_sha


def test_probe_on_top_restores_user_work_and_reports_both_shas(
    repo: pathlib.Path,
) -> None:
    user, spike_sha = probe_on_top(repo)
    assert len(user) == 40
    assert len(spike_sha) == 40
    assert (repo / "notes.txt").read_text() == "base\nuser edit\n"
    assert (repo / "scratch.txt").read_text() == "user scratch\n"
    assert not (repo / "feature.txt").exists()
    status = git(repo, "status", "--porcelain").splitlines()
    assert " M notes.txt" in status
    assert "?? scratch.txt" in status


def test_hold_user_leaves_files_in_tree(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "hold-user").stdout.strip()
    assert len(user) == 40
    assert (repo / "notes.txt").read_text() == "base\nuser edit\n"
    assert "?? scratch.txt" in git(repo, "status", "--porcelain").splitlines()


def test_stash_on_top_without_spike_changes(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "hold-user").stdout.strip()
    result = spike(repo, "stash-on-top", user, message="spike: none")
    assert result.stdout.strip() == "no changes"
    assert (repo / "notes.txt").read_text() == "base\nuser edit\n"


def test_delta_excludes_user_edits(repo: pathlib.Path) -> None:
    user, spike_sha = probe_on_top(repo)
    delta = spike(repo, "delta", user, spike_sha).stdout
    assert "+spike line" in delta
    assert "+spike file" in delta
    assert "+user edit" not in delta
    assert "user scratch" not in delta


def test_replay_applies_only_the_spike_delta(repo: pathlib.Path) -> None:
    user, spike_sha = probe_on_top(repo)
    result = spike(repo, "replay-apply", spike_sha, user)
    assert result.returncode == 0, result.stderr
    assert (repo / "notes.txt").read_text() == "base\nuser edit\nspike line\n"
    assert (repo / "feature.txt").read_text() == "spike file\n"
    git(repo, "add", "feature.txt")
    git(repo, "commit", "-q", "-m", "land spike")
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "feature.txt"
    show = git(repo, "show", "HEAD")
    assert "user edit" not in show
    assert "user scratch" not in show
    assert "?? scratch.txt" in git(repo, "status", "--porcelain").splitlines()


def test_replay_apply_stash_first_uses_whole_stash(repo: pathlib.Path) -> None:
    (repo / "feature.txt").write_text("spike file\n")
    spike_sha = spike(repo, "stash", message="spike: s").stdout.strip()
    result = spike(repo, "replay-apply", spike_sha)
    assert result.returncode == 0, result.stderr
    assert (repo / "feature.txt").read_text() == "spike file\n"
    assert spike_sha in git(repo, "stash", "list", "--format=%H")


def test_drop_matches_by_sha_and_spares_user_work(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "save-user").stdout.strip()
    (repo / "feature.txt").write_text("one\n")
    first = spike(repo, "stash", message="spike: one").stdout.strip()
    (repo / "feature.txt").write_text("two\n")
    second = spike(repo, "stash", message="spike: two").stdout.strip()

    assert spike(repo, "drop", first).stdout.strip() == "dropped"
    assert git(repo, "stash", "list", "--format=%H").splitlines() == [second, user]
    assert spike(repo, "drop", first).stdout.strip() == "already gone"

    refused = spike(repo, "drop", user)
    assert refused.returncode == 1
    assert user in git(repo, "stash", "list", "--format=%H")


def test_drop_accepts_an_abbreviated_sha(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "save-user").stdout.strip()
    (repo / "feature.txt").write_text("one\n")
    first = spike(repo, "stash", message="spike: one").stdout.strip()

    assert spike(repo, "drop", first[:7]).stdout.strip() == "dropped"
    assert git(repo, "stash", "list", "--format=%H") == user
    assert spike(repo, "drop", first[:7]).stdout.strip() == "already gone"
    assert spike(repo, "drop", "0123abc").stdout.strip() == "already gone"

    refused = spike(repo, "drop", user[:7])
    assert refused.returncode == 1
    assert user in git(repo, "stash", "list", "--format=%H")


def test_stash_on_top_prints_the_spike_sha_before_a_refused_restore(
    repo: pathlib.Path,
) -> None:
    (repo / "u.txt").write_text("user file\n")
    user = spike(repo, "hold-user").stdout.strip()
    (repo / ".gitignore").write_text("u.txt\n")
    result = spike(repo, "stash-on-top", user, message="spike: top")
    spike_sha = git(repo, "stash", "list", "--format=%H").splitlines()[0]
    assert result.returncode == 1
    assert result.stdout.strip() == spike_sha
    assert spike_sha != user
    assert user in result.stderr
    assert user in git(repo, "stash", "list", "--format=%H")


def test_delta_without_spike_sha_diffs_the_tree(repo: pathlib.Path) -> None:
    dirty_user_work(repo)
    user = spike(repo, "hold-user").stdout.strip()
    (repo / "notes.txt").write_text("base\nuser edit\nspike line\n")
    (repo / "feature.txt").write_text("spike file\n")
    delta = spike(repo, "delta", user).stdout
    assert "+spike line" in delta
    assert "+spike file" in delta
    assert "+user edit" not in delta
    assert "user scratch" not in delta
    assert "?? feature.txt" in git(repo, "status", "--porcelain").splitlines()


def test_branch_round_trip(repo: pathlib.Path) -> None:
    orig = spike(repo, "branch-start", "scratch").stdout.strip()
    assert orig == "main"
    assert git(repo, "branch", "--show-current") == "scratch"
    assert spike(repo, "branch-end", orig, "scratch").returncode == 0
    assert git(repo, "branch", "--show-current") == "main"
    assert git(repo, "branch", "--list", "scratch") == ""


def test_branch_start_existing_name_fails(repo: pathlib.Path) -> None:
    git(repo, "branch", "taken")
    result = spike(repo, "branch-start", "taken")
    assert result.returncode == 1
    assert git(repo, "branch", "--show-current") == "main"


def test_branch_round_trip_detached(repo: pathlib.Path) -> None:
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "--detach", head)
    orig = spike(repo, "branch-start", "scratch").stdout.strip()
    assert orig == head
    assert spike(repo, "branch-end", orig, "scratch").returncode == 0
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "branch", "--show-current") == ""


def test_ledger_dir_resolves_from_a_linked_worktree(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "--detach", str(tree))
    main = spike(repo, "ledger-dir").stdout.strip()
    linked = spike(tree, "ledger-dir").stdout.strip()
    assert main == linked
    assert pathlib.Path(main).is_dir()


def test_guard_without_home_reports_it(repo: pathlib.Path) -> None:
    result = spike(repo, "guard", unset_home=True)
    assert result.returncode == 1
    assert "HOME is not set" in result.stderr


def test_stash_message_with_shell_syntax_is_stored_verbatim(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    marker = tmp_path / "ran"
    goal = f'spike: $(touch {marker}) `touch {marker}` "quoted" (ok)'
    (repo / "feature.txt").write_text("x\n")
    sha = spike(repo, "stash", message=goal).stdout.strip()
    assert goal in git(repo, "stash", "list", "--format=%gs")
    assert git(repo, "stash", "list", "--format=%H") == sha
    assert not marker.exists()


def test_stash_reads_the_message_from_a_file(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    note = tmp_path / "msg.txt"
    note.write_text("spike: from file\nsecond line\n")
    (repo / "feature.txt").write_text("x\n")
    result = spike(repo, "stash", "-F", str(note))
    assert result.returncode == 0, result.stderr
    assert "spike: from file second line" in git(repo, "stash", "list", "--format=%gs")


def test_stash_refuses_a_positional_message(repo: pathlib.Path) -> None:
    (repo / "feature.txt").write_text("x\n")
    result = spike(repo, "stash", "spike: positional")
    assert result.returncode == 2
    assert git(repo, "stash", "list") == ""
    assert (repo / "feature.txt").exists()


def build_output(root: pathlib.Path) -> None:
    (root / "src" / "__pycache__").mkdir(parents=True)
    (root / "src" / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\0")
    (root / "run.log").write_text("log\n")
    (root / "feature.txt").write_text("source\n")


def test_untracked_lists_new_paths_but_not_bytecode_or_ignored(
    repo: pathlib.Path,
) -> None:
    (repo / ".gitignore").write_text("ignored.out\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    (repo / "ignored.out").write_text("x\n")
    build_output(repo)
    listed = spike(repo, "untracked").stdout.split()
    assert sorted(listed) == ["feature.txt", "run.log"]
    assert spike(repo, "untracked", "--leave", "run.log").stdout.split() == ["feature.txt"]


def test_stash_leaves_bytecode_ignored_and_named_paths_in_the_tree(
    repo: pathlib.Path,
) -> None:
    (repo / ".gitignore").write_text("ignored.out\n")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")
    (repo / "ignored.out").write_text("x\n")
    build_output(repo)
    sha = spike(repo, "stash", "--leave", "run.log", message="spike: build").stdout.strip()
    files = git(repo, "diff", "--name-only", "HEAD", sha).splitlines()
    assert files == ["feature.txt"]
    assert (repo / "run.log").exists()
    assert (repo / "ignored.out").exists()
    assert (repo / "src" / "__pycache__" / "m.cpython-312.pyc").exists()
    assert not (repo / "feature.txt").exists()


def test_stash_refuses_while_another_stash_holds_the_lock(
    repo: pathlib.Path,
) -> None:
    lock_dir = pathlib.Path(spike(repo, "ledger-dir").stdout.strip())
    (lock_dir / "stash.lock").write_text(f"{os.getpid()}\n")
    (repo / "feature.txt").write_text("x\n")
    result = spike(repo, "stash", message="spike: busy")
    assert result.returncode == 1
    assert "one at a time" in result.stderr
    assert git(repo, "stash", "list") == ""


def test_stash_clears_a_stale_lock_and_releases_its_own(
    repo: pathlib.Path,
) -> None:
    gone = subprocess.Popen(["true"])
    gone.wait()
    lock = pathlib.Path(spike(repo, "ledger-dir").stdout.strip()) / "stash.lock"
    lock.write_text(f"{gone.pid}\n")
    (repo / "feature.txt").write_text("x\n")
    result = spike(repo, "stash", message="spike: after crash")
    assert result.returncode == 0, result.stderr
    assert not lock.exists()


def test_teardown_removes_a_worktree_holding_left_in_place_files(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    (tree / "feature.txt").write_text("x\n")
    build_output(tree)
    sha = spike(tree, "stash", message="spike: wt").stdout.strip()
    assert (tree / "src" / "__pycache__").exists()
    plain = subprocess.run(
        ["git", "worktree", "remove", str(tree)], cwd=repo, capture_output=True, check=False
    )
    assert plain.returncode != 0
    result = spike(repo, "teardown", str(tree), sha)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "removed"
    assert not tree.exists()
    assert len(git(repo, "worktree", "list").splitlines()) == 1
    assert git(repo, "rev-parse", "--verify", sha)


def test_teardown_refuses_without_a_recorded_stash(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    (tree / "feature.txt").write_text("x\n")
    for sha in ("none", "deadbeef"):
        result = spike(repo, "teardown", str(tree), sha)
        assert result.returncode == 1
        assert tree.exists()


def test_teardown_reads_the_whole_stash_list(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    (tree / "feature.txt").write_text("saved\n")
    sha = spike(tree, "stash", message="spike: long stack").stdout.strip()
    reflog = repo / ".git/logs/refs/stash"
    reflog.write_bytes(reflog.read_bytes() * 8192)
    result = spike(repo, "teardown", str(tree), sha)
    assert result.returncode == 0, result.stderr
    assert not tree.exists()


@pytest.mark.parametrize(
    ("name", "stage"), [("notes.txt", False), ("new.txt", False), ("notes.txt", True)]
)
def test_teardown_preserves_edits_made_after_stashing(
    repo: pathlib.Path, tmp_path: pathlib.Path, name: str, stage: bool
) -> None:
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    (tree / "feature.txt").write_text("saved\n")
    sha = spike(tree, "stash", message="spike: before new work").stdout.strip()
    (tree / name).write_text("new user work\n")
    if stage:
        git(tree, "add", name)
    result = spike(repo, "teardown", str(tree), sha)
    assert result.returncode == 1
    assert "unstashed" in result.stderr
    assert (tree / name).read_text() == "new user work\n"


def test_teardown_preserves_commits_absent_from_stash(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    tree = tmp_path / "wt"
    git(repo, "worktree", "add", "--detach", str(tree), "HEAD")
    (tree / "feature.txt").write_text("saved\n")
    sha = spike(tree, "stash", message="spike: before new commit").stdout.strip()
    (tree / "notes.txt").write_text("new commit\n")
    git(tree, "commit", "-am", "new work")
    result = spike(repo, "teardown", str(tree), sha)
    assert result.returncode == 1
    assert "commits absent" in result.stderr
    assert (tree / "notes.txt").read_text() == "new commit\n"


def test_ledger_dir_falls_back_when_the_git_dir_is_unwritable(
    repo: pathlib.Path,
) -> None:
    git_dir = repo / ".git"
    git_dir.chmod(0o555)
    try:
        if os.access(git_dir, os.W_OK):
            pytest.skip("directory permissions are not enforced")
        result = spike(repo, "ledger-dir")
        assert result.returncode == 0, result.stderr
        ledger = pathlib.Path(result.stdout.strip())
        assert ledger.is_dir()
        assert ledger.name.startswith("spike-ledger.")
        assert git_dir not in ledger.parents
        shutil.rmtree(ledger)
    finally:
        git_dir.chmod(0o755)
