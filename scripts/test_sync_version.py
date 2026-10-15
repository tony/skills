"""Owned-fixture tests for ``sync`` keeping entry versions equal to plugin.json."""

# ruff: noqa: S101, INP001
# pyright: reportPrivateUsage=false, reportImplicitRelativeImport=false
from __future__ import annotations

import json
import typing as t

import marketplace
import pytest

if t.TYPE_CHECKING:
    from pathlib import Path


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, plugin_version: str) -> Path:
    plugin = tmp_path / "plugins" / "p" / ".claude-plugin"
    plugin.mkdir(parents=True)
    _ = (plugin / "plugin.json").write_text(
        json.dumps({"name": "p", "description": "d", "version": plugin_version}),
        encoding="utf-8",
    )
    path = tmp_path / "marketplace.json"
    _ = path.write_text(
        json.dumps(
            {
                "name": "m",
                "metadata": {"description": "d"},
                "owner": {"name": "o"},
                "plugins": [
                    {
                        "name": "p",
                        "description": "d",
                        "version": "0.1.0",
                        "author": {"name": "o"},
                        "source": "./plugins/p",
                        "category": "development",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    readme = tmp_path / "README.md"
    _ = readme.write_text("", encoding="utf-8")
    monkeypatch.setattr(marketplace, "MARKETPLACE_PATH", path)
    monkeypatch.setattr(marketplace, "PLUGINS_DIR", tmp_path / "plugins")
    monkeypatch.setattr(marketplace, "README_PATH", readme)
    return path


def test_check_fails_when_versions_differ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A plugin.json version the entry lacks is drift."""
    _ = _repo(tmp_path, monkeypatch, plugin_version="0.2.0")
    with pytest.raises(SystemExit) as exc:
        marketplace.sync(check=True)
    assert exc.value.code == 1


def test_write_copies_the_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``sync --write`` makes the entry carry the plugin.json version."""
    path = _repo(tmp_path, monkeypatch, plugin_version="0.2.0")
    marketplace.sync(write=True)
    assert json.loads(path.read_text(encoding="utf-8"))["plugins"][0]["version"] == "0.2.0"
    marketplace.sync(check=True)
