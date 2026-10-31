"""Tests for diff_gate.py against temporary repositories."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

import os
import stat
import subprocess
import sys
from pathlib import Path

import diff_gate  # pyright: ignore[reportImplicitRelativeImport]
import pytest

SCRIPT = Path(__file__).resolve().parent / "diff_gate.py"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}
PATTERNS = ["--pattern", "**/test_*.py", "--pattern", "tests/**"]


@pytest.mark.parametrize(
    ("returncode", "diagnostic"),
    [
        (0, "warning: could not open directory 'tests/': Permission denied\n"),
        (128, "fatal: unable to read index\n"),
        (128, ""),
    ],
)
def test_git_diagnostics_or_failure_stop_observation(
    monkeypatch: pytest.MonkeyPatch, returncode: int, diagnostic: str
) -> None:
    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["git"], returncode, stdout="", stderr=diagnostic)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(SystemExit) as error:
        diff_gate.changed_paths()
    assert str(error.value) == f"git status incomplete (exit {returncode}): {diagnostic.strip()}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, env=ENV, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "test_a.py").write_text("t = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, env=ENV, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, env=ENV, check=True)
    return tmp_path


def gate(repo: Path, mode: str) -> tuple[int, list[str]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), mode, *PATTERNS],
        cwd=repo,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stdout.split()


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
def test_clean_tree_passes(repo: Path) -> None:
    assert gate(repo, "test-only") == (0, [])
    assert gate(repo, "source-only") == (0, [])


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
def test_test_only_flags_source_and_untracked_source(repo: Path) -> None:
    (repo / "test_a.py").write_text("t = 2\n")
    (repo / "a.py").write_text("x = 2\n")
    (repo / "b.py").write_text("y = 1\n")
    assert gate(repo, "test-only") == (1, ["a.py", "b.py"])


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
def test_source_only_flags_modified_and_untracked_tests(repo: Path) -> None:
    (repo / "a.py").write_text("x = 2\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "case.py").write_text("c = 1\n")
    (repo / "test_a.py").write_text("t = 2\n")
    assert gate(repo, "source-only") == (1, ["test_a.py", "tests/case.py"])


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
def test_untracked_caches_are_ignored(repo: Path) -> None:
    for cache in ("__pycache__", ".pytest_cache", "node_modules/.cache"):
        (repo / cache).mkdir(parents=True)
        (repo / cache / "x.bin").write_text("cache")
    (repo / "test_a.py").write_text("t = 2\n")
    assert gate(repo, "test-only") == (0, [])


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
def test_tracked_cache_change_still_counts(repo: Path) -> None:
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "k.txt").write_text("1")
    subprocess.run(["git", "add", "-f", "-A"], cwd=repo, env=ENV, check=True)
    subprocess.run(["git", "commit", "-qm", "track"], cwd=repo, env=ENV, check=True)
    (repo / "__pycache__" / "k.txt").write_text("2")
    assert gate(repo, "test-only") == (1, ["__pycache__/k.txt"])


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
def test_staged_rename_counts_both_paths(repo: Path) -> None:
    subprocess.run(["git", "mv", "a.py", "c.py"], cwd=repo, env=ENV, check=True)
    assert gate(repo, "test-only") == (1, ["c.py", "a.py"])


@pytest.mark.integration(reason="uses an owned Git repository and a real permission boundary")
def test_unreadable_untracked_directory_stops(repo: Path) -> None:
    hidden = repo / "tests"
    hidden.mkdir()
    payload = b"assert False\n"
    (hidden / "case.py").write_bytes(payload)
    mode = stat.S_IMODE(hidden.stat().st_mode)
    env = {**ENV, "LC_ALL": "C"}
    hidden.chmod(0)
    try:
        try:
            list(hidden.iterdir())
        except PermissionError:
            pass
        else:
            pytest.skip("directory permissions do not deny reads for this process")
        raw = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert raw.returncode == 0
        assert raw.stdout == ""
        assert "Permission denied" in raw.stderr
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "source-only", *PATTERNS],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 1
        assert done.stdout == ""
        assert done.stderr == f"git status incomplete (exit 0): {raw.stderr.strip()}\n"
    finally:
        hidden.chmod(mode)
    assert (hidden / "case.py").read_bytes() == payload


@pytest.mark.integration(reason="uses an owned Git repository and the gate CLI")
@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_flagged_tracked_file_stops(repo: Path, flag: str) -> None:
    subprocess.run(["git", "update-index", flag, "a.py"], cwd=repo, env=ENV, check=True)
    (repo / "a.py").write_text("x = 2\n")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "test-only", *PATTERNS],
        cwd=repo,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    assert done.stdout == ""
    assert done.stderr == "git status cannot see flagged paths: a.py\n"
