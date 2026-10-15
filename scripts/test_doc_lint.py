"""Owned-fixture tests for the doc rules ``marketplace.py lint`` can enforce."""

# ruff: noqa: S101, INP001, SLF001
# pyright: reportPrivateUsage=false, reportImplicitRelativeImport=false
from __future__ import annotations

import typing as t

import marketplace
import pytest

if t.TYPE_CHECKING:
    from pathlib import Path

_SKILL = """\
---
name: s
description: d
user-invocable: true
---

See ../../references/prose-rules.md.

```console
# list files
ls
```

```bash
git status
```

```console
$ uv run pytest -q
$ mapfile -t a < f
```

```console
$ sed -i 's/a/b/' f
```
"""


def _plugin(root: Path, name: str, text: str) -> None:
    skill = root / "plugins" / name / "skills" / "s"
    skill.mkdir(parents=True)
    _ = (skill / "SKILL.md").write_text(text, encoding="utf-8")
    manifest = root / "plugins" / name / ".claude-plugin"
    manifest.mkdir()
    _ = (manifest / "plugin.json").write_text('{"name": "x", "description": "d"}', encoding="utf-8")


@pytest.fixture
def enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Enforce every doc rule over a throwaway plugins directory."""
    monkeypatch.setattr(marketplace, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(marketplace, "PLUGINS_DIR", tmp_path / "plugins")
    rules: frozenset[str] = frozenset(marketplace.DOC_RULES)
    monkeypatch.setattr(marketplace, "ENFORCED_DOC_RULES", rules)
    return tmp_path


def test_each_rule_refuses_with_one_line(enforced: Path) -> None:
    """Every enforced rule yields one error line naming plugin, file, line, and reason."""
    _plugin(enforced, "p", _SKILL.replace("../../references/prose-rules.md", "x"))
    errors = marketplace._check_doc_rules()
    head = "[p] skills/s/SKILL.md"
    assert sorted(errors) == sorted(
        [
            f"{head}:4: `user-invocable: true` is the default; delete it",
            f"{head}:1: no link to ../../references/prose-rules.md",
            f"{head}:11: console fence must open with a `$ ` command",
            f"{head}:10: comments belong in prose above the fence",
            f"{head}:15: use a `console` fence with `$ ` unless the block is a script",
            f"{head}:19: hardcoded `uv run pytest`; point to the project gates in AGENTS.md",
            f"{head}:20: `mapfile` is GNU-only",
            f"{head}:20: one command per console block; split the block",
            f"{head}:24: `sed -i` without the BSD `sed -i ''` form beside it",
        ]
    )


def test_tool_plugin_may_name_its_tool(enforced: Path) -> None:
    """A plugin named for a tool keeps its tool's commands."""
    _plugin(enforced, "ruff", _SKILL)
    assert not [e for e in marketplace._check_doc_rules() if "hardcoded" in e]


def test_exempt_skill_needs_no_prose_link(enforced: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A listed skill passes without the prose-rules link."""
    _plugin(enforced, "p", "---\nname: s\ndescription: d\n---\nbody\n")
    assert any("prose-rules" in e for e in marketplace._check_doc_rules())
    monkeypatch.setattr(marketplace, "PROSE_RULES_EXEMPT", {"p/s": "test"})
    assert marketplace._check_doc_rules() == []


def test_unenforced_rules_stay_quiet(enforced: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rules outside the enforced set produce no lint error."""
    _plugin(enforced, "p", _SKILL)
    monkeypatch.setattr(marketplace, "ENFORCED_DOC_RULES", frozenset[str]())
    assert marketplace._check_doc_rules() == []


def test_file_exemptions_name_real_files() -> None:
    """Every fence exemption points at a file that exists."""
    missing = [
        key
        for key in marketplace.DOC_FILE_EXEMPT
        if not (marketplace.REPO_ROOT / "plugins" / key).is_file()
    ]
    assert missing == []


def test_one_command_sed_bre_and_comment_run(enforced: Path) -> None:
    """Two commands in a block, a GNU sed escape, and a long comment each refuse."""
    text = "---\nname: s\ndescription: d\n---\n[p](../../references/prose-rules.md)\n\n"
    text += "```console\n$ git status\n$ git log\n```\n\n"
    text += "```console\n$ sed 's/a\\+/b/' f\n```\n"
    _plugin(enforced, "p", text)
    scripts = enforced / "plugins" / "p" / "scripts"
    scripts.mkdir()
    _ = (scripts / "x.py").write_text("# a\n# b\n# c\n# d\nx = 1\n", encoding="utf-8")
    head = "[p] skills/s/SKILL.md"
    run = "[p] plugins/p/scripts/x.py:1: comment run of 4 lines; keep the constraint, cut the rest"
    assert sorted(marketplace._check_doc_rules()) == sorted(
        [
            f"{head}:9: one command per console block; split the block",
            f"{head}:13: GNU-only `\\+` in a sed expression; use `sed -E` with a bare `+`",
            f"{run}",
        ]
    )
