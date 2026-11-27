"""Tests for concept_sets.py: the sets gate and the catalog diff."""

# ruff: noqa: S101, INP001, PLR2004
import json
from typing import TYPE_CHECKING

import concept_sets

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_SOURCE: dict[str, object] = {
    "source": "maslow-1943",
    "ref": "Psychological Review 50(4)",
    "commit": "",
    "scope": "whole article",
    "locator_kind": "page",
    "read": True,
    "why": "",
}


def _set(rid: str, labels: list[str], **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "schema": 1,
        "id": rid,
        "name": rid.replace("-", " "),
        "aliases": [],
        "parent": "",
        "variant_of": "",
        "framework": "Test theory",
        "author": "A. Author",
        "year": "1950",
        "purpose": "tell the members apart",
        "member_noun": "kinds",
        "stated_count": len(labels),
        "kind": "typology",
        "order": "presentation",
        "standing": "canonical",
        "provenance": "original",
        "members": [{"label": label, "gloss": ""} for label in labels],
        "open": [],
        "cites": [{"source": "maslow-1943", "locator": "p. 372", "quote": "q", "role": "primary"}],
    }
    row.update(extra)
    return row


def _study(tmp_path: Path, sets: list[dict[str, object]], catalog: list[object]) -> Path:
    for name, rows in (("sources", [_SOURCE]), ("sets", sets), ("catalog", catalog)):
        lines = "\n".join(json.dumps(row) for row in rows)
        (tmp_path / f"{name}.jsonl").write_text(lines + "\n", encoding="utf-8")
    return tmp_path


def test_check_passes_a_sound_study(tmp_path: Path) -> None:
    """A study whose rows are complete and linked passes with exit 0."""
    sets = [
        _set("needs", ["Physiological", "Safety"], kind="level", order="rank"),
        _set("subneeds", ["Food", "Water"], parent="needs"),
    ]
    assert concept_sets.main(["check", str(_study(tmp_path, sets, []))]) == 0


def test_check_names_each_broken_rule() -> None:
    """Each planted defect yields its own finding; nothing is silently accepted."""
    sets = [
        _set("axioms", ["First", "Second"], kind="axiom"),
        _set("loop-a", ["x", "y"], parent="loop-b"),
        _set("loop-b", ["x", "y"], parent="loop-a"),
        _set("orphan", ["x", "y"], variant_of="missing"),
        _set("over", ["x", "y", "z"], stated_count=2),
        _set("short", ["x", "y"], stated_count=5),
        _set("undated", ["x", "y"], year="unknown"),
        _set(
            "hearsay",
            ["x", "y"],
            cites=[{"source": "unknown", "locator": "p. 1", "quote": "q", "role": "secondary"}],
        ),
    ]
    findings = concept_sets.check_sets(sets, [_SOURCE])
    expected = [
        "axioms: axiom member 'First' needs its substance",
        "loop-a: parent links loop back to it",
        "orphan: variant_of 'missing' is not another set's id",
        "over: 3 members exceed the stated count 2; record the other enumeration as a variant",
        "short: stated count 5, 2 members recovered; name the gap in open",
        "undated: year unknown; name the unread source in open",
        "hearsay cite 1: source is not a row of sources.jsonl",
        "hearsay: no primary cite; name the gap in open",
    ]
    for line in expected:
        assert line in findings
    marked = _set("short", ["x", "y"], stated_count=5, open=["source lists five; two found"])
    assert concept_sets.check_sets([marked], [_SOURCE]) == []


def test_diff_flags_each_planted_catalog_case(tmp_path: Path) -> None:
    """Uncodified sets, loose members, partial counts, editorial groupings, merged versions."""
    sets = [
        _set("emotions", ["Anger", "Fear", "Joy"]),
        _set("stages-1950", ["Trust", "Autonomy"], kind="stage", order="developmental"),
        _set("stages-1982", ["Trust", "Autonomy", "Wisdom"], variant_of="stages-1950"),
        _set("false-selves", ["Persona", "False self"], provenance="editorial"),
        _set("needs", ["Physiological", "Safety", "Love"]),
    ]
    catalog: list[object] = [
        {"entry": "Anger"},
        {"entry": "Fear"},
        {"entry": "Needs", "members": ["Physiological", "Hunger"], "stated_count": 5},
        {"entry": "Masks", "members": ["Persona", "False self"], "matches": ["false-selves"]},
        {"entry": "Life stages", "members": ["Trust"], "matches": ["stages-1950", "stages-1982"]},
        {"entry": "Ghost", "matches": ["nope"]},
    ]
    study = _study(tmp_path, sets, catalog)
    report = concept_sets.diff_catalog(sets, concept_sets.load_rows(study / "catalog.jsonl")[0])
    assert [row["set"] for row in report["uncodified"]] == ["emotions"]
    assert report["loose_members"] == [
        {"set": "emotions", "name": "emotions", "entries": ["Anger", "Fear"]}
    ]
    partial = {row["entry"]: row for row in report["partial"]}
    assert partial["Needs"]["stated"] == 5
    assert partial["Needs"]["missing"] == {"needs": ["Safety", "Love"]}
    assert partial["Needs"]["extra"] == ["Hunger"]
    assert [row["entry"] for row in report["unsourced_groupings"]] == ["Masks"]
    assert report["merged_versions"] == [
        {"entry": "Life stages", "sets": ["stages-1950", "stages-1982"]}
    ]
    assert report["unknown_matches"] == [{"entry": "Ghost", "ids": ["nope"]}]


def test_diff_without_a_catalog_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A missing input is a refusal on stderr, never an empty report."""
    study = _study(tmp_path, [_set("needs", ["a", "b"])], [])
    (study / "catalog.jsonl").unlink()
    assert concept_sets.main(["diff", str(study)]) == 2
    assert "no catalog.jsonl" in capsys.readouterr().err
