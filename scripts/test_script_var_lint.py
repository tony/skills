"""Owned-fixture tests for the lint on graders that name bundled scripts."""

# ruff: noqa: S101, INP001, SLF001
# pyright: reportPrivateUsage=false, reportImplicitRelativeImport=false
from __future__ import annotations

import typing as t

import marketplace

if t.TYPE_CHECKING:
    from pathlib import Path

    import pytest

_CASE = """\
graders:
  - name: literal
    type: tool_used
    tool: Bash
    input_match: 'gate\\.py\\s+backup'
  - name: variable
    type: tool_used
    tool: Bash
    input_match: '(?:gate\\.py|python3?\\s+\\$\\{?[A-Za-z_]\\w*\\}?)\\s+backup'
"""


def test_new_offender_and_stale_baseline_line_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A grader missing the variable form and a stale baseline line each fail."""
    plugin = tmp_path / "plugins" / "p"
    (plugin / "scripts").mkdir(parents=True)
    _ = (plugin / "scripts" / "gate.py").write_text("", encoding="utf-8")
    (plugin / "evals" / "01-c").mkdir(parents=True)
    _ = (plugin / "evals" / "01-c" / "case.yaml").write_text(_CASE, encoding="utf-8")
    baseline = tmp_path / "scripts" / "script-var-baseline.txt"
    baseline.parent.mkdir()
    monkeypatch.setattr(marketplace, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(marketplace, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(marketplace, "SCRIPT_VAR_BASELINE", baseline)

    _ = baseline.write_text("# header\np/01-c:gone\n", encoding="utf-8")
    new, stale = marketplace._check_script_var_graders()
    assert new.startswith("p/01-c:literal: names a bundled script")
    assert "'p/01-c:gone' no longer offends" in stale

    _ = baseline.write_text("p/01-c:literal\n", encoding="utf-8")
    assert marketplace._check_script_var_graders() == []
