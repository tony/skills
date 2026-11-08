"""Tests for closest_model.py."""

# ruff: noqa: S101, S603, INP001, PLR2004, D103
import doctest
import importlib.machinery
import importlib.util
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


def newest(listing: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--newest", *args],
        input=listing,
        capture_output=True,
        text=True,
        check=False,
    )


def test_newest_takes_highest_version_and_skips_variants() -> None:
    result = newest(AGENT, "gpt-{v}-*high", "--exclude", "mini")
    assert (result.returncode, result.stdout) == (0, "gpt-5.7-high\n")


def test_newest_tie_goes_to_first_listed() -> None:
    result = newest("gpt-5.6-sol-high - A\ngpt-5.6-luna-high - B\n", "gpt-{v}-*high")
    assert result.stdout == "gpt-5.6-sol-high\n"


def test_newest_exclude_drops_a_word_part() -> None:
    listing = "gpt-5.9-mini-high - M\ngpt-5.4-high - G\n"
    assert newest(listing, "gpt-{v}-*high", "--exclude", "mini").stdout == "gpt-5.4-high\n"


def test_newest_emits_label_for_agy() -> None:
    result = newest(AGY, "gemini-{v}-pro-high", "--emit", "label")
    assert result.stdout == "Gemini 3.2 Pro (High)\n"


def test_newest_reports_not_live_listed_when_nothing_matches() -> None:
    result = newest(AGY, "gemini-{v}-ultra")
    assert (result.returncode, result.stdout) == (3, "")
    assert "not live-listed" in result.stderr
    assert newest("", "gemini-{v}-pro-high").returncode == 3


def match(listing: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--match", *args],
        input=listing,
        capture_output=True,
        text=True,
        check=False,
    )


def test_match_requires_every_word_case_insensitively() -> None:
    assert match(AGENT, "GPT 5.5").stdout == "gpt-5.5-high\n"
    assert match(AGENT, "gpt-5.4 mini").stdout == "gpt-5.4-mini-medium\n"


def test_match_lists_all_candidates_and_can_emit_labels() -> None:
    assert match(AGY, "3.2 pro").stdout == "gemini-3.2-pro-high\ngemini-3.2-pro-low\n"
    assert match(AGY, "3.2 pro low", "--emit", "label").stdout == "Gemini 3.2 Pro (Low)\n"


def test_match_without_a_hit_or_header_line_exits_1() -> None:
    assert match(AGENT, "gemini").returncode == 1
    assert match(AGENT, "available models").returncode == 1


def test_newest_rejects_a_template_without_version() -> None:
    assert newest(AGY, "gemini-pro").returncode == 2


def test_doctests() -> None:
    # Copies of this vendored module share a basename, so pytest collects none.
    spec = importlib.util.spec_from_file_location("closest_model_doctests", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = doctest.testmod(module)
    assert result.attempted > 0
    assert result.failed == 0
