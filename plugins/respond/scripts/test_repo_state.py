"""Tests for repo_state.py against temporary repositories and a stubbed ``gh``."""

# pyright: reportAny=false
# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportUnusedCallResult=false, reportPrivateUsage=false
import json
import subprocess
from typing import TYPE_CHECKING

import repo_state  # pyright: ignore[reportImplicitRelativeImport]
from ghcli import GhError  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _commit(repo: Path, name: str, text: str = "x\n") -> None:
    (repo / name).write_text(text)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"add {name}")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _commit(repo, "a.txt", "one\n")
    return repo


def _with_origin(repo: Path, tmp_path: Path, owner: str = "acme", name: str = "widgets") -> Path:
    bare = tmp_path / owner / f"{name}.git"
    bare.parent.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "origin", "main")
    return bare


def _gh_json(reply: object, readback: str = "") -> object:
    def gh(*args: str, **_kw: bool) -> str:
        if readback and "--jq" in args and "headRefOid" in args:
            return readback + "\n"
        return reply if isinstance(reply, str) else json.dumps(reply)

    return gh


def _run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = repo_state.main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_guard_refuses_a_repository_rooted_at_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A top level equal to, or above, the home directory halts with code 3."""
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(repo))
    code, _out, err = _run(["guard"], capsys)
    assert code == 3
    assert "home directory" in err
    monkeypatch.setenv("HOME", str(repo / "sub"))
    assert _run(["guard"], capsys)[0] == 3  # the repository contains home


def test_guard_allows_a_project_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repository below home passes."""
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    assert _run(["guard"], capsys)[0] == 0


def test_changes_lists_files_inside_new_directories_unquoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """New directories expand to files; odd names arrive verbatim, renames list both paths."""
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "mod one.py").write_text("x\n")
    (repo / "café.txt").write_text("x\n")
    _git(repo, "mv", "a.txt", "b.txt")
    code, out, _err = _run(["changes"], capsys)
    assert code == 0
    assert json.loads(out) == ["a.txt", "b.txt", "café.txt", "pkg/mod one.py"]


def test_revert_restores_tracked_and_removes_new_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Edits, staged additions, and untracked files all return to ``HEAD``."""
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    (repo / "a.txt").write_text("changed\n")
    (repo / "staged.txt").write_text("x\n")
    _git(repo, "add", "staged.txt")
    (repo / "loose.txt").write_text("x\n")
    assert _run(["revert"], capsys)[0] == 0
    assert (repo / "a.txt").read_text() == "one\n"
    assert not (repo / "staged.txt").exists()
    assert not (repo / "loose.txt").exists()
    assert _git(repo, "status", "--porcelain") == ""


def test_base_comes_from_the_pull_request_when_origin_head_is_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``baseRefName`` resolves ``origin/<base>`` though ``origin/HEAD`` does not exist."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    _git(repo, "branch", "-q", "develop")
    _git(repo, "push", "-q", "origin", "develop")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(repo_state, "gh", _gh_json("develop\n"))
    code, out, _err = _run(["base", "--pr", "7"], capsys)
    assert code == 0
    got = json.loads(out)
    assert (got["ref"], got["source"]) == ("origin/develop", "pr")
    assert got["sha"] == _git(repo, "rev-parse", "HEAD").strip()


def test_base_falls_back_to_trunk_without_gh_and_origin_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With ``gh`` failing and ``origin/HEAD`` unset, ``origin/main`` still resolves."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    monkeypatch.chdir(repo)

    def failing(*_a: str, **_k: bool) -> str:
        msg = "gh auth login"
        raise GhError(msg)

    monkeypatch.setattr(repo_state, "gh", failing)
    code, out, _err = _run(["base"], capsys)
    assert code == 0
    assert json.loads(out)["ref"] == "origin/main"


def test_base_flag_wins_and_unresolved_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--base`` overrides everything; a name that resolves nowhere is refused."""
    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(repo_state, "gh", _gh_json("main\n"))
    _git(repo, "branch", "-q", "parent")
    code, out, _err = _run(["base", "--base", "parent"], capsys)
    assert (code, json.loads(out)["source"]) == (0, "flag")
    code, _out, err = _run(["base", "--base", "nope"], capsys)
    assert code == 1
    assert "no base resolved" in err


def test_base_fetch_refreshes_the_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--fetch`` moves ``origin/main`` before the merge-base is taken."""
    repo = _repo(tmp_path)
    bare = _with_origin(repo, tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True)
    _git(other, "config", "user.email", "t@example.com")
    _git(other, "config", "user.name", "t")
    _commit(other, "later.txt")
    _git(other, "push", "-q", "origin", "main")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(repo_state, "gh", _gh_json("main\n"))
    out = json.loads(_run(["base", "--pr", "7", "--fetch"], capsys)[1])
    assert out["fetched"] is True
    assert (
        _git(repo, "rev-parse", "origin/main").strip() == _git(other, "rev-parse", "HEAD").strip()
    )


def test_base_for_a_named_pr_that_cannot_be_read_exits_four(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed lookup never degrades to the trunk for a stacked pull request."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    monkeypatch.chdir(repo)

    def failing(*_a: str, **_k: bool) -> str:
        msg = "HTTP 502"
        raise GhError(msg)

    monkeypatch.setattr(repo_state, "gh", failing)
    code, out, err = _run(["base", "--pr", "7"], capsys)
    assert (code, out) == (4, "")
    assert "HTTP 502" in err


def test_fetch_refreshes_every_remote_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A base branch that exists only on ``origin`` resolves though ``upstream`` sorts first."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    up = tmp_path / "up" / "widgets.git"
    up.parent.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(up)], check=True)
    _git(repo, "remote", "add", "upstream", str(up))
    _git(repo, "push", "-q", "upstream", "main")
    _git(repo, "branch", "-q", "stack")
    _git(repo, "push", "-q", "origin", "stack")
    _git(repo, "update-ref", "-d", "refs/remotes/origin/stack")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(repo_state, "gh", _gh_json("stack\n"))
    got = json.loads(_run(["base", "--pr", "7", "--fetch"], capsys)[1])
    assert (got["ref"], got["source"]) == ("origin/stack", "pr")


def test_since_mark_names_the_paths_a_gate_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A gate that edits a clean or dirty file, or adds one, is reported; idle paths are not."""
    repo = _repo(tmp_path)
    _commit(repo, "b.txt", "beta\n")
    monkeypatch.chdir(repo)
    (repo / "fix.txt").write_text("fix\n")
    assert _run(["mark"], capsys)[0] == 0
    assert json.loads(_run(["since-mark"], capsys)[1]) == []
    (repo / "b.txt").write_text("BETA\n")
    (repo / "fix.txt").write_text("FIX\n")
    (repo / "gen.txt").write_text("x\n")
    assert json.loads(_run(["since-mark"], capsys)[1]) == ["b.txt", "fix.txt", "gen.txt"]


def test_since_mark_without_a_mark_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """since-mark before any mark exits 1 with a reason, not a traceback."""
    monkeypatch.chdir(_repo(tmp_path))
    code, _, err = _run(["since-mark"], capsys)
    assert (code, "run mark before the gate" in err) == (1, True)


def _branch_with_commits(repo: Path, tmp_path: Path) -> None:
    _with_origin(repo, tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "f1.txt")
    _commit(repo, "f2.txt")


def test_fixup_check_accepts_an_unpushed_commit_on_a_linear_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The happy path prints the full SHA."""
    repo = _repo(tmp_path)
    _branch_with_commits(repo, tmp_path)
    monkeypatch.chdir(repo)
    sha = _git(repo, "rev-parse", "HEAD~1").strip()
    code, out, _err = _run(["fixup-check", sha, "--base", "origin/main"], capsys)
    assert (code, json.loads(out)["commit"]) == (0, sha)


def test_fixup_check_refuses_when_the_range_holds_a_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A merge elsewhere in ``<base>..HEAD`` would be flattened by autosquash."""
    repo = _repo(tmp_path)
    _branch_with_commits(repo, tmp_path)
    _git(repo, "checkout", "-q", "-b", "side", "origin/main")
    _commit(repo, "s.txt")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side")
    monkeypatch.chdir(repo)
    sha = _git(repo, "rev-parse", "HEAD~2").strip()
    code, _out, err = _run(["fixup-check", sha, "--base", "origin/main"], capsys)
    assert code == 1
    assert "merge commit" in err


def test_fixup_check_refuses_a_pushed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A commit any remote-tracking ref contains is shared history."""
    repo = _repo(tmp_path)
    _branch_with_commits(repo, tmp_path)
    _git(repo, "push", "-q", "origin", "feature")
    _commit(repo, "f3.txt")
    monkeypatch.chdir(repo)
    sha = _git(repo, "rev-parse", "HEAD~1").strip()
    code, _out, err = _run(["fixup-check", sha, "--base", "origin/main"], capsys)
    assert code == 1
    assert "is pushed" in err
    unpushed = _git(repo, "rev-parse", "HEAD").strip()
    assert _run(["fixup-check", unpushed, "--base", "origin/main"], capsys)[0] == 0


def test_fixup_check_refuses_a_commit_outside_the_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A trunk commit is not this branch's to rewrite."""
    repo = _repo(tmp_path)
    _branch_with_commits(repo, tmp_path)
    monkeypatch.chdir(repo)
    sha = _git(repo, "rev-parse", "origin/main").strip()
    code, _out, err = _run(["fixup-check", sha, "--base", "origin/main"], capsys)
    assert code == 1
    assert "not in origin/main..HEAD" in err


def _pr_head(oid: str, *, cross: bool = False, owner: str = "acme") -> dict[str, object]:
    return {
        "headRefName": "feature",
        "headRefOid": oid,
        "headRepository": {"name": "widgets"},
        "headRepositoryOwner": {"login": owner},
        "isCrossRepository": cross,
    }


def test_push_goes_to_the_remote_and_branch_the_pull_request_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no upstream set, ``push`` still pushes ``HEAD`` to the PR's head branch."""
    repo = _repo(tmp_path)
    bare = _with_origin(repo, tmp_path)
    _git(repo, "checkout", "-q", "-b", "local-name")
    _commit(repo, "f1.txt")
    base_oid = _git(repo, "rev-parse", "main").strip()
    monkeypatch.chdir(repo)
    local = _git(repo, "rev-parse", "HEAD").strip()
    monkeypatch.setattr(repo_state, "gh", _gh_json(_pr_head(base_oid), readback=local))
    code, out, _err = _run(["push", "7"], capsys)
    assert code == 0
    got = json.loads(out)
    assert (got["pushed"], got["head"]) == (True, local)
    assert _git(bare, "rev-parse", "refs/heads/feature").strip() == local


def test_push_refuses_when_the_read_back_head_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pull request must report the pushed head after the push."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    base_oid = _git(repo, "rev-parse", "HEAD").strip()
    _commit(repo, "f1.txt")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(repo_state, "gh", _gh_json(_pr_head(base_oid), readback=base_oid))
    code, _out, err = _run(["push", "7"], capsys)
    assert code == 1
    assert "after the push" in err


def test_push_matches_a_fork_remote_by_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A cross-repository pull request pushes to the remote that points at the fork."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path, "upstream-org", "widgets")
    fork = tmp_path / "me" / "widgets.git"
    fork.parent.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(fork)], check=True)
    _git(repo, "remote", "add", "fork", str(fork))
    _commit(repo, "f1.txt")
    monkeypatch.chdir(repo)
    base_oid = _git(repo, "rev-parse", "HEAD~1").strip()
    monkeypatch.setattr(repo_state, "gh", _gh_json(_pr_head(base_oid, cross=True, owner="me")))
    target = json.loads(_run(["push-target", "7"], capsys)[1])
    assert (target["remote"], target["state"]) == ("fork", "ahead")


def test_push_refuses_a_cross_repository_pr_with_no_matching_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Falling back to ``origin`` would push to the wrong repository."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    monkeypatch.chdir(repo)
    oid = _git(repo, "rev-parse", "HEAD").strip()
    monkeypatch.setattr(repo_state, "gh", _gh_json(_pr_head(oid, cross=True, owner="stranger")))
    code, _out, err = _run(["push", "7"], capsys)
    assert code == 1
    assert "no remote points at stranger/widgets" in err


def test_push_refuses_when_behind_and_never_forces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pull request head ahead of the local branch needs a human, not a force."""
    repo = _repo(tmp_path)
    bare = _with_origin(repo, tmp_path)
    _commit(repo, "f1.txt")
    ahead_oid = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(repo_state, "gh", _gh_json(_pr_head(ahead_oid)))
    code, _out, err = _run(["push", "7"], capsys)
    assert code == 1
    assert "behind" in err
    assert _git(bare, "branch", "--list", "feature") == ""


def test_push_up_to_date_pushes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A local head equal to the pull request head is reported, not pushed."""
    repo = _repo(tmp_path)
    _with_origin(repo, tmp_path)
    monkeypatch.chdir(repo)
    oid = _git(repo, "rev-parse", "HEAD").strip()
    monkeypatch.setattr(repo_state, "gh", _gh_json(_pr_head(oid)))
    out = json.loads(_run(["push", "7"], capsys)[1])
    assert out["state"] == "up-to-date"
    assert "pushed" not in out
