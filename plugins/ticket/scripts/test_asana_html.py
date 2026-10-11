"""Tests for asana_html.py."""

# ruff: noqa: S101, S603, S314, INP001, D103, PLR2004
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT = Path(__file__).with_name("asana_html.py")
TAGS = {
    "body",
    "strong",
    "em",
    "u",
    "s",
    "code",
    "ol",
    "ul",
    "li",
    "a",
    "blockquote",
    "pre",
    "h1",
    "h2",
    "hr",
    "p",
}


def run(tmp_path: Path, text: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "body.md").write_text(text)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "body.md")],
        capture_output=True,
        text=True,
        check=False,
    )


def test_output_is_xml_in_the_documented_tag_set(tmp_path: Path) -> None:
    text = (
        "# Title\n\n### Sub\n\nA **bold** and *it* and ~~old~~ with `a<b` & [l](https://x.io?a=1&b=2).\n\n"
        "- one\n- two\n\n1. first\n\n> quoted\n\n---\n\n```\nx < y && z\n```\n"
    )
    result = run(tmp_path, text)
    assert result.returncode == 0, result.stdout
    root = ET.fromstring(result.stdout)
    assert {el.tag for el in root.iter()} <= TAGS
    assert [a.attrib for a in root.iter() if a.attrib] == [{"href": "https://x.io?a=1&b=2"}]
    assert [el.tag for el in root.iter("h1")] == ["h1"]
    assert len(list(root.iter("h2"))) == 1
    assert next(root.iter("pre")).text == "x < y && z"


def test_unmappable_input_is_refused_with_no_html(tmp_path: Path) -> None:
    for text, word in (
        ("![a](u.png)", "image"),
        ("| a | b |\n|---|---|", "table"),
        ("- a\n  - b", "nested list"),
        ("<details>x</details>", "raw HTML"),
    ):
        result = run(tmp_path, text)
        assert result.returncode == 1
        assert word in result.stdout
        assert "<body>" not in result.stdout


def test_markup_inside_fence_is_kept(tmp_path: Path) -> None:
    result = run(tmp_path, "```\n<div> ![a](b) | x |\n```\n")
    assert result.returncode == 0
    assert "&lt;div&gt;" in result.stdout


def test_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2


def test_angle_brackets_in_code_spans_are_not_raw_html(tmp_path: Path) -> None:
    result = run(tmp_path, "The type `List<String>` fails.\n")
    assert result.returncode == 0
    assert "<code>List&lt;String&gt;</code>" in result.stdout
