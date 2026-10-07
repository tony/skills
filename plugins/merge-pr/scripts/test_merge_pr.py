"""Tests for merge_pr.py against a temp repo and a ``gh`` stub on PATH."""

# ruff: noqa: S101, INP001, S603, S607
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("merge_pr.py")
GH_STUB = """#!/bin/sh
case "$1 $2" in
  "pr view") cat "$STUB_DIR/pr-$3.json" ;;
  "pr merge") printf '%s\\n' "$@" >"$STUB_DIR/merge.args"
              for a in "$@"; do [ "$a" = -F ] && NEXT=1 && continue
                [ -n "$NEXT" ] && cp "$a" "$STUB_DIR/merge.body" && NEXT=; done ;;
esac
"""


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def _script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a repo with ``main`` plus a gh stub whose data lives in ``stub``."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.name", "demo")
    _git(work, "config", "user.email", "demo@example.invalid")
    _git(work, "remote", "add", "origin", "git@github.com:Acme/Widgets.git")
    (work / "a.txt").write_text("\n".join(map(str, range(1, 21))) + "\n")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-q", "-m", "init")
    stub = tmp_path / "stub"
    stub.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("STUB_DIR", str(stub))
    return work


def test_scope_matches_origin_by_slug(repo: Path) -> None:
    """A repo spec naming origin is local; any other is remote."""
    assert _script(repo, "scope").stdout == "local\n"
    assert _script(repo, "scope", "acme/widgets").stdout == "local\n"
    assert _script(repo, "scope", "other/repo").stdout == "remote\n"


def test_order_puts_stack_parent_first(repo: Path, tmp_path: Path) -> None:
    """A child given first is ordered after its parent."""
    for n, base, head in ((32, "stack-1", "stack-2"), (31, "main", "stack-1")):
        pr = {"number": n, "baseRefName": base, "headRefName": head, "headRefOid": f"oid{n}"}
        (tmp_path / "stub" / f"pr-{n}.json").write_text(json.dumps(pr))
    out = json.loads(_script(repo, "order", "32", "31").stdout)
    assert out["topology"] == "stack"
    assert out["order"] == [31, 32]
    assert out["trunk"] == "main"
    assert out["heads"]["31"] == "oid31"


def test_order_independent_keeps_given_order(repo: Path, tmp_path: Path) -> None:
    """Unrelated PRs keep the user's order."""
    for n in (7, 5):
        pr = {"number": n, "baseRefName": "main", "headRefName": f"b{n}", "headRefOid": "o"}
        (tmp_path / "stub" / f"pr-{n}.json").write_text(json.dumps(pr))
    out = json.loads(_script(repo, "order", "7", "5").stdout)
    assert (out["topology"], out["order"]) == ("independent", [7, 5])


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", f"add {name}")


def test_fingerprints_survive_a_clean_rebase(repo: Path) -> None:
    """Rebasing onto a moved base keeps patch ids; a changed commit is flagged."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "one.txt", "one\n")
    _commit(repo, "two.txt", "two\n")
    rec = _script(repo, "fingerprint", "record", "main..HEAD").stdout.strip()
    assert Path(rec).is_file()
    _git(repo, "checkout", "-q", "main")
    (repo / "a.txt").write_text("0\n" + (repo / "a.txt").read_text())
    _git(repo, "commit", "-q", "-am", "move base")
    _git(repo, "checkout", "-q", "feature")
    _git(repo, "rebase", "-q", "main")
    ok = _script(repo, "fingerprint", "verify", rec, "main..HEAD")
    assert (ok.returncode, ok.stdout) == (0, "ok\n")
    (repo / "two.txt").write_text("changed\n")
    _git(repo, "commit", "-q", "-a", "--amend", "--no-edit")
    bad = _script(repo, "fingerprint", "verify", rec, "main..HEAD")
    assert bad.returncode == 1
    assert bad.stdout.startswith("MISMATCH 2 ")
    tolerated = _script(repo, "fingerprint", "verify", rec, "main..HEAD", "--resolved", "two.txt")
    assert (tolerated.returncode, tolerated.stdout.startswith("resolved 2 ")) == (0, True)


def test_verify_fails_on_commit_count(repo: Path) -> None:
    """A different number of commits halts."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "one.txt", "one\n")
    rec = _script(repo, "fingerprint", "record", "main..HEAD").stdout.strip()
    _commit(repo, "two.txt", "two\n")
    out = _script(repo, "fingerprint", "verify", rec, "main..HEAD")
    assert out.returncode == 1
    assert out.stdout.startswith("count differs")


def test_merge_passes_hostile_message_as_arguments(repo: Path, tmp_path: Path) -> None:
    """Backticks, $(...) and a heredoc-like line reach gh unchanged."""
    path = _script(repo, "message-path").stdout.strip()
    subject = "fix: `rm -rf` $(id) (#9)"
    body = "line one\nMERGE_MSG_END\n$(touch pwned)\n"
    Path(path).write_text(f"{subject}\n\n{body}")
    done = _script(repo, "merge", "--message-file", path, "--", "9", "--squash")
    assert done.returncode == 0
    args = (tmp_path / "stub" / "merge.args").read_text().splitlines()
    assert args[:4] == ["pr", "merge", "9", "--squash"]
    assert args[args.index("-t") + 1] == subject
    assert (tmp_path / "stub" / "merge.body").read_text() == body
    assert not Path(path).exists()
    assert not (repo / "pwned").exists()


def test_merge_without_message_passes_flags_alone(repo: Path, tmp_path: Path) -> None:
    """No message file means no -t or -F."""
    _script(repo, "merge", "--", "9", "--rebase")
    args = (tmp_path / "stub" / "merge.args").read_text().splitlines()
    assert args == ["pr", "merge", "9", "--rebase"]
