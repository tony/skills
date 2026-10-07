"""Tests for default_delta.py against a fake ruff executable."""

# ruff: noqa: S101, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

from typing import TYPE_CHECKING

import default_delta  # pyright: ignore[reportImplicitRelativeImport]
import pytest

if TYPE_CHECKING:
    import pathlib

FAKE = """#!/bin/sh
case "$*" in
  *--show-settings*) printf 'linter.rules.enabled = [\\n\\ta (E401),\\n\\tb (F401),\\n]\\n' ;;
  *--extend-select*) echo '[{"code":"F401","count":4},{"code":"E401","count":1}]' ;;
  *) echo '[{"code":"F401","count":1}]' ;;
esac
"""


def _fake(tmp_path: pathlib.Path, body: str = FAKE) -> str:
    exe = tmp_path / "ruff"
    exe.write_text(body)
    exe.chmod(0o755)
    return str(exe)


def test_delta_per_rule_and_total(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each rule reports configured, widened and delta counts."""
    exe = _fake(tmp_path)
    assert default_delta.main(["--cwd", str(tmp_path), "--", exe]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "E401\t0\t1\t1",
        "F401\t1\t4\t3",
        "total\t1\t5\t4",
    ]


def test_unparseable_settings_exit_2(tmp_path: pathlib.Path) -> None:
    """Unrecognized --show-settings output is an error, not an empty set."""
    exe = _fake(tmp_path, "#!/bin/sh\necho 'format changed'\n")
    with pytest.raises(SystemExit) as stop:
        default_delta.main(["--cwd", str(tmp_path), "--", exe])
    assert stop.value.code == 2
