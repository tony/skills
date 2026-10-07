"""Registry matcher: added-line scope, path guards, diff and message modes."""

# ruff: noqa: S101, S603, S607, INP001, D103, PLR2004, E501
# pyright: reportAny=false, reportUnusedCallResult=false, reportImplicitStringConcatenation=false

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import detect  # pyright: ignore[reportImplicitRelativeImport]
import pytest

REGISTRY = Path(__file__).resolve().parent.parent / "references" / "signatures.yml"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}
MINI = """version: 1
signatures:
  - id: low-value.todo-noise
    tier: A
    kind: regex
    target: [diff]
    pattern: '^\\+.*\\b(TODO|FIXME):?\\s*(revisit|later)\\b'
    fp-guard: 'Added lines only.'
  - id: low-value.log-debris
    tier: B
    kind: regex
    target: [diff]
    skip-paths: ['(^|/)scripts/', 'debug']
    pattern: '^\\+\\s*print\\('
    fp-guard: 'Skip scripts.'
  - id: brittle.counts
    tier: B
    kind: regex
    target: [message-subject, message-body]
    pattern: '(?i)\\badds?\\s+\\d+\\s+tests?\\b'
  - id: ai-slop.emoji
    tier: A
    kind: regex
    target: [message-subject]
    pattern: '[\\x{1F300}-\\x{1FAFF}]'
  - id: verbose.semantic
    tier: B
    kind: semantic
    target: [diff]
"""


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, env=ENV, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def rules() -> list[detect.Rule]:
    sigs = detect.parse_yaml(MINI)["signatures"]
    return detect.build_rules(sigs)


def test_shipped_registry_loads_and_compiles() -> None:
    sigs, counts = detect.load_registry(REGISTRY)
    built = detect.build_rules(sigs)
    assert counts["builtin"] == len(sigs) > 10
    assert {r.sig["id"] for r in built} >= {
        "low-value.todo-noise",
        "ai-slop.emoji-in-commit-subject",
    }
    emoji = next(r for r in built if r.sig["id"] == "ai-slop.emoji-in-commit-subject")
    assert emoji.regex.search("ship it \U0001f680")
    assert not emoji.regex.search("check \u2713 and warn \u26a0")


def test_scan_demotes_preexisting_todo_and_keeps_added_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "old.py").write_text("x = 1  # TODO: revisit later\n")
    git(tmp_path, "add", "old.py")
    git(tmp_path, "commit", "-q", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "new.py").write_text("y = 2\n# TODO: revisit later\n")
    git(tmp_path, "add", "new.py")
    git(tmp_path, "commit", "-q", "-m", "branch")
    monkeypatch.chdir(tmp_path)

    added = detect.added_lines(base)
    found = detect.scan_files(rules(), ["old.py", "new.py"], added)
    by_file = {f["file"]: f for f in found}
    assert by_file["new.py"]["tier"] == "A"
    assert by_file["new.py"]["line_start"] == 2
    assert by_file["old.py"]["tier"] == "B"
    assert by_file["old.py"]["pre_existing"] is True

    on_trunk = detect.scan_files(rules(), ["old.py", "new.py"], detect.added_lines("HEAD"))
    assert {f["tier"] for f in on_trunk} == {"B"}
    no_base = detect.scan_files(rules(), ["new.py"], None)
    assert no_base[0]["tier"] == "B"


def test_skip_paths_suppress_a_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("print('x')\n")
    (tmp_path / "lib.py").write_text("print('x')\n")
    monkeypatch.chdir(tmp_path)
    found = detect.scan_files(rules(), ["scripts/run.py", "lib.py"], None)
    assert [f["file"] for f in found] == ["lib.py"]


def test_diff_mode_tracks_commit_path_and_line_numbers() -> None:
    log = (
        "commit abc1234\nAuthor: t\n\n    adds 3 tests\n\n"
        "diff --git a/src/q.py b/src/q.py\n--- a/src/q.py\n+++ b/src/q.py\n"
        "@@ -1,2 +10,3 @@\n keep\n+# TODO: revisit later\n+z = 1\n"
    )
    found = detect.scan_diff(rules(), log, historical=True)
    assert len(found) == 1
    assert found[0]["commit_sha"] == "abc1234"
    assert (found[0]["file"], found[0]["line_start"]) == ("src/q.py", 11)
    assert found[0]["tier"] == "A"
    assert found[0]["historical_only"] is True


def test_messages_mode_splits_subject_and_body() -> None:
    log = "sha1\x1fFeat \U0001f680 ship\n\nadds 3 tests here\0sha2\x1fplain subject\n"
    found = detect.scan_messages(rules(), log, historical=False)
    pairs = {(f["commit_sha"], f["signature_id"], f["line_start"]) for f in found}
    assert pairs == {("sha1", "ai-slop.emoji", 1), ("sha1", "brittle.counts", 3)}


def test_override_replace_append_delete_and_duplicate(tmp_path: Path) -> None:
    reg = tmp_path / "r.yml"
    reg.write_text(MINI)
    override = tmp_path / "o.yml"
    override.write_text(
        "replace:\n  - id: brittle.counts\n    tier: C\n"
        "append:\n  - id: project.x\n    kind: regex\n    tier: A\n    pattern: 'x'\n    target: [file]\n"
        "delete:\n  - ai-slop.emoji\n"
    )
    sigs, counts = detect.load_registry(reg, override)
    ids = {s["id"]: s for s in sigs}
    assert ids["brittle.counts"]["tier"] == "C"
    assert "ai-slop.emoji" not in ids
    assert counts == {"builtin": 5, "replaced": 1, "appended": 1, "deleted": 1}

    override.write_text("delete:\n  - brittle.counts\nreplace:\n  - id: brittle.counts\n")
    with pytest.raises(detect.RegistryError):
        detect.load_registry(reg, override)


def test_cli_prints_json_and_exit_2_on_bad_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reg = tmp_path / "r.yml"
    reg.write_text(MINI)
    target = tmp_path / "a.txt"
    target.write_text("# TODO: revisit later\n")
    assert detect.main(["files", "--registry", str(reg), str(target)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["loaded"]["builtin"] == 5
    assert out["findings"][0]["tier"] == "B"

    bad = tmp_path / "bad.yml"
    bad.write_text("delete:\n  - nope\n")
    assert detect.main(["files", "--registry", str(reg), "--override", str(bad), str(target)]) == 2
