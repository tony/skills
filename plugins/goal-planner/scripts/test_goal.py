"""Tests for goal.py."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import json
import sqlite3
import typing as t
from datetime import date

import goal  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if t.TYPE_CHECKING:
    import pathlib

NEXT_AFTER_GAP = 4


def _skill_file(path: pathlib.Path, name: str, *, gated: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    flag = "disable-model-invocation: true\n" if gated else ""
    front = f'---\nname: {name}\ndescription: "Use when testing."\n{flag}---\n\nBody.\n'
    _ = (path / "SKILL.md").write_text(front, encoding="utf-8")


def test_measure_counts_utf16_for_claude() -> None:
    """An astral character counts once as a code point and twice in UTF-16."""
    text = "/goal ship it \N{ROCKET}"
    result = goal.measure_text(text, "claude")
    assert result["codepoints"] == len(text)
    assert result["utf16"] == len(text) + 1
    assert (result["target"], result["cap"]) == (3800, 4000)


def test_measure_verdicts() -> None:
    """Claude warns past the target and fails past the cap; Codex spills."""
    assert goal.measure_text("x" * 3800, "claude")["verdict"] == "ok"
    assert goal.measure_text("x" * 3801, "claude")["verdict"] == "over-target"
    assert goal.measure_text("x" * 4001, "claude")["verdict"] == "over-cap"
    assert goal.measure_text("x" * 4001, "codex")["verdict"] == "spills"
    assert goal.measure_text("x" * 4001, "codex", spill=False)["verdict"] == "over-cap"


def test_measure_budget_overrides_target() -> None:
    """A budget replaces the Claude target but never the cap."""
    result = goal.measure_text("x" * 3000, "claude", budget=2500)
    assert (result["target"], result["verdict"]) == (2500, "over-target")


def test_measure_cli_exit_codes(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Only a Claude goal over the cap, or a Codex goal that may not spill, fails."""
    path = tmp_path / "g.md"
    _ = path.write_text("x" * 4001, encoding="utf-8")
    assert goal.main(["measure", "--host", "claude", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "over-cap"
    assert goal.main(["measure", "--host", "codex", str(path)]) == 0
    assert goal.main(["measure", "--host", "codex", "--no-spill", str(path)]) == 1


def test_measure_cli_ignores_saved_frontmatter(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A saved goal file is measured by the text a user pastes, not its metadata."""
    path = tmp_path / "parser-001.md"
    _ = path.write_text("---\ntopic: parser\n---\n/goal Fix it.\n", encoding="utf-8")
    assert goal.main(["measure", "--host", "claude", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["codepoints"] == len("/goal Fix it.\n")


def test_catalog_reads_gating(tmp_path: pathlib.Path) -> None:
    """Plugin skills are named plugin:skill and carry their gating flag."""
    base = tmp_path / "cache" / "mkt" / "spike" / "0.1.0" / "skills"
    _skill_file(base / "ratchet", "ratchet")
    _skill_file(base / "bakeoff", "bakeoff", gated=True)
    names = {s.name: s.gated for s in goal.discover_skills([tmp_path / "cache"])}
    assert names == {"spike:ratchet": False, "spike:bakeoff": True}


def test_catalog_keeps_newest_version_only(tmp_path: pathlib.Path) -> None:
    """Only the newest cached version of a plugin counts, compared numerically."""
    for version in ("0.9.0", "0.10.0"):
        _skill_file(
            tmp_path / "cache" / "mkt" / "spike" / version / "skills" / "ratchet", "ratchet"
        )
    skills = goal.discover_skills([tmp_path / "cache"])
    assert [s.name for s in skills] == ["spike:ratchet"]
    assert "0.10.0" in skills[0].path


def test_catalog_reads_bare_skill_dirs(tmp_path: pathlib.Path) -> None:
    """A user skill directory holds unprefixed skills."""
    _skill_file(tmp_path / "skills" / "double-check", "double-check")
    assert [s.name for s in goal.discover_skills([tmp_path / "skills"])] == ["double-check"]


def test_lint_flags_gated_unknown_and_syntax() -> None:
    """Gated, unknown, and wrong-host skill names are errors in a Claude goal."""
    skills = [
        goal.Skill("spike:ratchet", gated=False, path="p"),
        goal.Skill("spike:bakeoff", gated=True, path="p"),
    ]
    text = (
        "/goal Use /spike:bakeoff and /spike:loop and $spike:ratchet. "
        "Done when the tests pass; print the run."
    )
    rules = [e["rule"] for e in goal.lint_goal(text, "claude", skills)["errors"]]
    assert rules.count("gated-skill") == 1
    assert "unknown-skill" in rules
    assert "host-syntax" in rules


def test_lint_codex_slash_syntax_is_a_warning() -> None:
    """Codex reads $plugin:skill, so a slash form only warns."""
    skills = [goal.Skill("spike:ratchet", gated=False, path="p")]
    result = goal.lint_goal("/goal Use /spike:ratchet until tests pass.", "codex", skills)
    assert [w["rule"] for w in result["warnings"]] == ["host-syntax"]
    assert result["errors"] == []


def test_lint_claude_requires_done_when_and_warns_on_bound() -> None:
    """A Claude goal needs a done-when clause and a turn counter with its bound."""
    result = goal.lint_goal("/goal Fix the parser.", "claude", [])
    assert any(e["rule"] == "done-when" for e in result["errors"])
    text = "/goal Fix it. Done when tests pass; print the run. Or stop after 5 turns."
    result = goal.lint_goal(text, "claude", [])
    assert [w["rule"] for w in result["warnings"]] == ["bound"]
    counted = text + " End every turn with `turn N of 5`."
    assert goal.lint_goal(counted, "claude", [])["warnings"] == []


def test_lint_warns_when_done_when_prints_nothing() -> None:
    """The Claude evaluator only sees printed evidence."""
    text = (
        "/goal Fix it. Done when the tests pass. "
        "Stop after 5 turns; end each turn with `turn N of 5`."
    )
    assert [w["rule"] for w in goal.lint_goal(text, "claude", [])["warnings"]] == ["evidence"]


def test_lint_home_path_outside_ledger(tmp_path: pathlib.Path) -> None:
    """A home path warns unless it points into the ledger root."""
    ledger = tmp_path / "Documents"
    inside = f"/goal Read {ledger}/2026-10-24/objectives/p-001.md. Done when done; print it."
    outside = "/goal Read /home/someone/notes.md. Done when done; print it."
    skills: list[goal.Skill] = []
    assert goal.lint_goal(inside, "codex", skills, ledger)["warnings"] == []
    rules = [w["rule"] for w in goal.lint_goal(outside, "codex", skills, ledger)["warnings"]]
    assert rules == ["home-path"]


def test_lint_cli_exit_code(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI exits 1 on any error and prints both lists."""
    path = tmp_path / "g.md"
    _ = path.write_text("/goal Fix the parser.\n", encoding="utf-8")
    assert goal.main(["lint", "--host", "claude", "--catalog-root", str(tmp_path), str(path)]) == 1
    out = t.cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert sorted(out) == ["errors", "warnings"]


def _profile(path: pathlib.Path, documents: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(f"---\ndocuments: {documents}\n---\n", encoding="utf-8")
    return path


def test_root_precedence(tmp_path: pathlib.Path) -> None:
    """A flag beats the environment, which beats the profile, then WSL, then home."""
    nomnt = tmp_path / "nomnt"
    assert goal.resolve_root(str(tmp_path), {}, None, mnt=nomnt) == (tmp_path, "flag")
    env = {"GOAL_PLANNER_ROOT": str(tmp_path)}
    assert goal.resolve_root(None, env, None, mnt=nomnt) == (tmp_path, "env")
    profile = _profile(tmp_path / "cfg" / "profile.md", str(tmp_path / "docs"))
    assert goal.resolve_root(None, {}, profile, mnt=nomnt) == (tmp_path / "docs", "profile")
    auto = _profile(tmp_path / "cfg2" / "profile.md", "auto")
    home = {"HOME": str(tmp_path)}
    assert goal.resolve_root(None, home, auto, mnt=nomnt) == (tmp_path / "Documents", "home")


def test_root_wsl_picks_matching_user(tmp_path: pathlib.Path) -> None:
    """On WSL the Windows profile matching the Linux user wins; service profiles never do."""
    for user in ("ann", "bob", "Public"):
        (tmp_path / user / "Documents").mkdir(parents=True)
    root = goal.resolve_root(None, {"USER": "bob"}, None, mnt=tmp_path)
    assert root == (tmp_path / "bob" / "Documents", "wsl")


def test_root_wsl_ambiguous_raises(tmp_path: pathlib.Path) -> None:
    """Several Windows users and no match is an error naming them."""
    for user in ("ann", "bob"):
        (tmp_path / user / "Documents").mkdir(parents=True)
    with pytest.raises(goal.RootError) as err:
        _ = goal.resolve_root(None, {"USER": "zed"}, None, mnt=tmp_path)
    assert sorted(err.value.candidates) == ["ann", "bob"]


def test_next_number_spans_dates_and_never_refills(tmp_path: pathlib.Path) -> None:
    """Numbering continues past the highest number in any dated folder."""
    for day, number in (("2026-10-20", 1), ("2026-10-22", 3)):
        folder = tmp_path / day / "goals"
        folder.mkdir(parents=True)
        _ = (folder / f"parser-{number:03d}.md").write_text("x", encoding="utf-8")
    assert goal.next_number(tmp_path, "parser", "goal") == NEXT_AFTER_GAP
    assert goal.next_number(tmp_path, "parser", "objective") == 1
    assert goal.next_number(tmp_path, "parse", "goal") == 1


def test_save_writes_frontmatter_and_exact_body(tmp_path: pathlib.Path) -> None:
    """The body under the frontmatter is exactly the text to paste."""
    body = "/goal Fix it.\n"
    meta = {"host": "claude"}
    path = goal.save_entry(tmp_path, "parser", "goal", body, meta, date(2026, 10, 24))
    assert path == tmp_path / "2026-10-24" / "goals" / "parser-001.md"
    text = path.read_text(encoding="utf-8")
    saved = goal.parse_frontmatter(text)
    assert (saved["number"], saved["status"], saved["utf16"]) == ("1", "draft", "14")
    assert list(saved)[:5] == ["topic", "kind", "number", "host", "status"]
    assert goal.strip_frontmatter(text) == body


def _always_one(*_args: object) -> int:
    return 1


def test_save_never_overwrites_on_collision(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A number taken by another session moves the save to the next number."""
    folder = tmp_path / "2026-10-24" / "goals"
    folder.mkdir(parents=True)
    _ = (folder / "parser-001.md").write_text("theirs", encoding="utf-8")
    monkeypatch.setattr(goal, "next_number", _always_one)
    path = goal.save_entry(tmp_path, "parser", "goal", "/goal Mine.\n", {}, date(2026, 10, 24))
    assert path.name == "parser-002.md"
    assert (folder / "parser-001.md").read_text(encoding="utf-8") == "theirs"


def test_save_rejects_bad_topic(tmp_path: pathlib.Path) -> None:
    """Topics are kebab-case slugs."""
    with pytest.raises(ValueError, match="topic"):
        _ = goal.save_entry(tmp_path, "Parser Work", "goal", "x", {}, date(2026, 10, 24))


def _codex_home(tmp_path: pathlib.Path) -> pathlib.Path:
    home = tmp_path / "codex"
    attachment = home / "attachments" / "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    attachment.mkdir(parents=True)
    spilled = attachment / "goal-objective.md"
    _ = spilled.write_text("FULL OBJECTIVE TEXT", encoding="utf-8")
    con = sqlite3.connect(home / "goals_1.sqlite")
    columns = (
        "thread_id text, goal_id text, objective text, status text, token_budget integer,",
        "tokens_used integer, time_used_seconds integer, created_at_ms integer,",
        "updated_at_ms integer",
    )
    _ = con.execute(f"create table thread_goals ({' '.join(columns)})")
    pointer = "Read the Codex goal objective file at {} before continuing."
    rows = [
        ("t1", "g1", pointer.format(spilled), "complete", 1790000000000),
        (
            "t2",
            "g2",
            pointer.format(home / "attachments" / "gone" / "goal-objective.md"),
            "paused",
            1790000100000,
        ),
        ("t3", "g3", "Fix the parser.", "active", 1790000200000),
    ]
    insert = (
        "insert into thread_goals (thread_id, goal_id, objective, status, updated_at_ms)",
        "values (?, ?, ?, ?, ?)",
    )
    _ = con.executemany(" ".join(insert), rows)
    con.commit()
    con.close()
    return home


def test_find_resolves_codex_pointer_and_reports_missing(tmp_path: pathlib.Path) -> None:
    """A pointer objective reads its file; a gone file is reported, not raised."""
    hits = goal.find_goals(None, _codex_home(tmp_path), None, None, None)
    by_ref = {h["ref"]: h for h in hits if h["source"] == "codex-db"}
    assert by_ref["t1"]["text"] == "FULL OBJECTIVE TEXT"
    assert by_ref["t1"]["missing"] is False
    assert by_ref["t2"]["missing"] is True
    assert by_ref["t3"]["text"] == "Fix the parser."
    assert [h["text"] for h in hits if h["source"] == "codex-attachment"] == ["FULL OBJECTIVE TEXT"]


def test_find_reads_history_goal_prompts(tmp_path: pathlib.Path) -> None:
    """Only prompt records that set a goal come back from a history export."""
    export = tmp_path / "history.ndjson"
    records: list[dict[str, object]] = [
        {"kind": "prompt", "text": "/goal Fix the parser.", "timestamp": "2026-10-20T10:00:00Z"},
        {"kind": "prompt", "text": "print a goal", "timestamp": "2026-10-20T09:00:00Z"},
        {"type": "summary", "data": {}},
    ]
    _ = export.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    hits = goal.find_goals(None, None, export, None, None)
    assert [(h["source"], h["text"]) for h in hits] == [("history", "/goal Fix the parser.")]


def test_find_filters_ledger_by_text_and_topic(tmp_path: pathlib.Path) -> None:
    """Text matches case-insensitively; topic narrows ledger hits only."""
    day = date(2026, 10, 24)
    _ = goal.save_entry(tmp_path, "parser", "goal", "/goal Fix the Parser.\n", {}, day)
    _ = goal.save_entry(tmp_path, "docs", "goal", "/goal Rewrite the docs.\n", {}, day)
    texts = [h["text"] for h in goal.find_goals(tmp_path, None, None, "parser", None)]
    assert texts == ["/goal Fix the Parser.\n"]
    assert len(goal.find_goals(tmp_path, None, None, None, "docs")) == 1


def test_ledger_cli_save_then_list(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI saves a goal from a file and lists it back."""
    draft = tmp_path / "draft.md"
    _ = draft.write_text("/goal Fix it.\n", encoding="utf-8")
    root = str(tmp_path / "Documents")
    args = ["ledger", "save", "--root", root, "--topic", "parser", "--kind", "goal"]
    assert goal.main([*args, "--host", "claude", "--date", "2026-10-24", str(draft)]) == 0
    saved = t.cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert str(saved["path"]).endswith("2026-10-24/goals/parser-001.md")
    assert goal.main(["ledger", "list", "--root", root]) == 0
    listed = t.cast("list[dict[str, object]]", json.loads(capsys.readouterr().out))
    assert [(e["topic"], e["number"], e["kind"]) for e in listed] == [("parser", 1, "goal")]


def _prompt(text: str, cwd: str, day: str) -> dict[str, object]:
    return {
        "kind": "prompt",
        "agent": "claude",
        "text": text,
        "timestamp": f"{day}T10:00:00Z",
        "origin": {"cwd": cwd},
    }


def test_harvest_applies_sweep_bar(tmp_path: pathlib.Path) -> None:
    """A sentence needs 5 prompts, 2 projects, and a use within 30 days to count."""
    kept = "Effort and blast radius do not matter for this package at all."
    few = "Use the private mirror remote for every single push you make here."
    lonely = "Run the full benchmark matrix against every port before signing off."
    stale = "Soft reset and force push over every change that did not work out."
    records = [_prompt(f"/goal {kept} One.", f"~/p{i % 2}", "2026-10-20") for i in range(5)]
    records += [_prompt(f"/goal {few}", f"~/p{i % 2}", "2026-10-20") for i in range(4)]
    records += [_prompt(f"/goal {lonely}", "~/p0", "2026-10-20") for _ in range(5)]
    records += [_prompt(f"/goal {stale}", f"~/p{i % 2}", "2026-08-01") for i in range(5)]
    export = tmp_path / "history.ndjson"
    _ = export.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    found = goal.harvest(export, today=date(2026, 10, 24))
    assert [f["sentence"] for f in found] == [kept.lower()]
    assert (found[0]["count"], found[0]["projects"], found[0]["last_seen"]) == (5, 2, "2026-10-20")


def test_ledger_save_dry_run_prints_content_without_writing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dry run names the next path and the exact file text, and writes nothing."""
    draft = tmp_path / "draft.md"
    _ = draft.write_text("/goal Fix it.\n", encoding="utf-8")
    root = tmp_path / "Documents"
    args = ["ledger", "save", "--root", str(root), "--topic", "parser", "--kind", "goal"]
    assert goal.main([*args, "--date", "2026-10-24", "--dry-run", str(draft)]) == 0
    planned = t.cast("dict[str, object]", json.loads(capsys.readouterr().out))
    assert str(planned["path"]).endswith("2026-10-24/goals/parser-001.md")
    content = str(planned["content"])
    assert goal.strip_frontmatter(content) == "/goal Fix it.\n"
    assert goal.parse_frontmatter(content)["number"] == "1"
    assert not root.exists()
