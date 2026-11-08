"""Prove scan publication preserves user state across failures and races."""

# ruff: noqa: S101, S603, S607, INP001, D103

import json
import os
import shlex
import subprocess
from typing import TYPE_CHECKING

import pytest
import scan_apply

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration(reason="uses owned Git repositories and scan publication")


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    for key, value in {
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }.items():
        monkeypatch.setenv(key, value)
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    git(repo, "init", "-q", "-b", "main")
    (repo / "café.sh").write_text("#!/bin/sh\n# TODO: revisit this later\nprintf 'ok\\n'\n")
    (repo / "café.sh").chmod(0o755)
    (repo / "user.txt").write_text("base\n")
    git(repo, "add", "café.sh", "user.txt")
    git(repo, "commit", "-qm", "base")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    run = repo / ".git" / "scan"
    run.mkdir()
    target = repo / "café.sh"
    original = target.read_bytes()
    target.write_text("#!/bin/sh\nprintf 'ok\\n'\n")
    (run / "finding.patch").write_bytes(git(repo, "diff", "--binary"))
    target.write_bytes(original)
    (run / "commits.json").write_text(
        json.dumps(
            [
                {
                    "file": "café.sh",
                    "patch": "finding.patch",
                    "subject": "shell(chore) Remove vague TODO",
                    "body": "why: Keep the command visible.\n\nwhat:\n- Remove the vague TODO",
                }
            ]
        )
    )
    (run / "gates.json").write_text("[]")
    (repo / "user.txt").write_text("user staged\n")
    git(repo, "add", "user.txt")
    (repo / "user.txt").write_text("user staged\nuser unstaged\n")
    (repo / "untracked.txt").write_bytes(b"user untracked\xff\n")
    return repo, run, head


def protected(repo: Path) -> tuple[bytes, bytes, bytes, bytes]:
    return (
        git(repo, "diff", "--cached", "--binary", "--", "user.txt"),
        git(repo, "diff", "--binary", "--", "user.txt"),
        (repo / "user.txt").read_bytes(),
        (repo / "untracked.txt").read_bytes(),
    )


def invoke(
    run: Path, head: str, capsys: pytest.CaptureFixture[str], *extra: str
) -> dict[str, object]:
    mode = ["--verify"] if "--verify" in extra else ["--entry", "0"]
    args = ["--run-dir", str(run), "--expected-head", head, *mode, *extra]
    scan_apply.main(args)
    result = json.loads(capsys.readouterr().out)
    assert isinstance(result, dict)
    return {str(k): v for k, v in result.items()}


def test_success_preserves_partial_staging_unicode_and_executable_mode(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, run, head = setup
    before = protected(repo)
    hook = repo / ".git/hooks/post-merge"
    hook.write_text("#!/bin/sh\nprintf 'damaged\\n' > user.txt\n")
    hook.chmod(0o755)
    os.utime(repo / "café.sh", (1_000_000_000, 1_000_000_000))
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "committed", result
    assert protected(repo) == before
    assert git(repo, "diff", "--name-only", "-z", head, "HEAD") == "café.sh\0".encode()
    assert (repo / "café.sh").stat().st_mode & 0o111
    assert b"TODO" not in (repo / "café.sh").read_bytes()
    assert git(repo, "for-each-ref", "refs/heads/slop-scan-recovery-") == b""


@pytest.mark.parametrize("failure", ["gate", "hook"])
def test_failures_cannot_change_original_user_files(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str], failure: str
) -> None:
    repo, run, head = setup
    before = protected(repo)
    target = (repo / "café.sh").read_bytes()
    command = "printf 'gate edit\\n' > user.txt; printf 'new\\n' > generated; exit 1"
    if failure == "gate":
        (run / "gates.json").write_text(json.dumps([{"name": "lint", "command": command}]))
    else:
        hook = repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\n" + command + "\n")
        hook.chmod(0o755)
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == failure + "-failed", result
    assert protected(repo) == before
    assert (repo / "café.sh").read_bytes() == target
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head
    assert not (repo / "generated").exists()


def test_final_verification_runs_in_an_isolated_tree(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, run, head = setup
    before = protected(repo)
    command = "printf 'formatter edit\\n' > user.txt"
    (run / "gates.json").write_text(json.dumps([{"name": "format", "command": command}]))
    result = invoke(run, head, capsys, "--allow-dirty", "--verify")
    assert result["status"] == "gate-modified", result
    assert protected(repo) == before
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head


@pytest.mark.parametrize("change_during_gate", [False, True])
def test_live_target_edits_refuse_without_rollback(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str], change_during_gate: bool
) -> None:
    repo, run, head = setup
    before = protected(repo)
    if change_during_gate:
        command = "printf 'concurrent user edit\\n' > " + shlex.quote(str(repo / "café.sh"))
        (run / "gates.json").write_text(json.dumps([{"name": "lint", "command": command}]))
    else:
        (repo / "café.sh").write_text("concurrent user edit\n")
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "refused", result
    assert (repo / "café.sh").read_text() == "concurrent user edit\n"
    assert protected(repo) == before
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head


def test_unrelated_staging_during_gates_is_retained(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, run, head = setup
    command = (
        "printf 'new staged\\n' > "
        + shlex.quote(str(repo / "user.txt"))
        + " && git -C "
        + shlex.quote(str(repo))
        + " add -- user.txt"
        + " && printf 'new unstaged\\n' >> "
        + shlex.quote(str(repo / "user.txt"))
    )
    (run / "gates.json").write_text(json.dumps([{"name": "lint", "command": command}]))
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "committed", result
    assert git(repo, "show", ":user.txt") == b"new staged\n"
    assert (repo / "user.txt").read_text() == "new staged\nnew unstaged\n"


@pytest.mark.parametrize("concurrent_edit", [False, True])
def test_ref_failure_rolls_back_only_when_the_target_stays_unchanged(
    setup: tuple[Path, Path, str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    concurrent_edit: bool,
) -> None:
    repo, run, head = setup
    before = protected(repo)
    original = (repo / "café.sh").read_bytes()
    real_git = scan_apply._git  # noqa: SLF001

    def fail_update(
        location: Path, *args: str, index: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        if args[:3] == ("update-ref", "-m", "slop: apply scan finding"):
            if concurrent_edit:
                (repo / "café.sh").write_text("user edited after apply\n")
            return subprocess.CompletedProcess(args, 1, b"", b"ref update refused")
        return real_git(location, *args, index=index, check=check)

    monkeypatch.setattr(scan_apply, "_git", fail_update)
    result = invoke(run, head, capsys, "--allow-dirty")
    expected = "recovery-needed" if concurrent_edit else "refused"
    assert result["status"] == expected, result
    assert protected(repo) == before
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head
    assert git(repo, "show-ref", "--verify", "refs/heads/" + str(result["recovery_branch"]))
    expected_content = b"user edited after apply\n" if concurrent_edit else original
    assert (repo / "café.sh").read_bytes() == expected_content
    assert not (repo / ".git/index.lock").exists()


@pytest.mark.parametrize("refusal", ["dirty", "stale", "lock"])
def test_preconditions_refuse_without_changes(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str], refusal: str
) -> None:
    repo, run, head = setup
    before = protected(repo)
    original = (repo / "café.sh").read_bytes()
    lock = repo / ".git/index.lock"
    if refusal == "lock":
        lock.write_text("another operation\n")
    args = [] if refusal == "dirty" else ["--allow-dirty"]
    result = invoke(run, "0" * 40 if refusal == "stale" else head, capsys, *args)
    assert result["status"] == "refused", result
    if refusal == "lock":
        assert lock.read_text() == "another operation\n"
        lock.unlink()
    assert protected(repo) == before
    assert (repo / "café.sh").read_bytes() == original
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head


@pytest.mark.parametrize("error", [OSError, FileExistsError])
def test_publication_exception_reports_retained_candidate(
    setup: tuple[Path, Path, str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    error: type[OSError],
) -> None:
    repo, run, head = setup
    before = protected(repo)
    real_git = scan_apply._git  # noqa: SLF001

    def fail_update(
        location: Path, *args: str, index: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        if args[:3] == ("update-ref", "-m", "slop: apply scan finding"):
            raise error
        return real_git(location, *args, index=index, check=check)

    monkeypatch.setattr(scan_apply, "_git", fail_update)
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "recovery-needed", result
    assert protected(repo) == before
    assert b"TODO" not in (repo / "café.sh").read_bytes()
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head
    assert git(repo, "show-ref", "--verify", "refs/heads/" + str(result["recovery_branch"]))
    assert not (repo / ".git/index.lock").exists()


@pytest.mark.parametrize("cleanup", ["recovery-ref", "worktree", "candidate-patch"])
def test_completed_publication_is_not_reported_as_refused_after_cleanup_failure(
    setup: tuple[Path, Path, str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    cleanup: str,
) -> None:
    repo, run, head = setup
    before = protected(repo)
    real_git = scan_apply._git  # noqa: SLF001
    real_unlink = type(run).unlink

    def fail_git_cleanup(
        location: Path, *args: str, index: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        if cleanup == "recovery-ref" and args[:2] == ("update-ref", "-d"):
            raise OSError
        result = real_git(location, *args, index=index, check=check)
        if cleanup == "worktree" and args[:2] == ("worktree", "remove"):
            raise OSError
        return result

    def fail_unlink(path: Path, missing_ok: bool = False) -> None:
        real_unlink(path, missing_ok=missing_ok)
        if cleanup == "candidate-patch" and path.name.startswith(".candidate-"):
            raise OSError

    monkeypatch.setattr(scan_apply, "_git", fail_git_cleanup)
    monkeypatch.setattr(type(run), "unlink", fail_unlink)
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "committed", result
    assert result["commit"] == git(repo, "rev-parse", "HEAD").decode().strip()
    assert protected(repo) == before
    assert b"TODO" not in (repo / "café.sh").read_bytes()


def test_hook_changes_must_pass_gates_on_exact_candidate(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, run, head = setup
    before = protected(repo)
    original = (repo / "café.sh").read_bytes()
    command = "! git grep -q 'hook damage' -- café.sh"
    (run / "gates.json").write_text(json.dumps([{"name": "lint", "command": command}]))
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nprintf '# hook damage\\n' >> café.sh\ngit add -- café.sh\n")
    hook.chmod(0o755)
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "gate-failed", result
    assert protected(repo) == before
    assert (repo / "café.sh").read_bytes() == original
    assert git(repo, "rev-parse", "HEAD").decode().strip() == head


def test_symlinked_parent_is_refused_even_inside_the_repository(
    setup: tuple[Path, Path, str], capsys: pytest.CaptureFixture[str]
) -> None:
    repo, run, head = setup
    (repo / "alias").symlink_to(repo, target_is_directory=True)
    entries = json.loads((run / "commits.json").read_text())
    entries[0]["file"] = "alias/café.sh"
    (run / "commits.json").write_text(json.dumps(entries))
    before = protected(repo)
    result = invoke(run, head, capsys, "--allow-dirty")
    assert result["status"] == "refused", result
    assert "parent directories" in str(result["error"])
    assert protected(repo) == before
