"""Survey: floor, depth, hardlink and symlink handling."""

# ruff: noqa: S101, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import survey  # pyright: ignore[reportImplicitRelativeImport]


def run(root: Path, depth: int, pct: float) -> dict[str, Any]:  # pyright: ignore[reportExplicitAny]
    return json.loads(json.dumps(survey.survey(str(root), depth, pct)))


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
