"""Outer-loop Git rewrites, hooks and recovery against temporary repositories."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

pytestmark = pytest.mark.integration

SCRIPT = Path(__file__).resolve().parent / "rewrite.py"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, env=ENV, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        (repo / name).write_text(text)
    git(repo, "add", *files)
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def run(repo: Path, *args: str, script: Path = SCRIPT) -> tuple[int, dict[str, object]]:
    done = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=repo,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, json.loads(done.stdout)


def changes(draft: bool = False, two: bool = False) -> str:
    return (
        "# Changes\n"
        + ("- draft\n" if draft else "")
        + "\n" * 6
        + "## Old\n"
        + ("- two\n" if two else "")
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    commit(tmp_path, {"CHANGES.md": changes(), "code.py": "a\n"}, "base")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(tmp_path, "switch", "-q", "-c", "feat")
    return tmp_path


def test_partition_marks_pure_and_mixed(repo: Path) -> None:
    commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"CHANGES.md": changes(draft=True, two=True), "code.py": "b\n"}, "feat: two")
    code, result = run(repo, "partition", "--base", "origin/main", "--file", "CHANGES.md")
    assert code == 0
    commits = cast("list[dict[str, object]]", result["commits"])
    assert [c["pure"] for c in commits] == [True, False]


def test_drop_removes_pure_commit_and_keeps_code(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"code.py": "b\n"}, "feat: code")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft[:7])
    assert code == 0
    assert result["dropped"] == 1
    backup = str(result["backup"])
    assert backup.startswith("changelog-rewrite-backup-")
    assert git(repo, "rev-parse", backup) == result["backup_tip"]
    assert git(repo, "show", "HEAD:CHANGES.md") == changes().strip()
    assert git(repo, "show", "HEAD:code.py") == "b"
    assert git(repo, "log", "--format=%s", "origin/main..HEAD") == "feat: code"


def test_drop_leaves_mixed_commit_intact(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    files = {"CHANGES.md": changes(draft=True, two=True), "code.py": "b\n"}
    commit(repo, files, "feat: two")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 0, result
    assert result["mixed_remaining"] is True
    assert git(repo, "log", "--format=%s", "origin/main..HEAD") == "feat: two"


def test_drop_refuses_mixed_commit(repo: Path) -> None:
    mixed = commit(repo, {"CHANGES.md": changes(two=True), "code.py": "b\n"}, "feat: x")
    before = git(repo, "rev-parse", "HEAD")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", mixed)
    assert code == 1
    assert result["ok"] is False
    assert git(repo, "rev-parse", "HEAD") == before
    assert "changelog-rewrite-backup-" not in git(repo, "branch", "--list")


@pytest.mark.parametrize("kind", ["unstaged", "staged", "untracked"])
def test_drop_refuses_dirty_tree(repo: Path, kind: str) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    filename = "notes.txt" if kind == "untracked" else "code.py"
    (repo / filename).write_text("dirty\n")
    if kind == "staged":
        git(repo, "add", filename)
    status = git(repo, "status", "--porcelain")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1
    assert "uncommitted" in str(result["reason"])
    assert (repo / filename).read_text() == "dirty\n"
    assert git(repo, "status", "--porcelain") == status
    assert git(repo, "rev-parse", "HEAD") == draft


def test_failed_validation_restores_the_backup(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    tip = commit(repo, {"CHANGES.md": changes(draft=True) + "- later\n"}, "docs: later")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1
    assert result["backup"]
    assert git(repo, "rev-parse", "HEAD") == tip
    assert git(repo, "status", "--porcelain") == ""


@pytest.mark.parametrize("setting", ["rebase.abbreviateCommands", "rebase.updateRefs"])
def test_rebase_settings_cannot_skip_drops_or_move_other_branches(repo: Path, setting: str) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"CHANGES.md": changes(draft=True, two=True), "code.py": "b\n"}, "feat: mixed")
    before = git(repo, "rev-parse", "HEAD")
    git(repo, "branch", "user-checkpoint")
    git(repo, "config", setting, "true")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 0, result
    assert "docs: draft" not in git(repo, "log", "--format=%s", "origin/main..HEAD")
    assert git(repo, "rev-parse", "user-checkpoint") == before
    assert git(repo, "rev-parse", str(result["backup"])) == before


def test_drop_uses_fork_when_base_has_advanced(repo: Path) -> None:
    fork = git(repo, "rev-parse", "HEAD")
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"code.py": "b\n"}, "feat: code")
    git(repo, "switch", "-q", "main")
    commit(repo, {"base-only.py": "base\n"}, "feat: upstream")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-q", "feat")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 0, result
    assert result["merge_base"] == fork
    assert git(repo, "log", "--format=%s", f"{fork}..HEAD") == "feat: code"
    assert not (repo / "base-only.py").exists()


def test_drop_from_subdirectory_uses_root_relative_changelog(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    (repo / "src").mkdir()
    code, result = run(repo / "src", "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 0, result
    assert git(repo, "show", "HEAD:CHANGES.md") == changes().strip()


def test_failed_validation_keeps_new_hook_edits(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"CHANGES.md": changes(draft=True, two=True)}, "docs: later")
    hook = repo / ".git" / "hooks" / "post-rewrite"
    hook.write_text("#!/bin/sh\nprintf 'hook edit\\n' > code.py\n")
    hook.chmod(0o755)
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1, result
    assert (repo / "code.py").read_text() == "hook edit\n"
    assert result["backup"]


def test_recovery_preserves_hook_staging_and_unstaged_edits(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    commit(repo, {"code.py": "b\n"}, "feat: code")
    hook = repo / ".git" / "hooks" / "post-rewrite"
    hook.write_text(
        "#!/bin/sh\nprintf 'staged\\n' > code.py\ngit add code.py\nprintf 'unstaged\\n' > code.py\n"
    )
    hook.chmod(0o755)
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1, result
    assert git(repo, "show", ":code.py") == "staged"
    assert (repo / "code.py").read_text() == "unstaged\n"
    assert result["recovery"]


def test_failed_validation_pins_new_hook_commits(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    tip = commit(repo, {"code.py": "b\n"}, "feat: code")
    hook = repo / ".git" / "hooks" / "post-rewrite"
    hook.write_text(
        "#!/bin/sh\nprintf 'hook commit\\n' > code.py\ngit commit -qam 'hook: save edit'\n"
    )
    hook.chmod(0o755)
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1, result
    assert git(repo, "rev-parse", "HEAD") == tip
    assert git(repo, "show", f"{result['recovery']}:code.py") == "hook commit"
    assert git(repo, "log", "-1", "--format=%s", str(result["recovery"])) == "hook: save edit"


def test_conflict_is_left_intact_with_original_history_backed_up(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": "draft\n"}, "docs: draft")
    tip = commit(repo, {"CHANGES.md": "new draft\n", "code.py": "b\n"}, "feat: mixed")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1, result
    assert "still in progress" in str(result["reason"])
    assert git(repo, "rev-parse", str(result["backup"])) == tip
    assert (repo / ".git" / "rebase-merge").is_dir()
    assert "<<<<<<<" in (repo / "CHANGES.md").read_text()
    assert (repo / "code.py").read_text() == "b\n"


def test_local_base_works_and_rewrite_on_base_is_refused(repo: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    code, result = run(repo, "drop", "--base", "main", "--file", "CHANGES.md", draft)
    assert code == 0, result
    git(repo, "switch", "-q", "main")
    main_tip = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: main draft")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", main_tip)
    assert code == 1, result
    assert "base branch" in str(result["reason"])
    assert git(repo, "rev-parse", "HEAD") == main_tip


def test_ignored_file_overlapping_replayed_history_is_preserved(repo: Path) -> None:
    commit(repo, {".gitignore": "scratch.dat\n"}, "chore: ignore scratch")
    (repo / "scratch.dat").write_text("old\n")
    git(repo, "add", "-f", "scratch.dat")
    git(repo, "commit", "-qm", "feat: add scratch")
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    git(repo, "rm", "scratch.dat")
    git(repo, "commit", "-qm", "refactor: remove scratch")
    (repo / "scratch.dat").write_text("user ignored work\n")
    code, result = run(repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft)
    assert code == 1, result
    assert "ignored files overlap" in str(result["reason"])
    assert (repo / "scratch.dat").read_text() == "user ignored work\n"


def test_sequence_editor_quotes_installed_script_path(repo: Path, tmp_path: Path) -> None:
    draft = commit(repo, {"CHANGES.md": changes(draft=True)}, "docs: draft")
    install = tmp_path.parent / "plugin's $PATH with spaces"
    install.mkdir()
    script = install / "rewrite.py"
    shutil.copyfile(SCRIPT, script)
    code, result = run(
        repo, "drop", "--base", "origin/main", "--file", "CHANGES.md", draft, script=script
    )
    assert code == 0, result
    assert git(repo, "show", "HEAD:CHANGES.md") == changes().strip()
