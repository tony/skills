"""Tests for repo_facts.py against throwaway repositories."""

# ruff: noqa: S101, S603, S607, INP001, SLF001, PLR2004
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
        "mise.toml": {"node": "20", "npm:prettier": "3.3.0", "python": ["3.12", "3.11"]},
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


def test_pin_arrays_keep_every_version() -> None:
    """A support set is not collapsed to its first entry; unknown syntax is reported."""
    text = (
        "[tools]\n"
        'node = { version = "22", os = ["linux"] }  # tracked\n'
        "python = [\n"
        '  "3.12",  # newest\n'
        "  '3.11',\n"
        "]\n"
        "[tools.go]\n"
    )

    tools, understood = repo_facts._mise_tools(text)  # pyright: ignore[reportPrivateUsage]

    assert tools == {"node": "22", "python": ["3.12", "3.11"]}
    assert understood is False
    assert repo_facts._mise_tools("[tools]\nnode = latest\n")[1] is False  # pyright: ignore[reportPrivateUsage]


@pytest.mark.integration
def test_unreadable_or_malformed_pins_are_failed_not_absent(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreadable or unparsed pin files are named in failed, not treated as absent."""
    repo = _make(tmp_path)
    (repo / "package.json").write_text("{not json")
    (repo / ".tool-versions").write_text("python 3.12 3.11\nnodejs\n")
    _git(repo, "commit", "-qam", "malformed")
    _git(repo, "push", "-q", "origin", "main")

    out = repo_facts.facts(str(repo))

    assert out["failed"] == [".tool-versions", "package.json"]
    pins = cast("dict[str, object]", out["pins"])
    assert "package.json" not in pins
    assert pins["go.mod"] == {"go": "1.22", "toolchain": "go1.22.3"}

    objects = tmp_path / "empty-objects"
    objects.mkdir()
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(objects))
    unreadable = repo_facts.facts(str(repo))
    assert "go.mod" in cast("list[str]", unreadable["failed"])
    assert unreadable["pins"] == {}


@pytest.mark.integration
def test_local_default_ahead_of_remote_is_reported(tmp_path: pathlib.Path) -> None:
    """A local default ahead of the remote is the base, and its unpushed commits are surfaced."""
    repo = _make(tmp_path)
    _git(repo, "remote", "set-head", "origin", "main")
    (repo / "f").write_text("x")
    _git(repo, "add", "f")
    _git(repo, "commit", "-q", "-m", "local only")

    out = repo_facts.facts(str(repo))

    assert out["ahead_remote"] == 1
    assert out["pins_ref"] == "main"
    assert out["behind_remote"] == 0


@pytest.mark.integration
def test_lock_diff_finds_nested_locks_and_new_locks(tmp_path: pathlib.Path) -> None:
    """Tracked locks at any depth are compared; a lock absent from HEAD is new, not unreadable."""
    repo = _make(tmp_path)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "uv.lock").write_text(_lock(("demo", "1.0.0")))
    _git(repo, "add", "pkg")
    _git(repo, "commit", "-q", "-m", "nested lock")
    (repo / "pkg" / "uv.lock").write_text(_lock(("demo", "2.0.0")))
    (repo / "Cargo.lock").write_text(_lock(("demo", "1.0.0")))

    out = repo_facts.lock_diff(str(repo), [])

    assert out["pkg/uv.lock"] == {
        "majors": [{"name": "demo", "from": ["1.0.0"], "to": ["2.0.0"]}],
        "in_range": [],
    }
    assert out["Cargo.lock"] == {"new": True}


def test_manifest_diff_catches_zero_x_minor_and_unclassified_ranges() -> None:
    """A 0.x minor in a range edit is a major; ranges naming no version are unclassified."""
    old = (
        '{"dependencies": {"a": "^0.1.0", "b": "^1.2.3", "c": "workspace:*"},'
        ' "devDependencies": {"d": "~2.0.0"}}'
    )
    new = (
        '{"dependencies": {"a": "^0.2.1", "b": "^1.9.0", "c": "latest"},'
        ' "devDependencies": {"d": "~3.0.0", "e": "^1.0.0"}}'
    )

    out = repo_facts.manifest_changes(old, new)

    assert [m["name"] for m in out["majors"]] == ["a", "d"]
    assert [m["name"] for m in out["in_range"]] == ["b", "e"]
    assert [m["name"] for m in out["unclassified"]] == ["c"]


def test_unrecognized_version_cannot_pass_as_zero_series() -> None:
    """A version with no leading number stops classification instead of reading as 0.0."""
    with pytest.raises(ValueError, match="unrecognized version"):
        repo_facts.lock_changes(_lock(("demo", "1.0.0")), _lock(("demo", "main")))


def test_lock_changes_reads_uv_lock_as_written_by_uv() -> None:
    """Fields uv writes around name and version (sources, wheels) do not hide a package."""
    block = (
        '[[package]]\nname = "requests"\nversion = "{v}"\n'
        'source = {{ registry = "https://pypi.org/simple" }}\n'
        'dependencies = [\n    {{ name = "idna" }},\n]\n'
        'sdist = {{ url = "https://example.invalid/r.tar.gz", hash = "sha256:00", size = 1 }}\n'
        "wheels = [\n"
        '    {{ url = "https://example.invalid/r.whl", hash = "sha256:00", size = 1 }},\n]\n'
    )
    head = 'version = 1\nrevision = 3\nrequires-python = ">=3.9"\n\n'

    out = repo_facts.lock_changes(head + block.format(v="2.31.0"), head + block.format(v="3.0.0"))

    assert out["majors"] == [{"name": "requests", "from": ["2.31.0"], "to": ["3.0.0"]}]


def test_virtual_project_without_version_is_not_an_error() -> None:
    """Uv writes no version for a dynamic-version project; the lock still classifies."""
    virtual = '\n[[package]]\nname = "demo"\nsource = { virtual = "." }\n'
    out = repo_facts.lock_changes(
        _lock(("requests", "2.31.0")) + virtual, _lock(("requests", "3.0.0")) + virtual
    )

    assert [m["name"] for m in out["majors"]] == ["requests"]
    assert out["in_range"] == []


def test_widened_ceiling_is_unclassified() -> None:
    """A range edited without moving its first version is not silently unchanged."""
    out = repo_facts.manifest_changes(
        '{"dependencies": {"a": ">=1 <2"}}', '{"dependencies": {"a": ">=1 <3"}}'
    )

    assert [m["name"] for m in out["unclassified"]] == ["a"]


@pytest.mark.integration
def test_pins_cover_nested_files_and_every_python_version_line(tmp_path: pathlib.Path) -> None:
    """Nested pin files are keyed by path; a multi-line .python-version keeps every line."""
    repo = _make(tmp_path)
    (repo / ".python-version").write_text("3.12.1\n3.11.4\n")
    (repo / ".node-version").write_text("20.1.0\n")
    (repo / "sub").mkdir()
    (repo / "sub" / ".tool-versions").write_text("just 1.0.0\n")
    (repo / "sub" / "package.json").write_text('{"engines": {"node": ">=20"}}')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "more pins")
    _git(repo, "push", "-q", "origin", "main")

    pins = cast("dict[str, object]", repo_facts.facts(str(repo))["pins"])

    assert pins[".python-version"] == ["3.12.1", "3.11.4"]
    assert pins[".node-version"] == "20.1.0"
    assert pins["sub/.tool-versions"] == {"just": "1.0.0"}
    assert pins["sub/package.json"] == {"engines": {"node": ">=20"}}


def test_main_usage_and_exit_codes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Help exits 0, bad usage 2, and a result carrying an error 1 with a stderr reason."""
    assert repo_facts.main(["--help"]) == 0
    assert capsys.readouterr().out.startswith("usage: repo_facts.py")
    assert repo_facts.main(["--bogus"]) == 2
    assert "unknown option --bogus" in capsys.readouterr().err
    assert repo_facts.main(["--lock-diff"]) == 2
    assert "--lock-diff takes" in capsys.readouterr().err
    assert repo_facts.main([str(tmp_path / "missing")]) == 1
    captured = capsys.readouterr()
    assert "not a directory" in captured.out
    assert "carry an error" in captured.err


@pytest.mark.integration
def test_pin_sites_free_branch_and_issue_branch(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Pin sites list whole-word hits; a taken branch name gets a suffix; slugs are ASCII."""
    repo = _make(tmp_path)
    (repo / "pyproject.toml").write_text('dependencies = ["requests>=2"]\n# requests-mock\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "dep")
    _git(repo, "branch", "wip/deps")
    _git(repo, "branch", "wip/deps-2")

    sites = cast("list[dict[str, object]]", repo_facts.pin_sites(str(repo), "requests")["sites"])
    assert [(s["file"], s["line"]) for s in sites] == [("pyproject.toml", 1), ("pyproject.toml", 2)]
    assert repo_facts.pin_sites(str(repo), "requests")["total"] == len(sites)
    assert repo_facts.pin_sites(str(repo), "absent-name")["sites"] == []
    assert repo_facts.free_branch(str(repo), "wip/deps")["branch"] == "wip/deps-3"
    assert repo_facts.free_branch(str(repo), "wip/new")["branch"] == "wip/new"
    assert repo_facts.main(["--issue-branch", "42", "Bump uv: 0.7 -> 0.8!"]) == 0
    assert '"42-bump-uv-0-7-0-8"' in capsys.readouterr().out


def _clone_row(rows: list[dict[str, object]], path: pathlib.Path) -> dict[str, object]:
    return next(r for r in rows if r["path"] == str(path.resolve()))


@pytest.mark.integration
def test_scope_marks_worktree_owner_and_duplicate_exclusions(tmp_path: pathlib.Path) -> None:
    """A fleet walk keeps one clone per remote and says which rule dropped each other repo."""
    root = tmp_path / "fleet"
    root.mkdir()
    repos: dict[str, str] = {
        "a": "git@github.com:mine/a.git",
        "a-again": "https://github.com/mine/a",
        "b": "git@github.com:other/b.git",
    }
    for name, url in repos.items():
        repo = root / name
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "me@example.com")
        _git(repo, "config", "user.name", "me")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "x")
        _git(repo, "remote", "add", "origin", url)
    _git(root / "a", "worktree", "add", "-q", "-b", "wtb", str(root / "a-wt"))

    rows = repo_facts.scope([str(root)], [], ["Mine"])

    assert _clone_row(rows, root / "a")["excluded"] is None
    assert _clone_row(rows, root / "a")["email_in_recent"] is True
    assert _clone_row(rows, root / "a-again")["excluded"] == "duplicate"
    assert _clone_row(rows, root / "b")["excluded"] == "owner"
    wt = _clone_row(rows, root / "a-wt")
    assert wt["excluded"] == "worktree"
    assert wt["clone"] == str((root / "a").resolve())


@pytest.mark.integration
def test_scope_unresolved_repo_and_email_mismatch(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slug that matches nothing is an error row; foreign authors do not match the email."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "me@example.com")
    _git(
        repo,
        "-c",
        "user.email=bot@example.com",
        "-c",
        "user.name=ci[bot]",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "x",
    )

    rows = repo_facts.scope([], [str(repo), "nobody/nothing"], [])

    assert _clone_row(rows, repo)["email_in_recent"] is False
    assert _clone_row(rows, repo)["bot_only"] is True
    assert {"path": "nobody/nothing", "error": "repository not found"} in rows
    assert repo_facts.main(["--scope", "--repo", "nobody/nothing"]) == 1
    assert repo_facts.main(["--scope", "--bogus"]) == 2
    capsys.readouterr()


def test_issue_branch_folds_accents() -> None:
    """Accented letters fold to ASCII; letters with no ASCII form drop out."""
    assert repo_facts.issue_branch("7", "Mise à jour: Café 日本")["branch"] == "7-mise-a-jour-cafe"
