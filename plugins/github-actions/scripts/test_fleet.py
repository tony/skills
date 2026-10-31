"""Tests for fleet.py against throwaway local git repositories."""

# ruff: noqa: S101, INP001, S603, S607, PLR2004
import asyncio
import subprocess
from pathlib import Path

import fleet
import pytest

pytestmark = pytest.mark.integration


def _git(path: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def _clone(root: Path, name: str, url: str = "") -> Path:
    """Create a clone of a bare remote holding one commit on main."""
    bare = root / f"{name}-bare.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    work = root / name
    work.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True)
    _git(work, "remote", "add", "origin", url or str(bare))
    if url:
        _git(work, "config", f"url.{bare}.insteadOf", url)
    (work / "ci.yml").write_text("on: push\n")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "ci")
    _git(work, "push", "-q", "origin", "main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "remote", "set-head", "origin", "main")
    return work


def test_discover_refuses_bad_owner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An owner that is not an account name exits 2 with one reason line."""
    assert fleet.main(["discover", str(tmp_path), "--owner", "a;b"]) == 2
    assert capsys.readouterr().err == "--owner takes account names\n"


async def _fork_is_acme_fork(slug: str) -> bool:
    return slug == "acme/fork"


def test_discover_scopes_by_owner_and_fork(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner filter, forks, unreadable remotes, and nested repositories."""
    root = tmp_path / "fleet"
    root.mkdir()
    _clone(root, "own", "https://github.com/acme/own.git")
    _clone(root, "fork", "https://github.com/acme/fork.git")
    _clone(root, "other", "git@github.com:rival/other.git")
    _clone(root, "elsewhere", "https://example.com/acme/x.git")
    nested = root / "group"
    nested.mkdir()
    _clone(nested, "deep", "https://github.com/acme/deep.git")
    monkeypatch.setattr(fleet, "_is_fork", _fork_is_acme_fork)
    rows = {Path(r["path"]).name: r for r in fleet.discover(str(root), ["ACME"])}
    assert {n: r["in_scope"] for n, r in rows.items()} == {
        "own": True,
        "fork": False,
        "other": False,
        "elsewhere": False,
        "deep": True,
    }
    assert rows["fork"]["reason"] == "repository is a fork"
    assert rows["other"]["reason"] == "owner not in --owner"
    assert "not a github.com URL" in rows["elsewhere"]["reason"]
    everyone = fleet.discover(str(root), [])
    assert {r["owner"] for r in everyone if r["in_scope"]} == {"acme", "rival"}


def test_worktree_need(tmp_path: Path) -> None:
    """A clean default branch needs none; feature branches, dirt, and drift each do."""
    work = _clone(tmp_path, "w")
    clean = fleet.worktree_need(str(work))
    assert (clean["need"], clean["relation"], clean["default"]) == (False, "same", "main")
    (work / "mine.txt").write_text("x")
    assert fleet.worktree_need(str(work))["reasons"] == ["uncommitted or untracked files"]
    (work / "mine.txt").unlink()
    _git(work, "commit", "-q", "--allow-empty", "-m", "local only")
    ahead = fleet.worktree_need(str(work))
    assert (ahead["need"], ahead["relation"]) == (True, "ahead")
    _git(work, "switch", "-q", "-c", "feature/x")
    assert any("feature/x" in r for r in fleet.worktree_need(str(work))["reasons"])
    _git(work, "switch", "-q", "--detach")
    assert "detached HEAD" in fleet.worktree_need(str(work))["reasons"]


def test_branch_reuse_and_suffix(tmp_path: Path) -> None:
    """A branch is reused only for approved subjects and an unoccupied checkout."""
    work = _clone(tmp_path, "b")
    base = "origin/main"
    free = fleet.pick_branch(str(work), base, "bump/checkout", set())
    assert free == {"branch": "bump/checkout", "reuse": False}
    _git(work, "switch", "-q", "-c", "bump/checkout")
    _git(work, "commit", "-q", "--allow-empty", "-m", "Bump actions/checkout v3 -> v4")
    _git(work, "switch", "-q", "main")
    ok = fleet.pick_branch(str(work), base, "bump/checkout", {"Bump actions/checkout v3 -> v4"})
    assert ok == {"branch": "bump/checkout", "reuse": True}
    other = fleet.pick_branch(str(work), base, "bump/checkout", set())
    assert other == {"branch": "bump/checkout-2", "reuse": False}
    elsewhere = tmp_path / "elsewhere"
    _git(work, "worktree", "add", "-q", str(elsewhere), "bump/checkout")
    busy = fleet.pick_branch(str(work), base, "bump/checkout", {"Bump actions/checkout v3 -> v4"})
    assert busy["branch"] == "bump/checkout-2"
    with pytest.raises(fleet.RefusalError, match="not a valid branch name"):
        fleet.pick_branch(str(work), base, "bad..name", set())


def test_pushable_names_commits_not_made_this_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only commits recorded this run, or with an approved subject, may be pushed."""
    work = _clone(tmp_path, "p")
    _git(work, "commit", "-q", "--allow-empty", "-m", "Draft notes")
    mine_sha = _git(work, "rev-parse", "HEAD")
    _git(work, "commit", "-q", "--allow-empty", "-m", "Bump actions/checkout v3 -> v4")
    path = str(work)
    code = fleet.main(["pushable", path, "origin/main", "--made", mine_sha[:12]])
    err = capsys.readouterr().err
    assert code == 1
    assert err == f"not made in this run: {_git(work, 'rev-parse', 'HEAD')[:7]}\n"
    ok = fleet.main(
        [
            "pushable",
            path,
            "origin/main",
            "--made",
            mine_sha[:12],
            "--subject",
            "Bump actions/checkout v3 -> v4",
        ]
    )
    assert ok == 0
    assert fleet.main(["pushable", path, "origin/main", "--made", "abc"]) == 2


def test_fork_checks_run_concurrently_and_keep_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fork flags come back in input order, never more than FORK_CHECKS at once."""
    live = peak = 0

    async def fake(slug: str) -> bool | None:
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.01)
        live -= 1
        return slug.endswith("0")

    slugs = [f"o/r{i}" for i in range(20)]
    monkeypatch.setattr(fleet, "_is_fork", fake)
    flags = asyncio.run(fleet._fork_flags(slugs))  # noqa: SLF001
    assert flags == [s.endswith("0") for s in slugs]
    assert 1 < peak <= fleet.FORK_CHECKS
