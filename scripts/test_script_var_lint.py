"""Owned-fixture tests for the lint on graders that name bundled scripts."""

# ruff: noqa: S101, INP001, SLF001
# pyright: reportPrivateUsage=false, reportImplicitRelativeImport=false
from __future__ import annotations

import typing as t

import marketplace

if t.TYPE_CHECKING:
    from pathlib import Path

    import pytest

_LITERAL = """\
  - name: literal
    type: tool_used
    tool: Bash
    input_match: 'gate\\.py\\s+backup'
"""
_ORDER = """\
  - name: order
    type: tool_order
    before:
      tool: Bash
      input_match: 'git fetch'
    after:
      tool: Bash
      input_match: 'gate\\.py\\s+backup'
"""
_VARIABLE = """\
  - name: variable
    type: tool_used
    tool: Bash
    input_match: '(?:gate\\.py|python3?\\s+\\$\\{?[A-Za-z_]\\w*\\}?)\\s+backup'
"""


def test_offender_fails_and_variable_form_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Graders and order matchers missing the variable form fail; the form passes."""
    plugin = tmp_path / "plugins" / "p"
    (plugin / "scripts").mkdir(parents=True)
    _ = (plugin / "scripts" / "gate.py").write_text("", encoding="utf-8")
    (plugin / "evals" / "01-c").mkdir(parents=True)
    case = plugin / "evals" / "01-c" / "case.yaml"
    _ = case.write_text("graders:\n" + _LITERAL + _ORDER + _VARIABLE, encoding="utf-8")
    monkeypatch.setattr(marketplace, "PLUGINS_DIR", tmp_path / "plugins")

    errors = marketplace._check_script_var_graders()
    assert [e.split(": ")[0] for e in errors] == ["p/01-c:literal", "p/01-c:order"]

    _ = case.write_text("graders:\n" + _VARIABLE, encoding="utf-8")
    assert marketplace._check_script_var_graders() == []
