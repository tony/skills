"""Critical contracts for goal sizing, immutable bundles, and approved settings."""

# ruff: noqa: S101, INP001, PLR2004, SLF001
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import io
import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import planner  # pyright: ignore[reportImplicitRelativeImport]
import pytest


def _draft(root: Path, **overrides: object) -> planner.Draft:
    request: dict[str, object] = {
        "host": "claude",
        "topic": "release",
        "body": "Finish the reviewed release.",
        "documents_root": str(root),
        "date": "2026-10-24",
    }
    request.update(overrides)
    return planner.parse_request(request)


def _path(result: dict[str, object], key: str) -> Path:
    return Path(cast("str", result[key]))


def _pair(root: Path, **overrides: object) -> planner.Draft:
    fields: dict[str, object] = {
        "body": "Complete every requirement. {{GOAL_SPEC}}",
        "specification": "# Contract\nShip it.\n",
    }
    fields.update(overrides)
    return _draft(root, **fields)


def test_unicode_budget_covers_prefix_newlines_and_surrogates(tmp_path: Path) -> None:
    """Astral characters consume two UTF-16 units without losing their full text."""
    result = planner.render(_draft(tmp_path, body="a" * 3793 + "\n"))
    assert result["ready"] is True
    counts = cast("dict[str, object]", result["measurements"])
    assert counts["payload"] == {"codepoints": 3800, "utf16": 3800}
    assert counts["condition"] == {"codepoints": 3794, "utf16": 3794}
    too_long = planner.render(_draft(tmp_path, body="a" * 3793 + "\U0001f642"), save=True)
    assert too_long["ready"] is False
    assert too_long["payload"] == "/goal " + "a" * 3793 + "\U0001f642"
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(planner.PlannerError, match="surrogate"):
        _draft(tmp_path, body="invalid \ud800")


@pytest.mark.parametrize(
    ("maximum", "spend", "strict", "expected"),
    [
        (None, False, False, 3800),
        (3999, False, True, 3800),
        (2000, True, False, 2000),
        (None, True, True, 3999),
        (5000, True, False, 4000),
    ],
)
def test_reserve_requires_explicit_override(
    maximum: int | None,
    spend: bool,
    strict: bool,
    expected: int,
) -> None:
    """A generic under-4000 instruction cannot consume the default reserve."""
    assert planner.budget("claude", maximum, spend, strict) == expected


def test_codex_stays_unabridged_and_topic_prefixes_are_independent(tmp_path: Path) -> None:
    """Codex saves a complete long objective and distinct slug lineages stay separate."""
    planner.render(_draft(tmp_path, topic="release-notes"), save=True)
    body = "Complete the contract.\n" * 300
    result = planner.render(_draft(tmp_path, host="codex", body=body), save=True)
    assert result["ready"] is True
    assert result["revision"] == 1
    assert result["spec_path"] is None
    assert _path(result, "goal_path").read_bytes() == ("/goal " + body).encode()


def test_pair_print_equality_noop_and_changed_spec_across_dates(tmp_path: Path) -> None:
    """Reprinting reads saved bytes; changing only the contract preserves the prior pair."""
    first = planner.render(_pair(tmp_path), save=True)
    assert first["requested_date"] == "2026-10-24"
    goal = _path(first, "goal_path")
    spec = _path(first, "spec_path")
    assert first["ready"] is True
    assert goal.read_bytes() == cast("str", first["payload"]).encode()
    assert str(spec) in cast("str", first["payload"])
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file()}
    repeated = planner.render(_pair(tmp_path, date="2026-10-25"), save=True)
    assert repeated["requested_date"] == "2026-10-25"
    assert repeated["reused"] is True
    assert repeated["payload"] == first["payload"]
    assert not (tmp_path / "2026-10-25").exists()
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
    changed = planner.render(
        _pair(tmp_path, date="2026-10-25", specification="New contract"), save=True
    )
    assert changed["revision"] == 2
    assert str(goal) in cast("str", changed["payload"])
    assert _path(changed, "spec_path").name == "release-002.md"
    assert planner.inspect_goal(_path(changed, "goal_path")).revision == 2
    assert goal.read_bytes() == before[goal][0]
    spec.write_text("changed behind the launcher's back", encoding="utf-8")
    with pytest.raises(planner.PlannerError, match="digest changed"):
        planner.render(_pair(tmp_path), save=True)


def test_interruption_never_publishes_or_reuses_partial_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interrupted spec remains occupied and is reported by the next successful save."""
    link = os.link

    def interrupted(source: str, path: Path) -> None:
        if path.parent.name == "goals":
            message = "simulated disk failure after the specification"
            raise OSError(message)
        link(source, path)

    monkeypatch.setattr(os, "link", interrupted)
    failed = planner.render(_pair(tmp_path), save=True)
    assert failed["ready"] is False
    assert failed["payload"]
    assert not list(tmp_path.glob("*/goals/*.md"))
    assert list(tmp_path.glob("*/goal-specs/*.md"))
    monkeypatch.setattr(os, "link", link)
    result = planner.render(_pair(tmp_path, date="2026-10-25"), save=True)
    assert result["revision"] == 2
    assert result["ready"] is True
    assert result["incomplete_revisions"]
    assert not result["reused"]


def test_interrupted_response_reuses_the_published_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publishing the final goal completes the pair even if its response is interrupted."""
    link = os.link

    def interrupted(source: str, path: Path) -> None:
        link(source, path)
        if path.parent.name == "goals":
            message = "simulated interruption after publication"
            raise OSError(message)

    monkeypatch.setattr(os, "link", interrupted)
    failed = planner.render(_pair(tmp_path), save=True)
    assert failed["ready"] is False
    monkeypatch.setattr(os, "link", link)
    repeated = planner.render(_pair(tmp_path, date="2026-10-25"), save=True)
    assert repeated["ready"] is True
    assert repeated["reused"] is True
    assert repeated["payload"] == failed["payload"]
    assert repeated["revision"] == 1
    assert not (tmp_path / "2026-10-25").exists()


def test_concurrent_cross_date_allocations_retry_stale_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two writers observing the same initial revision cannot publish the same number."""
    inventory = planner._inventory
    barrier = threading.Barrier(2)
    seen = threading.local()

    def concurrent(draft: planner.Draft) -> tuple[list[planner.Artifact], set[int], list[str]]:
        result = inventory(draft)
        if not getattr(seen, "entered", False):
            seen.entered = True
            barrier.wait(timeout=1)
        return result

    monkeypatch.setattr(planner, "_inventory", concurrent)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                planner.render, _pair(tmp_path, date=date, specification=date), save=True
            )
            for date in ("2026-10-24", "2026-10-25")
        ]
        results = [future.result(timeout=1) for future in futures]
    assert {result["revision"] for result in results} == {1, 2}
    assert all(result["ready"] for result in results)
    for result in results:
        assert planner.inspect_goal(_path(result, "goal_path")).payload == result["payload"]


def test_matching_revision_elsewhere_does_not_hide_an_incomplete_pair(tmp_path: Path) -> None:
    """An orphan or local claim remains visible beside a completed revision elsewhere."""
    original = planner.render(_pair(tmp_path / "original"), save=True)
    orphan = tmp_path / "original/2026-10-25/goal-specs/release-001.md"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(_path(original, "spec_path").read_bytes())
    repeated = planner.render(_pair(tmp_path / "original"))
    assert str(orphan) in cast("list[str]", repeated["incomplete_revisions"])
    claim = tmp_path / "imported/.goal-reservations/release-001.reservation"
    claim.mkdir(parents=True)
    imported = planner.render(_pair(tmp_path / "imported", predecessors=[original["goal_path"]]))
    assert str(claim) in cast("list[str]", imported["incomplete_revisions"])


def test_imported_predecessor_rebinds_and_duplicate_lineages_fail(tmp_path: Path) -> None:
    """A new selected root receives a new pair; conflicting same-number histories stop."""
    original = planner.render(_pair(tmp_path / "old"), save=True)
    moved = planner.render(
        _pair(tmp_path / "new", predecessors=[original["goal_path"]]),
        save=True,
    )
    assert moved["revision"] == 2
    assert not moved["reused"]
    assert str(tmp_path / "new") in cast("str", moved["payload"])
    standalone = planner.render(_draft(tmp_path / "conflict"), save=True)
    duplicate = tmp_path / "conflict/2026-10-25/goals/release-001.md"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(_path(standalone, "goal_path").read_bytes())
    with pytest.raises(planner.PlannerError, match="Conflicting revision"):
        planner.render(_draft(tmp_path / "conflict"))


def test_collision_reuses_a_matching_completion_that_became_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale reader rechecks completed content after an exclusive allocation collision."""
    original = planner.render(_pair(tmp_path), save=True)
    inventory = planner._inventory
    stale = True

    def observed(draft: planner.Draft) -> tuple[list[planner.Artifact], set[int], list[str]]:
        nonlocal stale
        if stale:
            stale = False
            return [], set(), []
        return inventory(draft)

    monkeypatch.setattr(planner, "_inventory", observed)
    repeated = planner.render(_pair(tmp_path, date="2026-10-25"), save=True)
    assert repeated["reused"] is True
    assert repeated["goal_path"] == original["goal_path"]
    assert not (tmp_path / "2026-10-25").exists()


def test_revision_width_expands_without_filling_known_gaps(tmp_path: Path) -> None:
    """An imported high revision keeps its series beyond three digits."""
    predecessor = tmp_path / "2026-10-23/goals/release-999.md"
    predecessor.parent.mkdir(parents=True)
    predecessor.write_text("/goal Earlier contract.", encoding="utf-8")
    result = planner.render(_draft(tmp_path), save=True)
    assert result["revision"] == 1000
    assert _path(result, "goal_path").name == "release-1000.md"


@pytest.mark.parametrize("whole_root", [False, True])
def test_offline_transfer_verifies_copied_contract_then_rebinds(
    tmp_path: Path,
    whole_root: bool,
) -> None:
    """A copied pair can recover with its source gone, while the stale launcher stays invalid."""
    old = tmp_path / "old"
    new = tmp_path / "new"
    original = planner.render(_pair(old), save=True)
    if whole_root:
        shutil.copytree(old, new)
    else:
        shutil.copytree(old / "2026-10-24", new / "2026-10-24")
    shutil.rmtree(old)
    copied_goal = new / "2026-10-24/goals/release-001.md"
    copied_spec = new / "2026-10-24/goal-specs/release-001.md"
    before = (copied_goal.read_bytes(), copied_spec.read_bytes())
    with pytest.raises(planner.PlannerError, match=r"former Documents root|Companion locator"):
        planner.inspect_goal(copied_goal)
    result = planner.render(_pair(new, date="2026-10-25"), save=True)
    assert result["ready"] is True
    assert result["revision"] == 2
    assert not result["reused"]
    assert planner.inspect_goal(_path(result, "goal_path")).payload == result["payload"]
    assert str(new) in cast("str", result["payload"])
    assert str(old) not in cast("str", result["payload"])
    assert (copied_goal.read_bytes(), copied_spec.read_bytes()) == before
    assert copied_goal.read_text() == original["payload"]
    repeated = planner.render(_pair(new), save=True)
    assert repeated["reused"] is True
    assert repeated["revision"] == 2


def test_unrelated_invalid_date_directory_does_not_block_lineage(tmp_path: Path) -> None:
    """Only actual calendar-date directories participate in revision allocation."""
    (tmp_path / "2026-02-30").mkdir()
    result = planner.render(_draft(tmp_path), save=True)
    assert result["ready"] is True
    assert result["revision"] == 1


@pytest.mark.parametrize("location", ["root", "date", "goals", "goal-specs", "reservation"])
def test_symlink_destinations_are_rejected_without_touching_foreign_files(
    tmp_path: Path,
    location: str,
) -> None:
    """Every writable directory boundary rejects links into a foreign destination."""
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    root = tmp_path / "documents"
    targets = {
        "root": root,
        "date": root / "2026-10-24",
        "goals": root / "2026-10-24/goals",
        "goal-specs": root / "2026-10-24/goal-specs",
        "reservation": root / ".goal-reservations",
    }
    target = targets[location]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(planner.PlannerError, match="Symlink"):
        planner.render(_pair(root), save=True)
    assert list(foreign.iterdir()) == []


def test_bad_paths_missing_companions_and_foreign_targets_fail(tmp_path: Path) -> None:
    """Traversal, orphaned contracts, and unrelated existing files cannot be overwritten."""
    with pytest.raises(planner.PlannerError, match="topic"):
        _draft(tmp_path, topic="../escape")
    with pytest.raises(planner.PlannerError, match="traversal"):
        _draft(tmp_path / ".." / "escape")
    first = planner.render(_pair(tmp_path / "pair"), save=True)
    _path(first, "spec_path").unlink()
    with pytest.raises(planner.PlannerError, match="Required regular file"):
        planner.inspect_goal(_path(first, "goal_path"))
    target = tmp_path / "foreign/2026-10-24/goals/release-001.md"
    target.parent.mkdir(parents=True)
    target.write_text("Unrelated notes", encoding="utf-8")
    with pytest.raises(planner.PlannerError, match="Foreign"):
        planner.render(_draft(tmp_path / "foreign"), save=True)
    assert target.read_text() == "Unrelated notes"


def test_profiles_require_explicit_consent_and_separate_bindings(tmp_path: Path) -> None:
    """Approval applies to exact settings; portable profiles cannot carry machine roots."""
    profile: dict[str, object] = {
        "schema_version": 1,
        "kind": "profile",
        "approved": True,
        "name": "portable",
        "defaults": {"host": "claude", "save": True, "max_chars": 3800},
        "principles": ["Show evidence for acceptance."],
    }
    path = tmp_path / "settings/profile.json"
    with pytest.raises(planner.PlannerError, match="requires --approved"):
        planner.save_settings(path, profile, approved=False, replace=False)
    assert not path.parent.exists()
    planner.save_settings(path, profile, approved=True, replace=False)
    with pytest.raises(planner.PlannerError, match="already exist"):
        planner.save_settings(path, profile, approved=True, replace=False)
    with pytest.raises(planner.PlannerError, match="Unknown profile fields"):
        planner.validate_settings({**profile, "documents_root": str(tmp_path)}, "profile")
    with pytest.raises(planner.PlannerError, match="explicit approval"):
        planner.validate_settings({**profile, "approved": False}, "profile")
    bindings: dict[str, object] = {
        "schema_version": 1,
        "kind": "bindings",
        "approved": True,
        "documents_root": str(tmp_path),
    }
    with pytest.raises(planner.PlannerError, match="must be absolute"):
        planner.validate_settings({**bindings, "documents_root": "Documents"}, "bindings")
    with pytest.raises(planner.PlannerError, match="Unknown bindings fields"):
        planner.save_settings(path, bindings, approved=True, replace=True)
    profile["principles"] = ["Preserve the approved acceptance criteria."]
    planner.save_settings(path, profile, approved=True, replace=True)
    assert json.loads(path.read_text()) == profile


def test_cli_stdin_stdout_only_and_missing_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Structured stdin produces the complete payload without even a request scratch file."""
    request = {
        "host": "claude",
        "topic": "release",
        "body": "Full draft.",
        "documents_root": str(tmp_path / "documents"),
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    assert planner.main(["render", "--input", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["payload"] == "/goal Full draft."
    assert list(tmp_path.iterdir()) == []
    request.update({"body": "Read {{GOAL_SPEC}}", "specification": "Complete contract"})
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(request)))
    assert planner.main(["render", "--input", "-"]) == 2
    assert json.loads(capsys.readouterr().out)["ready"] is False
    assert list(tmp_path.iterdir()) == []
    assert planner.main(["profile", "read", "--path", str(tmp_path / "missing.json")]) == 2
    assert "No such file" in capsys.readouterr().out


def test_request_parser_rejects_silent_flag_and_schema_coercion(tmp_path: Path) -> None:
    """Ambiguous flags, malformed types, and duplicate placeholders stop before writes."""
    for override in (
        {"save": True},
        {"max_chars": True},
        {"spend_reserve": "yes"},
        {"predecessors": "old.md"},
        {"date": "2026-2-1"},
        {"body": "{{GOAL_SPEC}}"},
        {"specification": "Not referenced"},
    ):
        with pytest.raises(planner.PlannerError):
            _draft(tmp_path, **override)
    assert list(tmp_path.iterdir()) == []
