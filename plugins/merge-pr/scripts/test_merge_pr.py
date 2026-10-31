"""Tests for merge_pr.py against a temp repo and a ``gh`` stub on PATH."""

# ruff: noqa: S101, INP001, S603, S607, SLF001
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import merge_pr
import pytest

pytestmark = pytest.mark.integration(reason="uses an owned Git repository and the merge-pr CLI")

SCRIPT = Path(__file__).with_name("merge_pr.py")
PIN = ("--match-head-commit", "abc1234")
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
    assert set(out) == {"topology", "order", "trunk", "parents"}


def test_order_independent_keeps_given_order(repo: Path, tmp_path: Path) -> None:
    """Unrelated PRs keep the user's order."""
    for n in (7, 5):
        pr = {"number": n, "baseRefName": "main", "headRefName": f"b{n}", "headRefOid": "o"}
        (tmp_path / "stub" / f"pr-{n}.json").write_text(json.dumps(pr))
    out = json.loads(_script(repo, "order", "7", "5").stdout)
    assert (out["topology"], out["order"]) == ("independent", [7, 5])


def test_order_ignores_fork_head_named_like_base(repo: Path, tmp_path: Path) -> None:
    """A fork PR from its own ``main`` is not the parent of PRs based on ``main``."""
    for n, fork in ((1, True), (2, False)):
        pr = {
            "number": n,
            "baseRefName": "main",
            "headRefName": "main" if fork else "feat",
            "headRefOid": "o",
            "isCrossRepository": fork,
        }
        (tmp_path / "stub" / f"pr-{n}.json").write_text(json.dumps(pr))
    out = json.loads(_script(repo, "order", "1", "2").stdout)
    assert (out["topology"], out["order"]) == ("independent", [1, 2])


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
    assert Path(rec).is_absolute()
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


def test_record_falls_back_when_git_path_is_unwritable(repo: Path) -> None:
    """A file where the record directory belongs forces the temp-dir fallback."""
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "one.txt", "one\n")
    git_path = Path(_git(repo, "rev-parse", "--absolute-git-dir").strip())
    (git_path / "merge-pr-fingerprints").write_text("blocked\n")
    out = _script(repo, "fingerprint", "record", "main..HEAD")
    assert out.returncode == 0
    rec = Path(out.stdout.strip())
    assert rec.is_file()
    assert git_path not in rec.parents
    assert _script(repo, "fingerprint", "verify", str(rec), "main..HEAD").returncode == 0


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
    done = _script(repo, "merge", "--message-file", path, "--", "9", "--squash", *PIN)
    assert done.returncode == 0
    args = (tmp_path / "stub" / "merge.args").read_text().splitlines()
    assert args[:4] == ["pr", "merge", "9", "--squash"]
    assert args[args.index("-t") + 1] == subject
    assert (tmp_path / "stub" / "merge.body").read_text() == body
    assert not Path(path).exists()
    assert not (repo / "pwned").exists()


def test_merge_without_message_passes_flags_alone(repo: Path, tmp_path: Path) -> None:
    """No message file means no -t or -F."""
    _script(repo, "merge", "--", "9", "--rebase", *PIN)
    args = (tmp_path / "stub" / "merge.args").read_text().splitlines()
    assert args == ["pr", "merge", "9", "--rebase", *PIN]


def test_merge_refuses_without_head_pin(repo: Path, tmp_path: Path) -> None:
    """A merge that does not pin the verified head never reaches gh."""
    done = _script(repo, "merge", "--", "9", "--squash")
    assert done.returncode != 0
    assert not (tmp_path / "stub" / "merge.args").exists()


def test_resolved_waiver_covers_only_the_named_path(repo: Path) -> None:
    """An edit to another path in the same commit stays a mismatch."""
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "one.txt").write_text("one\n")
    (repo / "two.txt").write_text("two\n")
    _git(repo, "add", "one.txt", "two.txt")
    _git(repo, "commit", "-q", "-m", "add both")
    rec = _script(repo, "fingerprint", "record", "main..HEAD").stdout.strip()
    (repo / "one.txt").write_text("one, resolved\n")
    (repo / "two.txt").write_text("two, sneaked in\n")
    _git(repo, "commit", "-q", "-a", "--amend", "--no-edit")
    only_one = _script(repo, "fingerprint", "verify", rec, "main..HEAD", "--resolved", "one.txt")
    assert only_one.returncode == 1
    assert only_one.stdout.startswith("MISMATCH 1 ")
    both = _script(
        repo,
        "fingerprint",
        "verify",
        rec,
        "main..HEAD",
        "--resolved",
        "one.txt",
        "--resolved",
        "two.txt",
    )
    assert (both.returncode, both.stdout.startswith("resolved 1 ")) == (0, True)


_TIMED_GH = """\
#!/bin/sh
echo "start $3" >> "$GH_LOG"
case "$3" in
  2) echo "boom 2" >&2; exit 1 ;;
  3) echo "boom 3" >&2; exit 1 ;;
esac
sleep 0.3
echo "end $3" >> "$GH_LOG"
printf '{}'
"""


@pytest.fixture
def timed_gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put a ``gh`` on PATH that logs when each ``pr view`` starts and ends."""
    bin_dir = tmp_path / "timed-bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(_TIMED_GH)
    gh.chmod(0o755)
    log = tmp_path / "gh.log"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_LOG", str(log))
    return log


def test_view_all_reads_prs_concurrently(timed_gh: Path) -> None:
    """Both reads start before either ends, and results keep the given order."""
    results = asyncio.run(merge_pr._view_all("", ["7", "5"]))
    assert [code for code, _, _ in results] == [0, 0]
    events = timed_gh.read_text().split("\n")
    assert sorted(events[:2]) == ["start 5", "start 7"]


@pytest.mark.usefixtures("timed_gh")
def test_order_reports_first_failure_in_given_order(capsys: pytest.CaptureFixture[str]) -> None:
    """With two failing reads, only the earlier one in the given order is reported."""
    with pytest.raises(SystemExit) as exit_info:
        merge_pr.order("", ["1", "3", "2"])
    assert exit_info.value.code == 1
    assert capsys.readouterr().err == "boom 3\n"
