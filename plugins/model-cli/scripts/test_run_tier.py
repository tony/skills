"""Tests for run_tier.py using stub binaries."""

# ruff: noqa: S101, S603, INP001, PLR2004, D103
# pyright: reportUnusedCallResult=false, reportAny=false
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("run_tier.py")


def stub(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "stub"
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(0o755)
    return path


def tier(
    tmp_path: Path,
    binary: Path,
    prompt: str = "hello",
    timeout: str = "5",
    require: tuple[str, ...] = (),
) -> dict[str, object]:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(prompt)
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prompt-file",
            str(prompt_file),
            "--timeout",
            timeout,
            *[f"--require-flag={flag}" for flag in require],
            "--",
            str(binary),
            "-p",
            "--",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def test_ok_passes_prompt_as_one_last_argument(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, 'echo "$#:${@: -1}"'), prompt="two words\nline2")
    assert result["class"] == "ok"
    assert result["exit_code"] == 0
    assert result["stdout"] == "3:two words\nline2\n"


def test_credit_from_stderr_only(tmp_path: Path) -> None:
    failing = tier(tmp_path, stub(tmp_path, "echo RESOURCE_EXHAUSTED >&2; exit 1"))
    assert failing["class"] == "credit"
    quoted = tier(tmp_path, stub(tmp_path, "echo billing; exit 1"))
    assert quoted["class"] == "crash"
    bare = tier(tmp_path, stub(tmp_path, "echo billing >&2; exit 1"))
    assert bare["class"] == "crash"


def test_auth_and_unknown_model(tmp_path: Path) -> None:
    assert tier(tmp_path, stub(tmp_path, "echo 'Not logged in' >&2; exit 1"))["class"] == "auth"
    assert (
        tier(tmp_path, stub(tmp_path, "echo 'unknown model x' >&2; exit 1"))["class"]
        == "unknown-model"
    )


def test_empty_and_rate_limit(tmp_path: Path) -> None:
    assert tier(tmp_path, stub(tmp_path, "exit 0"))["class"] == "empty"
    assert tier(tmp_path, stub(tmp_path, "echo 'rate limit' >&2; exit 1"))["class"] == "rate-limit"


def test_timeout_kills_the_process_group(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, "sleep 30 & sleep 30"), timeout="0.5")
    assert result["class"] == "timeout"
    assert result["exit_code"] is None
    assert float(str(result["elapsed"])) < 5


def test_missing_binary_is_crash(tmp_path: Path) -> None:
    result = tier(tmp_path, tmp_path / "absent")
    assert result["class"] == "crash"
    assert result["exit_code"] == 127


def test_oversized_prompt_is_passed_as_a_file_reference(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, 'echo "${@: -1}"'), prompt="x" * 200_000)
    assert result["class"] == "ok"
    assert str(tmp_path / "prompt.txt") in str(result["stdout"])


HELP_STUB = 'if [ "$1" = --help ]; then echo "  --sandbox <MODE>"; exit 0; fi; echo ran'


def test_required_flag_present_runs_the_tier(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, HELP_STUB), require=("--sandbox",))
    assert result["class"] == "ok"


def test_required_flag_missing_runs_nothing(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    body = f'if [ "$1" = --help ]; then echo "  --other"; exit 0; fi; touch {marker}; echo ran'
    result = tier(tmp_path, stub(tmp_path, body), require=("--sandbox",))
    assert result["class"] == "unsupported-flag"
    assert "--sandbox" in str(result["stderr"])
    assert not marker.exists()


def test_flag_must_match_whole_word(tmp_path: Path) -> None:
    body = 'if [ "$1" = --help ]; then echo "--sandbox-mode"; exit 0; fi; echo ran'
    result = tier(tmp_path, stub(tmp_path, body), require=("--sandbox",))
    assert result["class"] == "unsupported-flag"


def test_malformed_timeout_is_a_usage_error(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hi")
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prompt-file",
            str(prompt_file),
            "--timeout",
            "5m",
            "--",
            "true",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 2
    assert "invalid --timeout" in out.stderr
    assert "Traceback" not in out.stderr
