"""Tests for goal.py."""

# ruff: noqa: S101, INP001
from __future__ import annotations

import json
import typing as t

import goal  # pyright: ignore[reportImplicitRelativeImport]

if t.TYPE_CHECKING:
    import pathlib

    import pytest


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
