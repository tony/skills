"""Positive and negative fixtures for each detect pattern."""

# ruff: noqa: S101, S603, INP001, D103, PLR2004
# pyright: reportUnusedCallResult=false

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from detect import PATTERNS, find  # pyright: ignore[reportImplicitRelativeImport]

CASES: list[tuple[str, str, bool]] = [
    ("margin", '<a className="px-2 me-4">', True),
    ("margin", '<a className="-ml-2 px-2">', True),
    ("margin", '<a class="ms-[3px]">', True),
    ("margin", '<a className="ml-px">', True),
    ("margin", '<a className="!me-4">', True),
    ("margin", '<a className="mx-auto px-2">', False),
    ("margin", '<a className="mt-4 my-2 m-4">', False),
    ("vmargin", '<div className="flex flex-col gap-3"><p className="mt-4">', True),
    ("vmargin", '<ul className="md:grid grid-cols-2"><li className="-mb-2">', True),
    ("vmargin", '<div className="flex gap-3"><p className="mt-4">', False),
    ("vmargin", '<div className="flex-col"><p className="mt-auto my-auto">', False),
    ("vmargin", '<div className="grid-cols-2"><p className="mt-4">', False),
    ("margin-in-gap", '<div className="flex gap-3"><a className="me-4">', True),
    ("margin-in-gap", '<div className="flex-col gap-3"><a className="my-2">', True),
    ("margin-in-gap", '<div className="flex gap-3"><a className="my-2">', False),
    ("margin-in-gap", '<div className="flex"><a className="me-4">', False),
    ("margin", '<a className="some-ml-2">', False),
    ("gap", '<div className="flex gap-3">', True),
    ("gap", '<div className="flex gap-x-[3px]">', True),
    ("gap", '<div className="flex gap-px">', True),
    ("gap", '<div className="flex">', False),
    ("gap", '<div className="biggap-3">', False),
    ("width", '<button className="h-8 w-24">', True),
    ("width", '<button className="w-[10rem]">', True),
    ("width", '<button className="min-w-24 max-w-24">', False),
    ("width", '<button className="w-full w-auto">', False),
    ("interactive", '<button className="px-2">', True),
    ("interactive", '<button\n  onClick={() => x()}\n  className="px-4"\n>', True),
    ("interactive", '<IconButton className="px-2">', True),
    ("interactive", '<article className="px-2">', False),
    ("interactive", '<Action className="px-2">', False),
    ("wrapper", '<div className="flex h-full items-center">', True),
    ("wrapper", '<div className="items-center flex">', True),
    ("wrapper", '<div className={cn("flex items-center", x)}>', True),
    ("wrapper", '<div className="inline-flex items-center">', False),
    ("wrapper", '<div className="flex flex-col place-items-center">', False),
    ("space-gap", '<div className="flex gap-2 space-x-3">', True),
    ("space-gap", '<div className="space-y-2 flex gap-y-1">', True),
    ("space-gap", "<div className={`flex gap-2 ${a} space-x-3`}>", True),
    ("space-gap", '<div className="flex gap-2">', False),
    ("space-gap", '<div className="space-x-3">', False),
    ("space-gap", 'cn("flex gap-2", "space-x-3")', False),
    ("space", '<div className="space-x-3">', True),
    ("space", 'cn("flex gap-2", "space-y-[3px]")', True),
    ("space", '<div className="flex gap-2">', False),
    ("space", '<div className="space-x-reverse">', False),
]


@pytest.mark.parametrize(("pattern", "text", "hit"), CASES)
def test_fixture(pattern: str, text: str, hit: bool) -> None:
    assert bool(find(pattern, text)) is hit


def test_line_number_counts_multiline_tag() -> None:
    text = 'x\n<button\n  onClick={() => y()}\n  className="px-2"\n>'
    assert find("interactive", text)[0][0] == 2


@pytest.mark.parametrize(
    "text",
    [
        '<div className="' + "flex gap-2 space-x-2 " * 5000,
        "<div " * 20000,
        "<a " * 33000,
    ],
)
def test_long_input_scans_fast(text: str) -> None:
    start = time.perf_counter()
    for pattern in PATTERNS:
        find(pattern, text)
    assert time.perf_counter() - start < 1.0


def test_missing_path_exits_two(tmp_path: Path) -> None:
    script = Path(__file__).with_name("detect.py")
    run = subprocess.run(
        [sys.executable, str(script), "margin", str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 2
    assert "no such path" in run.stderr


def test_cli_exit_codes(tmp_path: Path) -> None:
    (tmp_path / "a.tsx").write_text('<a className="me-4">')
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "b.tsx").write_text('<a className="me-4">')
    script = Path(__file__).with_name("detect.py")
    hit = subprocess.run(
        [sys.executable, str(script), "margin", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert hit.returncode == 0
    assert hit.stdout.count("\n") == 1
    miss = subprocess.run(
        [sys.executable, str(script), "gap", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert miss.returncode == 1


def test_margin_in_gap_caps_hits(tmp_path: Path) -> None:
    (tmp_path / "a.tsx").write_text('<div className="flex gap-2">' + '<a className="me-4"/>\n' * 80)
    script = Path(__file__).with_name("detect.py")
    run = subprocess.run(
        [sys.executable, str(script), "margin-in-gap", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0
    assert run.stdout.count("\n") == 50
    assert "stopped at 50 hits" in run.stderr
