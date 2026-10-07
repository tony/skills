"""Snapshot/diff isolates the skill's edits from earlier uncommitted ones."""

# ruff: noqa: S101, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest
import skill_diff  # pyright: ignore[reportImplicitRelativeImport]

EXIT_MISSING = 2


def test_diff_excludes_earlier_edits_and_temp_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_text("one\nfiller\nthree\n")
    root, out = skill_diff.snapshot([target], tmp_path)
    target.write_text("one\nthree\n")
    text = skill_diff.diff(root, work=False)
    assert "--- a/SKILL.md" in text
    assert "-filler" in text
    assert str(root) not in text
    skill_diff.clean(root)
    assert not root.exists()
    assert out[0][1] == "SKILL.md"


def test_work_diff_leaves_target_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_text("a\nb\n")
    root, out = skill_diff.snapshot([target], tmp_path)
    out[0][0].write_text("a\n")
    assert "-b" in skill_diff.diff(root, work=True)
    assert target.read_text() == "a\nb\n"
    skill_diff.clean(root)


def test_clean_refuses_foreign_dir(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        skill_diff.clean(tmp_path)


def test_missing_target_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_text("a\n")
    root, _ = skill_diff.snapshot([target], tmp_path)
    target.unlink()
    assert skill_diff.main(["diff", str(root)]) == EXIT_MISSING
    skill_diff.clean(root)


def test_stdin_snapshot_cleans_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root, out = skill_diff.snapshot([], tmp_path, "a\nb\n")
    out[0][0].write_text("a\n")
    assert out[0][1] == "SKILL.md"
    assert "-b" in skill_diff.diff(root, work=True)
    skill_diff.clean(root)
    assert not root.exists()
