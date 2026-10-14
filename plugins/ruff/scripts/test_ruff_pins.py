"""Tests for ruff_pins.py."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import ruff_pins  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib

    import pytest


def test_sites_finds_each_pin_and_skips_vendored_trees(tmp_path: pathlib.Path) -> None:
    """Metadata, requirements, pre-commit rev and workflow lines are found; .venv is not."""
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\nlint = ["ruff>=0.9.0"]\n')
    (tmp_path / "requirements-ci.txt").write_text("ruff==0.9.1\nblack==1\n")
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.9.2\n"
    )
    flow = tmp_path / ".github" / "workflows"
    flow.mkdir(parents=True)
    (flow / "ci.yml").write_text("      - run: pip install ruff==0.9.3\n")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "pyproject.toml").write_text('x = "ruff>=0.1.0"\n')
    found = {(p, n) for p, n, _ in ruff_pins.sites(str(tmp_path))}
    assert found == {
        ("pyproject.toml", 2),
        ("requirements-ci.txt", 1),
        (".pre-commit-config.yaml", 3),
        (".github/workflows/ci.yml", 1),
    }


def test_locked_reads_lockfile_and_compares(tmp_path: pathlib.Path) -> None:
    """The uv.lock entry is the resolved version; compare says how it sits against the target."""
    (tmp_path / "uv.lock").write_text(
        '[[package]]\nname = "ruff"\nversion = "0.9.1"\nsource = {}\n'
    )
    assert ruff_pins.locked(str(tmp_path)) == [("uv.lock", "0.9.1")]
    assert ruff_pins.compare("0.9.1", "0.16.10") == "behind"
    assert ruff_pins.compare("0.16.10", "0.9.1") == "ahead"


def test_non_numeric_version_exits_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-release spelling is refused rather than compared wrongly."""
    (tmp_path / "requirements.txt").write_text("ruff==0.9.1rc1\n")
    assert ruff_pins.main(["locked", str(tmp_path), "--target", "0.9.2"]) == 2
    assert "not a dotted numeric version" in capsys.readouterr().err


def test_lapse_uses_latest_matching_file(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The lapse is the latest upload among the platform's files plus the cooldown."""
    index = {
        "releases": {
            "1.0.0": [
                {
                    "filename": "r-1.0.0-linux.whl",
                    "upload_time_iso_8601": "2026-01-01T00:00:00.500000Z",
                },
                {"filename": "r-1.0.0-mac.whl", "upload_time_iso_8601": "2026-01-03T12:00:00Z"},
            ]
        }
    }
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index))
    assert (
        ruff_pins.main(["lapse", "--version", "1.0.0", "--cooldown", "7d", "--json", str(path)])
        == 0
    )
    assert "lapses\t2026-01-10T12:00:00+00:00" in capsys.readouterr().out
    args = ["lapse", "--version", "1.0.0", "--cooldown", "7d", "--json", str(path)]
    assert ruff_pins.main([*args, "--filename-contains", "linux"]) == 0
    assert "lapses\t2026-01-08T00:00:00.500000+00:00" in capsys.readouterr().out


def test_lapse_missing_release_exits_2(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown release gives no time, never a guess."""
    path = tmp_path / "index.json"
    path.write_text('{"releases": {}}')
    assert (
        ruff_pins.main(["lapse", "--version", "9.9.9", "--cooldown", "7d", "--json", str(path)])
        == 2
    )
    assert "no release 9.9.9" in capsys.readouterr().err
