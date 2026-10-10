"""Tests for pr_backup.py with ``gh`` replaced by a stub on PATH."""

# ruff: noqa: S101, INP001, S603, S607
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Every case drives CLI subprocesses against an owned Git repository.
pytestmark = pytest.mark.integration

SCRIPT = Path(__file__).with_name("pr_backup.py")
BODY = "## Summary\n\n- Add a parser\nline with trailing space \n\n"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a git repo whose PATH holds a gh stub that prints ``stub.json``."""
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    gh = stub_bin / "gh"
    gh.write_text(f"#!/bin/sh\ncat '{tmp_path}/stub.json'\n")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_bin}{os.pathsep}{os.environ['PATH']}")
    (tmp_path / "stub.json").write_text(json.dumps({"number": 17, "title": "Add it", "body": BODY}))
    return work


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_save_writes_verbatim_body(repo: Path) -> None:
    """The backup keeps the body byte for byte and prints its directory."""
    done = _run(repo, "save", "17")
    assert done.returncode == 0, done.stderr
    out = repo / done.stdout.strip()
    assert (out / "body.md").read_bytes().decode() == BODY
    assert (out / "title.txt").read_text() == "Add it"
    assert out.name.endswith("-pr17")


def test_check_detects_edit_since_backup(repo: Path) -> None:
    """Check passes on an unchanged body and fails once the body differs."""
    out = str(repo / _run(repo, "save", "17").stdout.strip())
    assert _run(repo, "check", out).returncode == 0
    (repo.parent / "stub.json").write_text(
        json.dumps({"number": 17, "title": "Add it", "body": BODY + "edited"})
    )
    done = _run(repo, "check", out)
    assert done.returncode == 1
    assert "changed" in done.stderr


def test_check_detects_title_edit_since_backup(repo: Path) -> None:
    """A title edited after the backup fails the check even when the body matches."""
    out = str(repo / _run(repo, "save", "17").stdout.strip())
    (repo.parent / "stub.json").write_text(
        json.dumps({"number": 17, "title": "Add it, edited", "body": BODY})
    )
    done = _run(repo, "check", out)
    assert done.returncode == 1
    assert "title" in done.stderr


def test_save_falls_back_when_git_dir_is_unwritable(repo: Path) -> None:
    """An unwritable pr-backups path falls back to a temp directory."""
    (repo / ".git" / "pr-backups").write_text("blocked")
    done = _run(repo, "save", "17")
    assert done.returncode == 0, done.stderr
    out = Path(done.stdout.strip())
    assert (out / "body.md").read_bytes().decode() == BODY
    assert ".git" not in out.parts


def test_check_needs_only_the_backup_files(repo: Path) -> None:
    """Check runs before the new text is staged, so no .new file is required."""
    out = Path(_run(repo, "save", "17").stdout.strip())
    assert sorted(f.name for f in (repo / out).iterdir()) == ["body.md", "number.txt", "title.txt"]
    assert _run(repo, "check", str(repo / out)).returncode == 0


def test_verify_reads_the_edit_back(repo: Path) -> None:
    """Verify passes when the PR carries the edit files and fails when it does not."""
    out = str(repo / _run(repo, "save", "17").stdout.strip())
    body = repo.parent / "body.new.md"
    title = repo.parent / "title.new.txt"
    body.write_text("## Summary\n\n- New\n")
    title.write_text("New title\n")
    assert _run(repo, "verify", out, str(body), str(title)).returncode == 1
    (repo.parent / "stub.json").write_text(
        json.dumps({"number": 17, "title": "New title", "body": "## Summary\r\n\r\n- New\r\n"})
    )
    assert _run(repo, "verify", out, str(body), str(title)).returncode == 0
