"""Tests for closest_model.py."""

# ruff: noqa: S101, S603, INP001, D103
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("closest_model.py")

AGENT = """Available models

auto - Auto (default)
gpt-5.3-codex-high - Codex 5.3 High
gpt-5.4-mini-medium - GPT-5.4 Mini
gpt-5.5-high - GPT-5.5 1M High
gpt-5.6-sol-high - GPT-5.6 Sol 1M High
gpt-5.7-high - GPT-5.7 1M High
gpt-5.2-high - GPT-5.2 High
"""

AGY = """Fetching available models...
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.2-pro-high\tGemini 3.2 Pro (High)
gemini-3.2-pro-low\tGemini 3.2 Pro (Low)
"""


def pick(want: str, listing: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), want],
        input=listing,
        capture_output=True,
        text=True,
        check=False,
    )


def test_nearest_newer_version_wins() -> None:
    result = pick("gpt-5.4-high", AGENT)
    assert (result.returncode, result.stdout) == (0, "gpt-5.5-high\n")


def test_nearest_older_version_when_no_newer() -> None:
    result = pick("gpt-5.9-high", AGENT)
    assert (result.returncode, result.stdout) == (0, "gpt-5.7-high\n")


def test_other_lines_and_levels_never_match() -> None:
    result = pick("gpt-5.4-xhigh", AGENT)
    assert (result.returncode, result.stdout) == (1, "")


def test_display_names_match_display_names() -> None:
    result = pick("Gemini 3.1 Pro (High)", AGY)
    assert (result.returncode, result.stdout) == (0, "Gemini 3.2 Pro (High)\n")


def test_listed_id_is_not_its_own_replacement() -> None:
    result = pick("gpt-5.4-mini-medium", AGENT)
    assert (result.returncode, result.stdout) == (1, "")


def test_id_without_version_has_no_family() -> None:
    result = pick("auto", AGENT)
    assert (result.returncode, result.stdout) == (1, "")
