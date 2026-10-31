"""Exercise replay recovery against owned temporary Git repositories."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("replay.py")
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def test_stopped_report_graders_reject_extra_paragraphs() -> None:
    cases = Path(__file__).parents[1] / "evals"
    for case, result, state, choice in (
        (
            "02-rebase-competing-conflict",
            "src/parser.py has competing tokenization behavior.",
            "The replay is paused; backup saved retains the original tip.",
            "Choose whether blank input returns an empty list or an empty token.",
        ),
        (
            "04-rebase-merge-commit-stops",
            "The branch contains a merge commit.",
            "No replay ran; no recovery refs were created.",
            "Choose a separate merge-handling workflow or leave the branch unchanged.",
        ),
        (
            "05-rebase-already-up-to-date",
            "The branch is already current with origin/main.",
            "No replay ran; no recovery refs were created.",
            "Next: done.",
        ),
    ):
        pattern = next(
            line.removeprefix("    pattern: '").removesuffix("'")
            for line in (cases / case / "case.yaml").read_text().splitlines()
            if line.startswith("    pattern: '^⚠")
        )
        valid = f"⚠ Stopped: {result}\n\n{state}\n\n{choice}\n"
        assert re.search(pattern, valid)
        assert not re.search(pattern, valid + "\n- Additional history.\n")
        assert not re.search(pattern, valid.replace("\n\n", "\n\nCommit inventory.\n\n", 1))


def test_console_graders_require_prompt_and_tracking_remote() -> None:
    case = Path(__file__).parents[1] / "evals/07-rebase-fork-upstream-remote/case.yaml"
    push, missing_prompt = [
        line.removeprefix("    pattern: '").removesuffix("'")
        for line in case.read_text().splitlines()
        if line.startswith("    pattern: '```console")
    ]
    valid = (
        "```console\n$ git push \\\n"
        "    --force-with-lease \\\n"
        "    --force-if-includes \\\n"
        "    origin HEAD:feat-evaluate\n```\n"
    )
    assert re.search(push, valid)
    assert not re.search(missing_prompt, valid)
    assert not re.search(push, valid.replace("origin", "upstream"))
    assert not re.search(push, valid.replace("$ ", ""))
    assert re.search(missing_prompt, valid.replace("$ ", ""))


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, env=ENV, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, content in files.items():
        (repo / name).write_text(content)
    git(repo, "add", "--", *files)
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def run(repo: Path, *args: str) -> tuple[int, dict[str, object]]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        env=ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-qb", "main")
    commit(tmp_path, {"notes": "base\n", "code": "base\n", ".gitignore": "cache\n"}, "base")
    git(tmp_path, "switch", "-qc", "feature")
    commit(tmp_path, {"code": "feature\n"}, "feature")
    git(tmp_path, "switch", "-q", "main")
    commit(tmp_path, {"upstream": "upstream\n"}, "upstream")
    git(tmp_path, "switch", "-q", "feature")
    return tmp_path


@pytest.mark.integration
def test_inspect_empty_overlap_and_replay_pin_the_actual_target(repo: Path) -> None:
    tip = git(repo, "rev-parse", "HEAD")
    code, plan = run(repo, "inspect", "--onto", "main")
    assert code == 0, plan
    assert plan["overlap"] == []
    assert git(repo, "status", "--porcelain") == ""
    for key in ("rebase.updateRefs", "rebase.abbreviateCommands", "rebase.autoStash"):
        git(repo, "config", key, "true")
    git(repo, "branch", "checkpoint")
    code, result = run(repo, "start", "--onto", "main")
    assert code == 0, result
    assert result["outcome"] == "rebased"
    assert result["target_oid"] == git(repo, "rev-parse", "main")
    assert git(repo, "rev-parse", "checkpoint") == tip
    assert git(repo, "rev-parse", str(result["backup"])) == tip
    assert git(repo, "show", "HEAD:code") == "feature"
    assert (repo / "upstream").read_text() == "upstream\n"


@pytest.mark.integration
def test_partial_staging_and_untracked_edits_survive(repo: Path) -> None:
    (repo / "notes").write_text("staged\n")
    git(repo, "add", "notes")
    (repo / "notes").write_text("working\n")
    (repo / "draft").write_text("untracked\n")
    code, result = run(repo, "start", "--onto", "main")
    assert code == 0, result
    assert git(repo, "show", ":notes") == "staged"
    assert (repo / "notes").read_text() == "working\n"
    assert (repo / "draft").read_text() == "untracked\n"
    assert git(repo, "rev-parse", str(result["stash_ref"])) == result["stash"]
    assert str(result["stash"]) in git(repo, "stash", "list", "--format=%H")


@pytest.mark.integration
@pytest.mark.parametrize("filename", ["cache", "draft"])
def test_incoming_ignored_or_untracked_file_is_preserved(repo: Path, filename: str) -> None:
    git(repo, "switch", "-q", "main")
    (repo / filename).write_text("upstream\n")
    git(repo, "add", "-f", filename)
    git(repo, "commit", "-qm", "track file")
    git(repo, "switch", "-q", "feature")
    tip = git(repo, "rev-parse", "HEAD")
    (repo / filename).write_text("user work\n")
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert "overlap" in str(result["reason"])
    assert (repo / filename).read_text() == "user work\n"
    assert git(repo, "rev-parse", "HEAD") == tip
    assert "rebase-backup" not in git(repo, "branch", "--list")


def conflict(repo: Path, *, notes: bool = False) -> None:
    git(repo, "switch", "-q", "main")
    files = {"code": "trunk\n"}
    if notes:
        files["notes"] = "trunk notes\n"
    commit(repo, files, "competing upstream change")
    git(repo, "switch", "-q", "feature")


@pytest.mark.integration
def test_continue_keeps_exact_stash_after_restore_conflict(repo: Path) -> None:
    conflict(repo, notes=True)
    (repo / "notes").write_text("another caller's notes\n")
    other = git(repo, "stash", "create", "another caller's stash")
    (repo / "notes").write_text("unsaved notes\n")
    code, first = run(repo, "start", "--onto", "main")
    assert code == 1, first
    assert first["phase"] == "rebase_conflict"
    saved = str(first["stash"])
    git(repo, "stash", "store", "-m", "another caller's stash", other)
    assert git(repo, "rev-parse", "refs/stash") != saved
    (repo / "code").write_text("combined\n")
    git(repo, "add", "code")
    code, final = run(repo, "continue")
    assert code == 1, final
    assert final["phase"] == "restore_conflict"
    assert final["outcome"] == "rebased"
    assert final["stash"] == saved
    assert git(repo, "show", f"{saved}:notes") == "unsaved notes"
    assert git(repo, "rev-parse", str(final["stash_ref"])) == saved
    assert "<<<<<<<" in (repo / "notes").read_text()
    assert not (repo / ".git" / "rebase-merge").exists()
    (repo / "notes").write_text("resolved local notes\n")
    git(repo, "add", "notes")
    code, resolved = run(repo, "restore", "--resolved")
    assert code == 0, resolved
    assert git(repo, "show", ":notes") == "resolved local notes"
    assert saved in git(repo, "stash", "list", "--format=%H")


@pytest.mark.integration
def test_manual_abort_then_restore_keeps_partial_staging(repo: Path) -> None:
    conflict(repo)
    tip = git(repo, "rev-parse", "HEAD")
    (repo / "notes").write_text("staged\n")
    git(repo, "add", "notes")
    (repo / "notes").write_text("working\n")
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert result["phase"] == "rebase_conflict"
    git(repo, "rebase", "--abort")
    code, result = run(repo, "restore")
    assert code == 0, result
    assert result["outcome"] == "aborted"
    assert git(repo, "rev-parse", "HEAD") == tip
    assert git(repo, "show", ":notes") == "staged"
    assert (repo / "notes").read_text() == "working\n"


@pytest.mark.integration
def test_continue_refuses_unrelated_staged_work(repo: Path) -> None:
    conflict(repo)
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert result["phase"] == "rebase_conflict"
    (repo / "code").write_text("combined\n")
    (repo / "notes").write_text("user staged\n")
    git(repo, "add", "code", "notes")
    head = git(repo, "rev-parse", "HEAD")
    code, result = run(repo, "continue")
    assert code == 1, result
    assert "unrelated staged" in str(result["reason"])
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "show", ":notes") == "user staged"


@pytest.mark.integration
def test_continue_preserves_ignored_work_added_while_paused(repo: Path) -> None:
    (repo / "cache").write_text("branch cache\n")
    git(repo, "add", "-f", "cache")
    git(repo, "commit", "-qm", "track cache")
    conflict(repo)
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert result["phase"] == "rebase_conflict"
    (repo / "code").write_text("combined\n")
    git(repo, "add", "code")
    (repo / "cache").write_text("new user work\n")
    code, result = run(repo, "continue")
    assert code == 1, result
    assert "overlap" in str(result["reason"])
    assert (repo / "cache").read_text() == "new user work\n"


@pytest.mark.integration
def test_hook_edits_block_restore_and_both_versions_survive(repo: Path) -> None:
    (repo / "notes").write_text("user edit\n")
    hook = repo / ".git" / "hooks" / "post-rewrite"
    hook.write_text("#!/bin/sh\nprintf 'hook edit\\n' > notes\ngit add notes\n")
    hook.chmod(0o755)
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert result["phase"] == "restore_blocked"
    assert git(repo, "show", ":notes") == "hook edit"
    assert (repo / "notes").read_text() == "hook edit\n"
    assert git(repo, "show", f"{result['stash']}:notes") == "user edit"


@pytest.mark.integration
def test_pre_rebase_hook_edits_are_not_lost(repo: Path) -> None:
    (repo / "notes").write_text("user edit\n")
    hook = repo / ".git" / "hooks" / "pre-rebase"
    hook.write_text("#!/bin/sh\nprintf 'hook edit\\n' > notes\ngit add notes\n")
    hook.chmod(0o755)
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert git(repo, "show", ":notes") == "hook edit"
    assert (repo / "notes").read_text() == "hook edit\n"
    assert git(repo, "show", f"{result['stash']}:notes") == "user edit"


@pytest.mark.integration
@pytest.mark.parametrize("change", ["commit", "ignored"])
def test_pre_rebase_hook_cannot_introduce_unprotected_changes(repo: Path, change: str) -> None:
    git(repo, "switch", "-q", "main")
    (repo / "cache").write_text("trunk cache\n")
    git(repo, "add", "-f", "cache")
    git(repo, "commit", "-qm", "track cache")
    git(repo, "switch", "-q", "feature")
    hook_directory = repo / "configured hooks"
    hook_directory.mkdir()
    git(repo, "config", "core.hooksPath", str(hook_directory))
    hook = hook_directory / "pre-rebase"
    if change == "commit":
        script = "printf 'hook commit\\n' > notes\ngit add notes\ngit commit -qm 'hook commit'\n"
    else:
        script = "printf 'hook ignored work\\n' > cache\n"
    hook.write_text(f"#!/bin/sh\n{script}")
    hook.chmod(0o755)
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    if change == "commit":
        assert git(repo, "show", "HEAD:notes") == "hook commit"
    else:
        assert (repo / "cache").read_text() == "hook ignored work\n"


@pytest.mark.integration
def test_restore_preserves_new_ignored_work_on_deleted_path(repo: Path) -> None:
    git(repo, "switch", "-q", "main")
    git(repo, "rm", "notes")
    commit(repo, {".gitignore": "cache\nnotes\n"}, "remove notes")
    git(repo, "switch", "-q", "feature")
    (repo / "notes").write_text("user edit\n")
    hook = repo / ".git" / "hooks" / "post-rewrite"
    hook.write_text("#!/bin/sh\nprintf 'new ignored work\\n' > notes\n")
    hook.chmod(0o755)
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert result["phase"] == "restore_blocked"
    assert (repo / "notes").read_text() == "new ignored work\n"
    assert git(repo, "show", f"{result['stash']}:notes") == "user edit"


@pytest.mark.integration
def test_rejecting_hook_restores_the_original_index(repo: Path) -> None:
    (repo / "notes").write_text("staged\n")
    git(repo, "add", "notes")
    hook = repo / ".git" / "hooks" / "pre-rebase"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    tip = git(repo, "rev-parse", "HEAD")
    code, result = run(repo, "start", "--onto", "main")
    assert code == 1, result
    assert result["outcome"] == "aborted"
    assert git(repo, "rev-parse", "HEAD") == tip
    assert git(repo, "show", ":notes") == "staged"


@pytest.mark.integration
def test_continue_does_not_follow_a_moved_target_ref(repo: Path) -> None:
    conflict(repo)
    code, first = run(repo, "start", "--onto", "main")
    assert code == 1, first
    assert first["phase"] == "rebase_conflict"
    git(repo, "update-ref", "refs/heads/main", str(first["base"]))
    (repo / "code").write_text("combined\n")
    git(repo, "add", "code")
    code, final = run(repo, "continue")
    assert code == 0, final
    assert final["target_oid"] == first["target_oid"]
    assert git(repo, "rev-parse", "HEAD^") == first["target_oid"]
