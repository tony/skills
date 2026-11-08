"""Owned-repository tests for ``marketplace.py versions``."""

# ruff: noqa: S101, S603, S607, INP001
import json
import subprocess
import typing as t

import marketplace
import pytest

if t.TYPE_CHECKING:
    from pathlib import Path


def _git(repo: Path, *args: str) -> None:
    _ = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")


def _manifest(version: str) -> str:
    return json.dumps({"name": "p", "description": "d", "version": version})


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a repository with one plugin committed at 0.1.0."""
    _git(tmp_path, "init", "--quiet")
    _write(tmp_path, "plugins/p/.claude-plugin/plugin.json", _manifest("0.1.0"))
    _write(tmp_path, "plugins/p/skills/s/SKILL.md", "one\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "--quiet", "--message", "base")
    monkeypatch.setattr(marketplace, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(marketplace, "PLUGINS_DIR", tmp_path / "plugins")
    return tmp_path


def _commit(repo: Path) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "--message", "change")


def test_changed_plugin_without_bump_fails(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A file change under a plugin with the version untouched names the plugin."""
    _write(repo, "plugins/p/skills/s/SKILL.md", "two\n")
    _commit(repo)
    with pytest.raises(SystemExit) as exc:
        marketplace.versions(base="HEAD~1")
    assert exc.value.code == 1
    assert "p: files changed but version is still 0.1.0" in capsys.readouterr().out


def test_bump_passes(repo: Path) -> None:
    """Changing the version alongside the files passes."""
    _write(repo, "plugins/p/skills/s/SKILL.md", "two\n")
    _write(repo, "plugins/p/.claude-plugin/plugin.json", _manifest("0.1.1"))
    _commit(repo)
    marketplace.versions(base="HEAD~1")


def test_generated_codex_files_do_not_count(repo: Path) -> None:
    """A change confined to .codex-plugin/ needs no bump."""
    _write(repo, "plugins/p/.codex-plugin/plugin.json", "{}\n")
    _commit(repo)
    marketplace.versions(base="HEAD~1")


def test_new_plugin_needs_no_bump(repo: Path) -> None:
    """A plugin absent from the base is new, not changed."""
    _write(repo, "plugins/q/.claude-plugin/plugin.json", _manifest("0.1.0"))
    _commit(repo)
    marketplace.versions(base="HEAD~1")


def test_unknown_base_refuses(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An unresolvable base exits non-zero with one reason line."""
    _ = repo
    with pytest.raises(SystemExit) as exc:
        marketplace.versions(base="no-such-ref")
    assert exc.value.code == 1
    assert "cannot diff against 'no-such-ref'" in capsys.readouterr().out
