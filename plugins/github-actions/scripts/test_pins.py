"""Tests for pins.py with ``gh`` replaced by a stub on PATH."""

# ruff: noqa: S101, INP001, S603, S607
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("pins.py")

GH_STUB = """#!/bin/sh
case "$*" in
  "repo view acme/one"*) echo main ;;
  "repo view acme/two"*) echo trunk ;;
  "api repos/actions/checkout/releases"*) printf 'v4.2.2\\nv4.0.0\\nv3.0.0\\nv5.0.0\\n' ;;
  "api repos/actions/checkout/git/ref/tags/v4") echo '{}' ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
"""


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _make_repo(root: Path, slug: str, branch: str, ref: str) -> Path:
    """Create a clone of a bare remote pinning checkout at ``ref``."""
    name = slug.split("/")[1]
    bare = root / f"{name}-bare.git"
    _git("init", "-q", "--bare", str(bare), cwd=root)
    work = root / name
    work.mkdir()
    _git("init", "-q", "-b", branch, cwd=work)
    _git("remote", "add", "origin", f"https://github.com/{slug}.git", cwd=work)
    wf = work / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(
        f"steps:\n  - uses: actions/checkout@{ref}\n  - uses: ./local\n",
    )
    (work / ".github" / "README.md").write_text("  - uses: not/a-workflow@v1\n")
    _git("add", ".", cwd=work)
    _git(
        "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "ci",
        cwd=work,
    )  # fmt: skip
    _git(
        "config", f"url.{bare}.insteadOf", f"https://github.com/{slug}.git",
        cwd=work,
    )  # fmt: skip
    _git("push", "-q", "origin", branch, cwd=work)
    _git("fetch", "-q", "origin", cwd=work)
    return work


@pytest.fixture
def stub_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put a gh stub first on PATH."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    gh = stub_bin / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub_bin}{os.pathsep}{os.environ['PATH']}")


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )  # fmt: skip


@pytest.mark.usefixtures("stub_path")
def test_inventory_reads_each_repo_by_its_own_path(
    tmp_path: Path,
) -> None:
    """Two clones with different default branches are read from their own trees."""
    one = _make_repo(tmp_path, "acme/one", "main", "v3")
    two = _make_repo(tmp_path, "acme/two", "trunk", "v2")
    done = _run("inventory", str(one), str(two), cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    first, second = (json.loads(x) for x in done.stdout.splitlines())
    assert (first["slug"], first["default"]) == ("acme/one", "main")
    assert (second["slug"], second["default"]) == ("acme/two", "trunk")
    for rec, ref in ((first, "v3"), (second, "v2")):
        actions = [p for p in rec["pins"] if p["kind"] == "action"]
        assert [(p["action"], p["ref"]) for p in actions] == [("actions/checkout", ref)]
        assert rec["files"] == [".github/workflows/ci.yml"]
    assert [p["kind"] for p in first["pins"]] == ["action", "local"]


@pytest.mark.usefixtures("stub_path")
def test_majors_lists_first_release_of_each_major(
    tmp_path: Path,
) -> None:
    """Majors above the pin and at or below the target print in order."""
    done = _run("majors", "actions/checkout", "v3", "v5", cwd=tmp_path)
    assert done.stdout.split() == ["v4.0.0", "v5.0.0"]


@pytest.mark.usefixtures("stub_path")
def test_tag_exit_status(
    tmp_path: Path,
) -> None:
    """A missing tag exits 1; an existing one exits 0."""
    assert _run("tag", "actions/checkout", "v4", cwd=tmp_path).returncode == 0
    assert _run("tag", "actions/checkout", "v99", cwd=tmp_path).returncode == 1
