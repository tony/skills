"""Snapshot/diff isolates the skill's edits from earlier uncommitted ones."""

# ruff: noqa: S101, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest
import skill_diff  # pyright: ignore[reportImplicitRelativeImport]

EXIT_MISSING = 2


def test_report_graders_reject_malformed_replies() -> None:
    graders = Path(__file__).parents[1] / "evals/01-skill-style-bloated-helper/graders"
    patterns = [
        next(
            line.removeprefix("pattern: '").removesuffix("'")
            for line in (graders / name).read_text().splitlines()
            if line.startswith("pattern: '")
        )
        for name in ("output-shape.md", "short-target-first-hero.md")
    ]
    valid = """The draft loses its intro.

## Ledger

- Intro: repeats the task.

## Behavior changes

- Description names the trigger.

## Diff

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ -1 +0,0 @@
-Intro
```
"""
    assert all(re.search(pattern, valid) for pattern in patterns)
    fenced_diff = valid.replace("-Intro", "-```bash\n-echo example\n-```")
    assert all(re.search(pattern, fenced_diff) for pattern in patterns)
    for malformed in (
        valid.replace("- Intro:", "- **Intro:**", 1),
        valid.replace("The draft loses its intro.", "We trimmed the draft."),
        valid.replace("The draft loses its intro.", "The draft loses filler. We edited it."),
        valid + "\n## Summary\n\nDone.\n```",
    ):
        assert not all(re.search(pattern, malformed) for pattern in patterns), malformed


def test_examples_preserve_protected_command_fences() -> None:
    references = Path(__file__).parents[1] / "references"
    fences: list[list[str]] = []
    for name in ("example-bloated.md", "example-ideal.md"):
        text = (references / name).read_text().split("````markdown\n", 1)[1]
        sample = text.split("\n````", 1)[0]
        fences.append(re.findall(r"^```[^\n]*\n(.*?)^```", sample, re.MULTILINE | re.DOTALL))
    assert fences[0]
    assert fences[0] == fences[1]


def test_diff_excludes_earlier_edits_and_temp_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_text("one\nfiller\nthree\n")
    root, out = skill_diff.snapshot([target], tmp_path)
    target.write_text("one\nthree\n")
    text = skill_diff.diff(root, work=False)
    assert "--- a/SKILL.md" in text
    assert "-filler" in text
    assert str(root) not in text
    skill_diff.clean(root)
    assert not root.exists()
    assert out[0][1] == "SKILL.md"


def test_work_diff_leaves_target_untouched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_text("a\nb\n")
    root, out = skill_diff.snapshot([target], tmp_path)
    out[0][0].write_text("a\n")
    assert "-b" in skill_diff.diff(root, work=True)
    assert target.read_text() == "a\nb\n"
    skill_diff.clean(root)


def test_clean_refuses_foreign_dir(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        skill_diff.clean(tmp_path)


def test_missing_target_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_text("a\n")
    root, _ = skill_diff.snapshot([target], tmp_path)
    target.unlink()
    assert skill_diff.main(["diff", str(root)]) == EXIT_MISSING
    skill_diff.clean(root)


def test_stdin_snapshot_cleans_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root, out = skill_diff.snapshot([], tmp_path, "a\nb\n")
    out[0][0].write_text("a\n")
    assert out[0][1] == "SKILL.md"
    assert "-b" in skill_diff.diff(root, work=True)
    skill_diff.clean(root)
    assert not root.exists()


def test_missing_final_newline_gets_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root, out = skill_diff.snapshot([], tmp_path, "a\nb")
    out[0][0].write_text("a\nc")
    assert skill_diff.diff(root, work=True).splitlines()[2:] == [
        "@@ -1,2 +1,2 @@",
        " a",
        "-b",
        "\\ No newline at end of file",
        "+c",
        "\\ No newline at end of file",
    ]
    skill_diff.clean(root)


def test_non_utf8_target_exits_2_and_leaves_no_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "SKILL.md"
    target.write_bytes(b"caf\xe9\n")
    before = set(Path(tempfile.gettempdir()).glob(f"{skill_diff.PREFIX}*"))
    assert skill_diff.main(["snapshot", str(target)]) == EXIT_MISSING
    assert "not UTF-8" in capsys.readouterr().err
    assert set(Path(tempfile.gettempdir()).glob(f"{skill_diff.PREFIX}*")) == before


def test_outside_cwd_labels_are_unique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    targets: list[Path] = []
    for name in ("a", "b"):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text("x\n")
        targets.append(d / "SKILL.md")
    root, out = skill_diff.snapshot(targets, cwd)
    assert [label for _, label in out] == ["a/SKILL.md", "b/SKILL.md"]
    skill_diff.clean(root)
