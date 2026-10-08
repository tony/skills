"""Delete guard: scope, keeper, and symlink refusals."""

# ruff: noqa: S101, INP001, D103, TC002, TC003
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import os
from pathlib import Path

import guarded_rm  # pyright: ignore[reportImplicitRelativeImport]
import pytest

REFUSED = guarded_rm.EXIT_REFUSED
OK = guarded_rm.EXIT_OK


def run(*args: str) -> int:
    return guarded_rm.main(["guarded_rm.py", *args])


def test_listing_without_delete_keeps_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "s" / "cache").mkdir(parents=True)
    (tmp_path / "s" / "cache" / "f").write_text("x")
    assert run("--scope", str(tmp_path / "s"), str(tmp_path / "s" / "cache")) == OK
    assert "  f" in capsys.readouterr().out
    assert (tmp_path / "s" / "cache" / "f").exists()


def test_delete_removes_target_only(tmp_path: Path) -> None:
    (tmp_path / "s" / "cache").mkdir(parents=True)
    (tmp_path / "s" / "cache" / "f").write_text("x")
    (tmp_path / "s" / "other").write_text("y")
    args = ["--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "s" / "cache")]
    assert run(*args) == OK
    assert not (tmp_path / "s" / "cache").exists()
    assert (tmp_path / "s" / "other").exists()


def test_symlink_out_of_scope_is_refused(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "precious").write_text("x")
    (tmp_path / "s" / "link").symlink_to(tmp_path / "out")
    assert run("--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "s" / "link")) == REFUSED
    assert (tmp_path / "out" / "precious").exists()


def test_scope_root_and_outside_are_refused(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    (tmp_path / "o").mkdir()
    assert run("--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "s")) == REFUSED
    assert run("--scope", str(tmp_path / "s"), "--delete", str(tmp_path / "o")) == REFUSED
    assert (tmp_path / "s").exists()
    assert (tmp_path / "o").exists()


def test_keeper_overlap_is_refused(tmp_path: Path) -> None:
    (tmp_path / "s" / "a" / "keep").mkdir(parents=True)
    scope = str(tmp_path / "s")
    keeper = str(tmp_path / "s" / "a" / "keep")
    assert (
        run("--scope", scope, "--keeper", keeper, "--delete", str(tmp_path / "s" / "a")) == REFUSED
    )
    assert run("--scope", scope, "--keeper", keeper, "--delete", keeper) == REFUSED
    assert (tmp_path / "s" / "a" / "keep").exists()


def test_missing_target_is_refused(tmp_path: Path) -> None:
    (tmp_path / "s").mkdir()
    assert run("--scope", str(tmp_path / "s"), str(tmp_path / "s" / "nope")) == REFUSED


def test_refuses_mount_point_inside_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "s" / "cache"
    (cache / "mnt").mkdir(parents=True)
    real_lstat = os.lstat

    def fake_lstat(path: str) -> object:
        st = real_lstat(path)
        if str(path).endswith("mnt"):
            return type("St", (), {"st_dev": st.st_dev + 1})()
        return st

    monkeypatch.setattr(os, "lstat", fake_lstat)
    assert run("--scope", str(tmp_path / "s"), "--delete", str(cache)) == REFUSED
    assert (cache / "mnt").exists()


def test_sub_gib_sizes_use_mib_and_kib() -> None:
    assert guarded_rm.human(8 * 1024) == "8 KiB"
    assert guarded_rm.human(3 * 2**20) == "3.0 MiB"
    assert guarded_rm.human(2 * 2**30) == "2.00 GiB"
