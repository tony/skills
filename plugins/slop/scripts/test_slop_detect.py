"""Registry matcher: added-line scope, path guards, diff and message modes."""

# ruff: noqa: S101, S603, S607, INP001, D103, PLR2004, E501

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import slop_detect as detect

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


def test_preexisting_print_is_advisory_not_a_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "legacy.py").write_text("print('x')\n")
    git(tmp_path, "add", "legacy.py")
    git(tmp_path, "commit", "-q", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "fresh.py").write_text("print('y')\n")
    git(tmp_path, "add", "fresh.py")
    git(tmp_path, "commit", "-q", "-m", "branch")
    monkeypatch.chdir(tmp_path)

    found = detect.scan_files(rules(), ["legacy.py", "fresh.py"], detect.added_lines(base))
    by_file = {f["file"]: f for f in found}
    assert by_file["legacy.py"]["tier"] == "C"
    assert by_file["legacy.py"]["pre_existing"] is True
    assert by_file["legacy.py"]["registry_tier"] == "B"
    assert by_file["fresh.py"]["tier"] == "B"
    assert "pre_existing" not in by_file["fresh.py"]


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


@pytest.mark.parametrize(
    "text",
    [
        "append:\n  - id: a\n    pattern: &p 'x'\n",
        "append:\n  - id: a\n    pattern: *p\n",
        "append:\n  - id: a\n    target: [diff,\n      file]\n",
        "append:\n  - id: a\n    meta: {k: v}\n",
        "append:\n  - id: a\n    nested:\n      k: v\n",
        "append:\n  - id: a\n    pattern: 'unterminated\n",
        "append:\n\t- id: a\n",
        "---\nappend:\n  - id: a\n",
        "just a stray line\n",
        "deletes:\n  - a.b\n",
    ],
)
def test_override_with_unsupported_syntax_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    reg = tmp_path / "r.yml"
    reg.write_text(MINI)
    override = tmp_path / "o.yml"
    override.write_text(text)
    target = tmp_path / "a.txt"
    target.write_text("x\n")
    argv = ["files", "--registry", str(reg), "--override", str(override), str(target)]
    assert detect.main(argv) == 2
    assert capsys.readouterr().err.startswith("detect:")


def _shipped() -> list[detect.Sig]:
    return detect.load_registry(REGISTRY)[0]


def _hits(sig_id: str, mode: str, text: str) -> list[dict[str, object]]:
    built = detect.build_rules(_shipped())
    if mode == "message":
        found = detect.scan_messages(built, f"sha\x1f{text}\n", historical=False)
    else:
        diff = f"diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -0,0 +1 @@\n+{text}\n"
        found = detect.scan_diff(built, diff, historical=False)
    return [f for f in found if f["signature_id"] == sig_id]


TIER_A_FIXTURES = [
    ("ai-slop.signatures", "message", "feat(x) Add y\n\nGenerated with Claude Code", True),
    ("ai-slop.signatures", "message", "feat(x) Add y\n\nDone \U0001f916", True),
    ("ai-slop.signatures", "message", "feat(x) Add y\n\nGenerated with protoc 25", False),
    ("ai-slop.emoji-in-commit-subject", "message", "feat(x) Ship it \U0001f680", True),
    ("ai-slop.emoji-in-commit-subject", "message", "feat(x) Check ✓ and ⚠", False),
    ("brittle.commit-message-markdown-leak", "message", "**feat** add y", True),
    ("brittle.commit-message-markdown-leak", "message", "- add y", True),
    ("brittle.commit-message-markdown-leak", "message", "feat(x) Add y with - dash", False),
    ("low-value.todo-noise", "diff", "# TODO: revisit later", True),
    ("low-value.todo-noise", "diff", "# TODO(alice): revisit after PROJ-12", False),
    ("low-value.todo-noise", "diff", "# TODO: revisit later, see PROJ-12", False),
    ("low-value.todo-noise", "diff", "# TODO: revisit later, see #42", False),
    ("low-value.todo-noise", "diff", "# TODO: revisit later https://x.test/i/1", False),
]


@pytest.mark.parametrize(("sig_id", "mode", "text", "fires"), TIER_A_FIXTURES)
def test_tier_a_rule_fixtures(sig_id: str, mode: str, text: str, fires: bool) -> None:
    assert bool(_hits(sig_id, mode, text)) is fires


def test_every_tier_a_rule_has_a_positive_and_negative_fixture() -> None:
    tier_a = {s["id"] for s in _shipped() if s["tier"] == "A"}
    for sig_id in tier_a:
        outcomes = {fires for sid, _, _, fires in TIER_A_FIXTURES if sid == sig_id}
        assert outcomes == {True, False}, sig_id


def test_tier_a_guards_reach_the_agent_and_none_guard_stays_silent() -> None:
    assert _hits("ai-slop.signatures", "message", "x\n\n\U0001f916")[0]["fp_guard"]
    assert "fp_guard" not in _hits("brittle.commit-message-markdown-leak", "message", "# x")[0]


def test_guards_name_only_checks_something_performs() -> None:
    pipeline = (REGISTRY.parent / "detect-pipeline.md").read_text()
    for sig in _shipped():
        guard = str(sig.get("fp-guard", ""))
        assert not re.search(r"\bLCS\b|similarity|\d\.\d", guard), sig["id"]
        if "tone calibration" in guard:
            assert "## Tone calibration" in pipeline, sig["id"]
        if guard.startswith("Skip test files") or "test fixtures" in guard:
            assert sig.get("skip-paths"), sig["id"]


def test_command_guards_route_through_the_guard_check() -> None:
    pipeline = (REGISTRY.parent / "detect-pipeline.md").read_text()
    guarded = [s["id"] for s in _shipped() if "`git " in str(s.get("fp-guard", ""))]
    assert guarded
    assert "### Guard check" in pipeline
    assert "git grep -c" in pipeline.split("### Guard check")[1].split("\n## ")[0]
    assert "Guard check" in pipeline.split("## Pass B")[1].split("\n## ")[0]


def test_diff_mode_keeps_spaced_and_non_ascii_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    names = ["my file.py", "café.py"]
    for name in names:
        (tmp_path / name).write_text("x = 1\n# TODO: revisit later\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "branch")
    base = git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.chdir(tmp_path)

    log = git(tmp_path, "-c", "core.quotepath=off", "log", "-p", "--reverse")
    found = detect.scan_diff(rules(), log, historical=False)
    assert sorted(f["file"] for f in found) == sorted(names)

    files = detect.scan_files(rules(), names, detect.added_lines("HEAD~0"))
    assert {f["tier"] for f in files} == {"B"}
    (tmp_path / "my file.py").write_text("x = 1\n# TODO: revisit later\ny = 2\n")
    git(tmp_path, "commit", "-q", "-am", "edit")
    files = detect.scan_files(rules(), names[:1], detect.added_lines(base))
    assert files[0]["tier"] == "B"
    assert detect.added_lines(base) == {"my file.py": {3}}


def test_files_mode_skips_symlinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n# TODO: revisit later\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "link.py").symlink_to(outside)
    (repo / "real.py").write_text("x = 1\n# TODO: revisit later\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    monkeypatch.chdir(repo)

    found = detect.scan_files(rules(), ["link.py", "real.py"], None)
    assert {f["file"] for f in found} == {"real.py"}


def test_conventions_requiring_disclosure_demote_attribution_to_tier_b(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    shipped = detect.build_rules(_shipped())
    message = "feat(x) Add y\n\nGenerated with Claude Code"
    found = detect.scan_messages(shipped, f"sha\x1f{message}\n", historical=False)
    footer = [f for f in found if f["signature_id"] == "ai-slop.signatures"]

    detect.demote_by_conventions(shipped, footer)
    assert footer[0]["tier"] == "A"

    (tmp_path / "AGENTS.md").write_text("No attribution footers, no inflated adjectives.\n")
    detect.demote_by_conventions(shipped, footer)
    assert footer[0]["tier"] == "A"

    (tmp_path / "CONTRIBUTING.md").write_text("Contributors must disclose AI assistance.\n")
    detect.demote_by_conventions(shipped, footer)
    assert footer[0]["tier"] == "B"
    assert footer[0]["registry_tier"] == "A"
    assert footer[0]["demoted_by"] == "conventions"


@pytest.mark.parametrize(
    "trailer",
    [
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "Co-authored-by: Copilot <copilot@github.com>",
        "co-authored-by: Claude Opus 4 <NOREPLY@ANTHROPIC.COM>",
    ],
)
def test_ai_coauthor_trailer_forms_match(trailer: str) -> None:
    assert _hits("ai-slop.co-authored-by-ai", "message", f"feat(x) Add y\n\n{trailer}")


def test_human_coauthor_trailer_does_not_match() -> None:
    human = "feat(x) Add y\n\nCo-authored-by: Ada Lovelace <ada@example.com>"
    assert not _hits("ai-slop.co-authored-by-ai", "message", human)


def _repo(tmp_path: Path, name: str, text: str) -> None:
    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, env=ENV, check=True, capture_output=True)

    run("init", "-q")
    (tmp_path / name).write_text(text + "\n")
    run("add", "--", name)
    run("commit", "-q", "-m", "x")


def test_present_keeps_hostile_text_and_paths_as_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    name = "-odd name.txt"
    payload = 'TODO: revisit $(touch pwned) `touch pwned` "; touch pwned #'
    _repo(tmp_path, name, payload)
    gone = {"file": name, "text": "TODO: revisit later"}
    kept = {"file": name, "text": payload}
    findings = tmp_path / "f.json"
    findings.write_text(json.dumps({"findings": [kept, gone]}))
    monkeypatch.chdir(tmp_path)
    assert detect.main(["present", "--findings", str(findings)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["findings"] == [kept]
    assert not (tmp_path / "pwned").exists()


def test_out_writes_json_and_prints_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    reg = tmp_path / "r.yml"
    reg.write_text(MINI)
    target = tmp_path / "a.txt"
    target.write_text("# TODO: revisit later\n")
    dest = tmp_path / "out.json"
    args = ["files", "--registry", str(reg), "--out", str(dest), str(target)]
    assert detect.main(args) == 0
    shown = capsys.readouterr().out
    assert "findings: 1" in shown
    assert not shown.lstrip().startswith("{")
    assert json.loads(dest.read_text())["findings"][0]["tier"] == "B"
