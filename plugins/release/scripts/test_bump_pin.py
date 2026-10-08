"""Tests for bump_pin.py."""

# ruff: noqa: S101, INP001, D103
# pyright: reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

import bump_pin  # pyright: ignore[reportImplicitRelativeImport]

if TYPE_CHECKING:
    import pathlib

    import pytest


def test_inline_array_and_name_casing(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "pyproject.toml"
    f.write_text('dependencies = ["Foo_Bar[x]==0.1.1", "other==0.1.1", "foo-bar==0.1.10"]\n')
    assert bump_pin.bump(f, "foo-bar", "0.1.1", "0.2.0") == 1
    assert f.read_text() == (
        'dependencies = ["Foo_Bar[x]==0.2.0", "other==0.1.1", "foo-bar==0.1.10"]\n'
    )


def test_requirements_file_and_prerelease_boundary(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "requirements.txt"
    f.write_text("foo==0.1.1a1\nfoo==0.1.1\n")
    assert bump_pin.bump(f, "foo", "0.1.1", "0.1.2") == 1
    assert f.read_text() == "foo==0.1.1a1\nfoo==0.1.2\n"


def test_package_json_scoped_name(tmp_path: pathlib.Path) -> None:
    f = tmp_path / "package.json"
    f.write_text('{"dependencies": {"@s/pkg": "~1.0.0"}}\n')
    assert bump_pin.bump(f, "@s/pkg", "1.0.0", "1.1.0") == 1
    assert '"~1.1.0"' in f.read_text()


def test_no_match_leaves_file_and_exits_1(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "pyproject.toml"
    f.write_text('dependencies = ["foo>=0.1.1"]\n')
    assert bump_pin.main([str(f), "foo", "0.1.1", "0.2.0"]) == 1
    assert f.read_text() == 'dependencies = ["foo>=0.1.1"]\n'
    assert "edit it by hand" in capsys.readouterr().err
