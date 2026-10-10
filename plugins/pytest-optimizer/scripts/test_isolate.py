"""Owned-Git proofs that execution never touches the user's checkout."""

# ruff: noqa: S101, S603, S607, INP001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false, reportImplicitStringConcatenation=false
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import typing as t

import isolate  # pyright: ignore[reportImplicitRelativeImport]
import pytest

pytestmark = pytest.mark.integration

ENV = (
    "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
)  # fmt: skip


def git(cwd: pathlib.Path, *args: str, check: bool = True) -> str:
    """Run git in ``cwd`` and return stdout."""
    proc = subprocess.run(
        ["git", *ENV, "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert not check or proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a repository with two test files, a README and a side branch."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    (root / "tests" / "conftest.py").write_text("SCOPE = 'function'\n")
    (root / "tests" / "test_a.py").write_text("DELAY = 0.8\n")
    (root / "README.md").write_text("readme\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "branch", "side")
    return root


def make_patch(repo: pathlib.Path, out: pathlib.Path, path: str, text: str) -> dict[str, t.Any]:
    """Record a candidate the way 01-benchmark does, in a detached scratch tree."""
    started = isolate.start(repo, "HEAD")
    assert started["ok"], started
    tree = pathlib.Path(started["tree"])
    (tree / path).write_text(text)
    captured = isolate.capture(tree, out)
    assert captured["ok"], captured
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    return captured


def snapshot(repo: pathlib.Path) -> dict[str, t.Any]:
    """Everything the user could lose: refs, index, status and file bytes."""
    files = {
        str(p.relative_to(repo)): p.read_bytes()
        for p in sorted(repo.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(repo).parts
    }
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "branch": git(repo, "symbolic-ref", "HEAD"),
        "refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"),
        "index": (repo / ".git" / "index").read_bytes(),
        "status": git(repo, "status", "--porcelain=v2", "--untracked-files=all"),
        "files": files,
    }


def test_failed_item_and_user_edits_never_cross_the_boundary(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """A good item, concurrent user edits and a failing item leave the checkout alone."""
    good = make_patch(repo, tmp_path / "good.patch", "tests/conftest.py", "SCOPE = 'session'\n")
    bad = make_patch(repo, tmp_path / "bad.patch", "tests/test_a.py", "DELAY = 0.0\n")
    base = git(repo, "rev-parse", "HEAD")
    before_refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads").split("\n")

    started = isolate.start(repo, base, "pytest-optimizer/run1")
    assert started["ok"], started
    tree = pathlib.Path(started["tree"])

    applied = isolate.apply(tree, tmp_path / "good.patch", good["sha256"], ["tests/conftest.py"])
    assert applied["ok"], applied
    gated = isolate.gate(tree, ["tests/conftest.py"])
    assert gated["ok"], gated
    git(tree, "commit", "-q", "-m", "item one")
    assert isolate.landed(tree, gated["parent"], gated["tree"])["ok"]

    # The user keeps working while the run is in flight.
    (repo / "README.md").write_text("readme, edited by the user\n")
    (repo / "notes.txt").write_text("untracked user notes\n")
    (repo / "tests" / "test_a.py").write_text("DELAY = 0.8  # user edit\n")
    git(repo, "add", "tests/test_a.py")
    (repo / ".git" / "index.lock").write_text("")
    midway = snapshot(repo)

    applied = isolate.apply(tree, tmp_path / "bad.patch", bad["sha256"], ["tests/test_a.py"])
    assert applied["ok"], applied
    assert (tree / "tests" / "test_a.py").read_text() == "DELAY = 0.0\n"
    assert isolate.reset(tree)["ok"]
    assert (tree / "tests" / "test_a.py").read_text() == "DELAY = 0.8\n"
    assert git(tree, "status", "--porcelain") == ""
    assert git(tree, "rev-list", "--count", f"{base}..HEAD") == "1"

    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    assert snapshot(repo) == midway

    (repo / ".git" / "index.lock").unlink()
    after_refs = git(repo, "for-each-ref", "--format=%(refname)", "refs/heads").split("\n")
    assert sorted(after_refs) == sorted([*before_refs, "refs/heads/pytest-optimizer/run1"])
    git(repo, "merge", "--ff-only", "pytest-optimizer/run1")
    assert (repo / "tests" / "conftest.py").read_text() == "SCOPE = 'session'\n"
    assert (repo / "README.md").read_text() == "readme, edited by the user\n"
    assert (repo / "notes.txt").read_text() == "untracked user notes\n"


def test_reset_and_apply_refuse_the_users_checkout(repo: pathlib.Path) -> None:
    """Only a worktree this tool created can be reset or patched."""
    (repo / "README.md").write_text("dirty\n")
    (repo / "scratch.txt").write_text("untracked\n")

    for refusal in (isolate.reset(repo), isolate.gate(repo, ["README.md"])):
        assert refusal["ok"] is False
    assert (repo / "README.md").read_text() == "dirty\n"
    assert (repo / "scratch.txt").exists()
    assert isolate.finish(repo)["removed"] is False
    assert repo.exists()


def test_apply_rejects_altered_patch_and_wrong_file_set(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """A patch whose bytes or paths differ from the plan is never applied."""
    patch = tmp_path / "p.patch"
    cap = make_patch(repo, patch, "tests/conftest.py", "SCOPE = 'session'\n")
    started = isolate.start(repo, "HEAD")
    tree = pathlib.Path(started["tree"])

    assert isolate.apply(tree, patch, "0" * 64, ["tests/conftest.py"])["ok"] is False
    wrong = isolate.apply(tree, patch, cap["sha256"], ["tests/test_a.py"])
    assert wrong["ok"] is False
    assert git(tree, "status", "--porcelain") == ""
    patch.write_bytes(patch.read_bytes() + b"\n")
    assert isolate.apply(tree, patch, cap["sha256"], ["tests/conftest.py"])["ok"] is False
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_gate_and_landed_catch_extra_paths_and_hook_edits(
    repo: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Files the run created, and bytes a hook changed, never pass as the gated item."""
    patch = tmp_path / "p.patch"
    cap = make_patch(repo, patch, "tests/conftest.py", "SCOPE = 'session'\n")
    started = isolate.start(repo, "HEAD", "pytest-optimizer/run2")
    tree = pathlib.Path(started["tree"])
    assert isolate.apply(tree, patch, cap["sha256"], ["tests/conftest.py"])["ok"]

    (tree / "stray.log").write_text("written by a timed test\n")
    stray = isolate.gate(tree, ["tests/conftest.py"])
    assert (stray["ok"], stray["paths"]) == (False, ["stray.log"])
    (tree / "stray.log").unlink()

    gated = isolate.gate(tree, ["tests/conftest.py"])
    assert gated["ok"]
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho '# hooked' >> tests/conftest.py\ngit add tests/conftest.py\n")
    hook.chmod(0o755)
    git(tree, "commit", "-q", "-m", "item")
    result = isolate.landed(tree, gated["parent"], gated["tree"])
    assert (result["ok"], result["reason"]) == (False, "committed tree differs from the gated tree")
    assert isolate.reset(tree, gated["parent"])["ok"]
    assert git(tree, "rev-parse", "HEAD") == gated["parent"]
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]


def test_finish_removes_only_its_own_worktree(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """Another worktree on the repository survives; no prune is involved."""
    other = tmp_path / "other"
    git(repo, "worktree", "add", "-q", "--detach", str(other))
    started = isolate.start(repo, "HEAD")

    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    assert other.is_dir()
    assert str(other.resolve()) in git(repo, "worktree", "list", "--porcelain")
    assert started["dir"] not in git(repo, "worktree", "list", "--porcelain")


def test_finish_drops_only_an_unused_result_branch(repo: pathlib.Path) -> None:
    """A branch with commits is kept; an untouched one is removed."""
    base = git(repo, "rev-parse", "HEAD")
    kept = isolate.start(repo, base, "pytest-optimizer/kept")
    kept_tree = pathlib.Path(kept["tree"])
    (kept_tree / "new.txt").write_text("x\n")
    git(kept_tree, "add", "new.txt")
    git(kept_tree, "commit", "-q", "-m", "work")
    unused = isolate.start(repo, base, "pytest-optimizer/unused")

    assert isolate.finish(pathlib.Path(kept["dir"]), base)["branch_dropped"] is False
    assert isolate.finish(pathlib.Path(unused["dir"]), base)["branch_dropped"] is True
    branches = git(repo, "branch", "--list", "pytest-optimizer/*")
    assert "kept" in branches
    assert "unused" not in branches


def test_export_fallback_captures_a_bound_patch(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A host that refuses worktrees still yields the same hash-bound patch."""
    (repo / "untracked.txt").write_text("not exported\n")
    started = isolate.start(repo, "HEAD", export=True)
    tree = pathlib.Path(started["tree"])
    assert not (tree / "untracked.txt").exists()
    (tree / "tests" / "conftest.py").write_text("SCOPE = 'session'\n")
    cap = isolate.capture(tree, tmp_path / "e.patch")

    assert cap["ok"]
    assert cap["sha256"] == hashlib.sha256((tmp_path / "e.patch").read_bytes()).hexdigest()
    assert isolate.finish(pathlib.Path(started["dir"]))["removed"]
    assert "untracked.txt" in git(repo, "status", "--porcelain")


def test_inputs_digest_binds_dirty_and_untracked_bytes(repo: pathlib.Path) -> None:
    """Edits that keep HEAD and node ids unchanged still change the digest."""
    clean = isolate.inputs(repo)
    assert clean["dirty"] is False

    (repo / "tests" / "test_a.py").write_text("DELAY = 0.1\n")
    tracked = isolate.inputs(repo)
    (repo / "helper.py").write_text("X = 1\n")
    untracked = isolate.inputs(repo)
    (repo / "helper.py").write_text("X = 2\n")

    digests = [
        clean["digest"],
        tracked["digest"],
        untracked["digest"],
        isolate.inputs(repo)["digest"],
    ]
    assert len(set(digests)) == len(digests)
    assert (tracked["dirty"], untracked["untracked"]) == (True, 1)
