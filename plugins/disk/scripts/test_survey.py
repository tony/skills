"""Survey: floor, depth, hardlink and symlink handling."""

# ruff: noqa: S101, INP001, D103

import json
import os
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest
import survey


def run(
    root: Path,
    depth: int,
    pct: float,
    limit: float = 90.0,
    skip: str = "/mnt",
) -> dict[str, Any]:
    out = survey.survey(str(root), depth, pct, limit, skip)
    return json.loads(json.dumps(out))


LIMIT = 400_000


def test_hardlink_counted_once_and_symlink_not_followed(tmp_path: Path) -> None:
    big = tmp_path / "a" / "big"
    big.parent.mkdir()
    big.write_bytes(b"x" * 200_000)
    os.link(big, tmp_path / "b_link")
    (tmp_path / "ln").symlink_to(tmp_path / "a")
    out = run(tmp_path, 3, 0)
    sizes = {d["path"]: d["bytes"] for d in out["directories"]}
    root = sizes[str(tmp_path.resolve())]
    assert sizes[str(tmp_path.resolve() / "a")] < LIMIT
    assert root < LIMIT


def test_floor_filters_and_depth_limits(tmp_path: Path) -> None:
    deep = tmp_path / "d1" / "d2" / "d3" / "d4"
    deep.mkdir(parents=True)
    (deep / "f").write_bytes(b"x" * 100_000)
    paths = {d["path"] for d in run(tmp_path, 2, 0)["directories"]}
    assert str(deep.resolve()) not in paths
    assert str((tmp_path / "d1").resolve()) in paths
    assert run(tmp_path, 2, 100)["directories"] == []


def test_unreadable_directory_is_reported(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        out = run(tmp_path, 3, 0)
    finally:
        locked.chmod(0o700)
    if os.geteuid() != 0:
        assert any("locked" in e for e in out["errors"])
        assert out["complete"] is False


def test_skip_root_is_skipped_unless_survey_is_inside_it(tmp_path: Path) -> None:
    mnt = tmp_path / "mnt"
    (mnt / "c").mkdir(parents=True)
    (mnt / "c" / "f").write_bytes(b"x" * 100_000)
    outside = run(tmp_path, 3, 0, skip=str(mnt.resolve()))
    assert outside["skipped"] == [str(mnt.resolve())]
    assert all("/mnt/c" not in d["path"] for d in outside["directories"])
    inside = run(mnt / "c", 3, 0, skip=str(mnt.resolve()))
    assert inside["skipped"] == []
    assert inside["directories"]


def test_expired_time_limit_marks_result_incomplete(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    assert run(tmp_path, 3, 0)["complete"] is True
    out = run(tmp_path, 3, 0, limit=-1)
    assert out["complete"] is False


def test_repeated_directory_inode_is_counted_once(tmp_path: Path) -> None:
    file_bytes = 100_000
    (tmp_path / "payload").write_bytes(b"x" * file_bytes)
    walker = survey.Walker(tmp_path.stat().st_dev, 3)
    assert walker.walk(str(tmp_path)) >= file_bytes
    assert walker.walk(str(tmp_path)) == 0
    assert walker.skipped == [str(tmp_path)]


def test_listing_stops_at_the_deadline_and_cli_rejects_bad_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in "abc":
        (tmp_path / name).write_bytes(b"x")
    ticks = iter([0.0, 0.0, 0.0, 9.0, 9.0, 9.0, 9.0, 9.0])
    monkeypatch.setattr(survey, "time", SimpleNamespace(monotonic=lambda: next(ticks, 9.0)))
    walker = survey.Walker(tmp_path.stat().st_dev, 3, deadline=1.0)
    _ = walker.walk(str(tmp_path))
    assert walker.timed_out
    for flag, value in (("--depth", "-1"), ("--time-limit", "nan"), ("--time-limit", "-1")):
        with pytest.raises(SystemExit):
            survey.main(["survey.py", str(tmp_path), flag, value])
        assert "must be" in capsys.readouterr().err


def test_largest_ranks_below_floor_directories(tmp_path: Path) -> None:
    (tmp_path / "small").mkdir()
    (tmp_path / "small" / "f").write_bytes(b"x" * 20_000)
    (tmp_path / "bigger").mkdir()
    (tmp_path / "bigger" / "f").write_bytes(b"x" * 90_000)
    out = run(tmp_path, 3, 99)
    assert out["directories"] == []
    ranked = [d["path"] for d in out["largest"]]
    assert ranked == [str(tmp_path / "bigger"), str(tmp_path / "small")]
