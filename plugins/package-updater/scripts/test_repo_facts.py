"""Tests for repo_facts.py against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, cast

import pytest
import repo_facts  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib

# Native Git fixtures use the outer loop; lock-text parsing stays in the unit loop.


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


@pytest.mark.integration
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


@pytest.mark.integration
def test_upstream_remote_is_a_fork_signal(tmp_path: pathlib.Path) -> None:
    """An upstream remote flags a fork; a plain clone has no signal."""
    repo = _make(tmp_path)
    assert repo_facts.facts(str(repo))["fork_signal"] is False
    _git(repo, "remote", "add", "upstream", "https://example.com/org/x.git")
    assert repo_facts.facts(str(repo))["fork_signal"] is True


@pytest.mark.integration
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


@pytest.mark.integration
def test_behind_remote_is_null_without_local_default(tmp_path: pathlib.Path) -> None:
    """An absent local default ref reports null, not a silent zero."""
    repo = _make(tmp_path)
    _git(repo, "checkout", "-q", "-b", "side")
    _git(repo, "branch", "-q", "-D", "main")
    out = repo_facts.facts(str(repo))
    assert out["behind_remote"] is None


@pytest.mark.integration
def test_linked_worktree_and_non_repo(tmp_path: pathlib.Path) -> None:
    """A linked worktree is flagged; a plain directory reports an error."""
    repo = _make(tmp_path)
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "wtb", str(wt))
    assert repo_facts.facts(str(wt))["linked_worktree"] is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert "error" in repo_facts.facts(str(plain))


@pytest.mark.integration
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


def _lock(*pairs: tuple[str, str]) -> str:
    return "version = 1\n" + "".join(
        f'\n[[package]]\nname = "{n}"\nversion = "{v}"\nsource = {{ registry = "x" }}\n'
        for n, v in pairs
    )


@pytest.mark.integration
def test_lock_diff_splits_majors_from_in_range(tmp_path: pathlib.Path) -> None:
    """A new major, or a new 0.x minor, is a major; a minor or patch is in range."""
    repo = tmp_path / "locked"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    base = _lock(("requests", "2.31.0"), ("pytest", "7.4.4"), ("ruff", "0.4.1"), ("same", "1.0.0"))
    (repo / "uv.lock").write_text(base)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    new = _lock(
        ("requests", "3.0.0"), ("pytest", "7.5.1"), ("ruff", "0.5.0"), ("same", "1.0.0"),
        ("fresh", "1.0.0"),
    )  # fmt: skip
    (repo / "uv.lock").write_text(new)

    out = repo_facts.lock_diff(str(repo), [])

    assert out["uv.lock"] == {
        "majors": [
            {"name": "requests", "from": ["2.31.0"], "to": ["3.0.0"]},
            {"name": "ruff", "from": ["0.4.1"], "to": ["0.5.0"]},
        ],
        "in_range": [
            {"name": "fresh", "from": [], "to": ["1.0.0"]},
            {"name": "pytest", "from": ["7.4.4"], "to": ["7.5.1"]},
        ],
    }


@pytest.mark.integration
def test_failed_status_is_unknown_and_preserves_index(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable status cannot authorize work in the user's checkout."""
    repo = _make(tmp_path)
    _git(repo, "remote", "set-head", "origin", "main")
    index = repo / ".git" / "index"
    before = index.read_bytes()
    broken = tmp_path / "broken-index"
    broken.write_bytes(b"invalid index")
    monkeypatch.setenv("GIT_INDEX_FILE", str(broken))

    out = repo_facts.facts(str(repo))

    assert out["dirty"] is None
    assert out["failed"] == ["worktree status"]
    assert index.read_bytes() == before
    assert broken.read_bytes() == b"invalid index"


@pytest.mark.integration
def test_multiple_non_origin_remotes_need_a_choice(tmp_path: pathlib.Path) -> None:
    """Choosing the alphabetically first remote can target another repository."""
    repo = _make(tmp_path)
    _git(repo, "remote", "rename", "origin", "alpha")
    _git(repo, "remote", "add", "beta", "../another.git")

    out = repo_facts.facts(str(repo), fetch=True)

    assert out["remote"] is None
    assert out["error"] == "multiple remotes without origin"
    assert "fetch_ok" not in out
    assert "pins" not in out


@pytest.mark.integration
def test_remote_name_with_slash_keeps_default_branch(tmp_path: pathlib.Path) -> None:
    """A slash belongs to the remote name, not the default branch."""
    repo = _make(tmp_path)
    _git(repo, "remote", "set-head", "origin", "main")
    _git(repo, "remote", "rename", "origin", "team/fork")

    out = repo_facts.facts(str(repo))

    assert out["default_branch"] == "main"
    assert out["pins_ref"] == "team/fork/main"
    pins = cast("dict[str, object]", out["pins"])
    assert pins[".tool-versions"] == {"uv": "0.7.8", "just": "1.36.0"}


def test_added_parallel_major_is_not_in_range() -> None:
    """A lock may retain an old version while adding an incompatible one."""
    changes = repo_facts.lock_changes(
        _lock(("demo", "1.0.0")),
        _lock(("demo", "1.0.0"), ("demo", "2.0.0")),
    )

    assert changes == {
        "majors": [{"name": "demo", "from": [], "to": ["2.0.0"]}],
        "in_range": [],
    }


@pytest.mark.parametrize(("quote", "newline"), [("'", "\n"), ('"', "\r\n"), ("'", "\r\n")])
def test_lock_spelling_cannot_hide_major(quote: str, newline: str) -> None:
    """TOML string quotes and CRLF preserve package identity and version."""
    changes = repo_facts.lock_changes(
        _lock(("demo", "1.0.0")).replace('"', quote).replace("\n", newline),
        _lock(("demo", "2.0.0")).replace('"', quote).replace("\n", newline),
    )

    assert changes == {
        "majors": [{"name": "demo", "from": ["1.0.0"], "to": ["2.0.0"]}],
        "in_range": [],
    }


@pytest.mark.integration
def test_lock_diff_reads_crlf_blob_without_trimming(tmp_path: pathlib.Path) -> None:
    """Git blob content keeps the line ending after the final version field."""
    repo = _make(tmp_path)
    _git(repo, "config", "core.autocrlf", "false")
    base = b'[[package]]\r\nname = "demo"\r\nversion = "1.0.0"\r\n'
    (repo / "Cargo.lock").write_bytes(base)
    _git(repo, "add", "Cargo.lock")
    _git(repo, "commit", "-q", "-m", "lock")
    changed = base.replace(b"1.0.0", b"2.0.0")
    (repo / "Cargo.lock").write_bytes(changed)
    index = (repo / ".git" / "index").read_bytes()

    out = repo_facts.lock_diff(str(repo), ["Cargo.lock"])

    assert out["Cargo.lock"] == {
        "majors": [{"name": "demo", "from": ["1.0.0"], "to": ["2.0.0"]}],
        "in_range": [],
    }
    assert (repo / ".git" / "index").read_bytes() == index
    assert (repo / "Cargo.lock").read_bytes() == changed


@pytest.mark.integration
def test_unreadable_head_lock_is_not_an_empty_baseline(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Git objects leave classification unavailable without writes."""
    repo = _make(tmp_path)
    original = _lock(("demo", "1.0.0"))
    (repo / "uv.lock").write_text(original)
    _git(repo, "add", "uv.lock")
    _git(repo, "commit", "-q", "-m", "lock")
    candidate = _lock(("demo", "2.0.0"))
    (repo / "uv.lock").write_text(candidate)
    index = repo / ".git" / "index"
    before = index.read_bytes()
    objects = tmp_path / "empty-objects"
    objects.mkdir()
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(objects))

    out = repo_facts.lock_diff(str(repo), ["uv.lock"])

    assert out["uv.lock"] == {"error": "HEAD baseline is not readable"}
    assert index.read_bytes() == before
    assert (repo / "uv.lock").read_text() == candidate


def test_unrecognized_lock_is_not_no_changes() -> None:
    """Unsupported or incomplete package fields cannot bypass classification."""
    with pytest.raises(ValueError, match="no readable package tables"):
        repo_facts.lock_changes("version = 1", "unreadable")
    with pytest.raises(ValueError, match="package name or version is not readable"):
        repo_facts.lock_changes(_lock(("demo", "1.0.0")), '[[package]]\nname = "demo"\n')
