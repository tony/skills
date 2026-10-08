"""Tests for repo_facts.py against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import repo_facts  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make(tmp_path: pathlib.Path) -> pathlib.Path:
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / ".tool-versions").write_text("uv 0.7.8 # pin\njust 1.36.0\n")
    (repo / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "1.80.0"\n')
    mise = ["[tools]", 'node = "20"', '"npm:prettier" = "3.3.0" # fmt']
    mise += ['python = ["3.12", "3.11"]', "", "[env]", 'A = "b"', ""]
    (repo / "mise.toml").write_text("\n".join(mise))
    (repo / "go.mod").write_text("module x\n\ngo 1.22\ntoolchain go1.22.3\n")
    (repo / "package.json").write_text('{"packageManager": "pnpm@9.0.0"}')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "main")
    return repo


def test_pins_come_from_default_branch_not_working_tree(tmp_path: pathlib.Path) -> None:
    """A feature branch with a different pin does not change what is reported."""
    repo = _make(tmp_path)
    _git(repo, "checkout", "-q", "-b", "topic")
    (repo / ".tool-versions").write_text("uv 0.9.0\n")
    _git(repo, "commit", "-qam", "topic pin")

    out = repo_facts.facts(str(repo))

    assert out["default_branch"] == "main"
    assert out["branch"] == "topic"
    assert out["pins"] == {
        ".tool-versions": {"uv": "0.7.8", "just": "1.36.0"},
        "mise.toml": {"node": "20", "npm:prettier": "3.3.0", "python": "3.12"},
        "rust-toolchain.toml": "1.80.0",
        "go.mod": {"go": "1.22", "toolchain": "go1.22.3"},
        "package.json": {"packageManager": "pnpm@9.0.0"},
    }


def test_upstream_remote_is_a_fork_signal(tmp_path: pathlib.Path) -> None:
    """An upstream remote flags a fork; a plain clone has no signal."""
    repo = _make(tmp_path)
    assert repo_facts.facts(str(repo))["fork_signal"] is False
    _git(repo, "remote", "add", "upstream", "https://example.com/org/x.git")
    assert repo_facts.facts(str(repo))["fork_signal"] is True


def test_default_branch_falls_back_to_ls_remote(tmp_path: pathlib.Path) -> None:
    """With origin/HEAD unset the remote is asked; behind count is reported."""
    repo = _make(tmp_path)
    _git(repo, "remote", "set-head", "origin", "-d")
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "t")
    (other / "f").write_text("x")
    _git(other, "add", ".")
    _git(other, "commit", "-q", "-m", "ahead")
    _git(other, "push", "-q", "origin", "main")

    out = repo_facts.facts(str(repo), fetch=True)

    assert out["default_branch"] == "main"
    assert out["fetch_ok"] is True
    assert out["behind_remote"] == 1


def test_behind_remote_is_null_without_local_default(tmp_path: pathlib.Path) -> None:
    """An absent local default ref reports null, not a silent zero."""
    repo = _make(tmp_path)
    _git(repo, "checkout", "-q", "-b", "side")
    _git(repo, "branch", "-q", "-D", "main")
    out = repo_facts.facts(str(repo))
    assert out["behind_remote"] is None


def test_linked_worktree_and_non_repo(tmp_path: pathlib.Path) -> None:
    """A linked worktree is flagged; a plain directory reports an error."""
    repo = _make(tmp_path)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wtb", str(wt))
    assert repo_facts.facts(str(wt))["linked_worktree"] is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert "error" in repo_facts.facts(str(plain))


def test_remoteless_repo_reads_pins_from_current_branch(tmp_path: pathlib.Path) -> None:
    """Without a remote, pins come from the current branch."""
    repo = tmp_path / "solo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / ".tool-versions").write_text("uv 0.7.8\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")

    out = repo_facts.facts(str(repo))

    assert out["default_branch"] is None
    assert out["pins_ref"] == "main"
    assert out["pins"] == {".tool-versions": {"uv": "0.7.8"}}
