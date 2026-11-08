"""Owned-fixture tests for how ``portable`` spells bundled paths."""

# ruff: noqa: S101, INP001, SLF001
import posixpath
import typing as t

import _portable_render as render
import marketplace

if t.TYPE_CHECKING:
    from pathlib import Path

    import pytest


_SKILL = (
    "---\nname: s\ndescription: d\n---\n../../references/a/shared.md ../../references/b/page.md\n"
)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")


def _build(root: Path, monkeypatch: pytest.MonkeyPatch) -> render.BuiltSkill:
    monkeypatch.setattr(render, "REPO_ROOT", root)
    monkeypatch.setattr(render, "PLUGINS_DIR", root / "plugins")
    plugin = root / "plugins" / "demo"
    skill_dir = plugin / "skills" / "s"
    skill = render.OutputSkill(
        "demo-s",
        render.SourceComponent(plugin, skill_dir / "SKILL.md", "s", skill_dir, {"name": "s"}),
    )
    return render.SkillBuilder(skill, render.PortableIndex({}, {})).build()


def _fixture(root: Path, *, collide: bool) -> None:
    sibling = "shared.md" if collide else "other.md"
    _write(
        root,
        "plugins/demo/skills/s/SKILL.md",
        _SKILL,
    )
    _write(root, "plugins/demo/references/a/shared.md", "A\n")
    _write(root, f"plugins/demo/references/b/{sibling}", "B\n")
    _write(
        root,
        "plugins/demo/references/b/page.md",
        f"Run `../../scripts/run.py` from this file's directory.\n[Details]({sibling})\n",
    )
    _write(root, "plugins/demo/scripts/run.py", "print()\n")


def _check(built: render.BuiltSkill) -> list[str]:
    return marketplace._check_paths(built)


def test_reference_links_resolve_from_own_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bundled reference spells scripts and siblings relative to itself."""
    _fixture(tmp_path, collide=False)
    built = _build(tmp_path, monkeypatch)
    page = built.files["references/page.md"][0].decode()
    assert "`./run.py`" in page
    assert "[Details](./other.md)" in page
    assert _check(built) == []


def test_basename_collision_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two sources sharing a basename fail the check instead of mislinking."""
    _fixture(tmp_path, collide=True)
    built = _build(tmp_path, monkeypatch)
    assert any("collides" in e for e in _check(built))


def test_validator_rejects_wrong_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A spelling that resolves to a different file than intended fails."""
    _fixture(tmp_path, collide=False)
    built = _build(tmp_path, monkeypatch)
    emitted, _spelled, intended = next(
        link for link in built.links if posixpath.basename(link[2]) == "run.py"
    )
    built.links.append((emitted, "./other.md", intended))
    assert any(", not " in e for e in _check(built))


def test_validator_rejects_missing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The old root-relative spelling inside a reference misses."""
    _fixture(tmp_path, collide=False)
    built = _build(tmp_path, monkeypatch)
    content, mode = built.files["references/page.md"]
    built.files["references/page.md"] = (content + b"see references/run.py\n", mode)
    assert any("does not resolve" in e for e in _check(built))


def _sibling_fixture(root: Path) -> None:
    _write(
        root,
        "plugins/demo/skills/s/SKILL.md",
        "---\nname: s\ndescription: d\n---\n../../scripts/a.py\n",
    )
    _write(root, "plugins/demo/scripts/a.py", "from b import f\n\n\ndef g():\n    import c\n")
    _write(root, "plugins/demo/scripts/b.py", "import d\n\nf = 1\n")
    _write(root, "plugins/demo/scripts/d.py", "")
    _write(root, "plugins/demo/scripts/c.py", "import json\n")
    _write(root, "plugins/demo/scripts/test_b.py", "import a\n")


def test_script_siblings_it_imports_are_bundled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linked script ships the modules it imports, transitively, never tests."""
    _sibling_fixture(tmp_path)
    built = _build(tmp_path, monkeypatch)
    emitted = {rel for rel in built.files if rel.endswith(".py")}
    assert emitted == {f"references/{m}.py" for m in "abcd"}


def test_missing_sibling_import_fails_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check names an emitted script whose sibling import was not emitted."""
    _sibling_fixture(tmp_path)
    monkeypatch.setattr(marketplace, "REPO_ROOT", tmp_path)
    built = _build(tmp_path, monkeypatch)
    assert marketplace._check_sibling_imports(built) == []
    del built.files["references/b.py"]
    del built.vendored["references/b.py"]
    errors = marketplace._check_sibling_imports(built)
    assert len(errors) == 1
    assert "imports 'b'" in errors[0]
