#!/usr/bin/env python3
"""Run one model-CLI tier and print a JSON result with its failure class.

Usage: run_tier.py --prompt-file FILE [--timeout SECONDS|none]
       [--require-flag=FLAG ...] -- BINARY ARGS...

Each --require-flag=FLAG (the = is required) is checked against
`BINARY [SUBCOMMAND] --help` before the run; a missing flag prints class
"unsupported-flag" and runs nothing.

The prompt file's text is appended to the command as its last argument; a
prompt over MAX_ARG_BYTES is replaced by an instruction to read the file.
Stdin is closed. Output keys: exit_code (null on timeout), class, elapsed, stdout,
stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import cast

MAX_ARG_BYTES = 100_000

CREDIT_PATTERNS = (
    "RESOURCE_EXHAUSTED",
    "quota exceeded",
    "quota_exceeded",
    "insufficient_quota",
    "exceeded your current quota",
    r"billing (?:limit|error|issue)",
    "capacity exhausted",
    "usage limit",
)
CREDIT_RE = re.compile("|".join(CREDIT_PATTERNS), re.IGNORECASE)
RATE_RE = re.compile(r"rate.?limit|too many requests|\b429\b", re.IGNORECASE)
AUTH_RE = re.compile(
    r"not logged in|log in|login required|authentication|unauthori[sz]ed|\b401\b|api key",
    re.IGNORECASE,
)
MODEL_RE = re.compile(
    r"unknown model|invalid model|model not found|cannot use this model", re.IGNORECASE
)
FAILURES = (("rate-limit", RATE_RE), ("unknown-model", MODEL_RE), ("auth", AUTH_RE))


def classify(*, exit_code: int | None, timed_out: bool, stdout: str, stderr: str) -> str:
    """Classify one attempt; stderr only, since stdout can quote code that says "billing".

    >>> classify(exit_code=0, timed_out=False, stdout="hi", stderr="")
    'ok'
    >>> classify(exit_code=None, timed_out=True, stdout="", stderr="")
    'timeout'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="RESOURCE_EXHAUSTED")
    'credit'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="429 daily limit")
    'credit'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="429 Too Many Requests")
    'rate-limit'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="Not logged in")
    'auth'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="Unknown model x")
    'unknown-model'
    >>> classify(exit_code=2, timed_out=False, stdout="", stderr="boom")
    'crash'
    >>> classify(exit_code=0, timed_out=False, stdout="", stderr="")
    'empty'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="billing limit reached")
    'credit'
    >>> classify(exit_code=1, timed_out=False, stdout="", stderr="billing")
    'crash'
    >>> classify(exit_code=0, timed_out=False, stdout="billing", stderr="billing")
    'ok'
    """
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "ok" if stdout.strip() else "empty"
    if CREDIT_RE.search(stderr) or ("429" in stderr and "daily limit" in stderr.lower()):
        return "credit"
    for name, pattern in FAILURES:
        if pattern.search(stderr):
            return name
    return "crash"


def missing_flags(command: list[str], flags: list[str]) -> list[str]:
    """Return the flags absent from the help text of the command's leading words.

    ``codex exec --yolo`` probes ``codex exec --help``. An unreadable help
    text reports every flag missing.
    """
    if not flags:
        return []
    probe: list[str] = []
    for word in command:
        if word.startswith("-"):
            break
        probe.append(word)
    try:
        done = subprocess.run(  # noqa: S603
            [*probe, "--help"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return list(flags)
    text = done.stdout + done.stderr
    return [f for f in flags if not re.search(rf"(?<![\w-]){re.escape(f)}(?![\w-])", text)]


def run(
    command: list[str], prompt: str, timeout: float | None, prompt_file: Path | None = None
) -> dict[str, object]:
    """Run command with prompt appended; kill the whole process group on timeout.

    A prompt over MAX_ARG_BYTES cannot be one argument (Linux caps it near
    128 KiB), so the CLI is told to read ``prompt_file`` instead.
    """
    start = time.monotonic()
    if prompt_file is not None and len(prompt.encode()) > MAX_ARG_BYTES:
        prompt = f"Read the file {prompt_file.resolve()} and follow its instructions exactly."
    try:
        proc = subprocess.Popen(  # noqa: S603
            [*command, prompt],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        return {
            "exit_code": 127,
            "class": "crash",
            "elapsed": 0.0,
            "stdout": "",
            "stderr": str(exc),
        }
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    exit_code = None if timed_out else proc.returncode
    return {
        "exit_code": exit_code,
        "class": classify(exit_code=exit_code, timed_out=timed_out, stdout=stdout, stderr=stderr),
        "elapsed": round(time.monotonic() - start, 1),
        "stdout": stdout,
        "stderr": stderr,
    }


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the tier, and print the JSON result."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--prompt-file", required=True, type=Path)
    _ = parser.add_argument("--timeout", default="600")
    _ = parser.add_argument("--require-flag", action="append", default=[])
    _ = parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    prompt_file = cast("Path", args.prompt_file)
    raw = cast("list[str]", args.command)
    command = raw[1:] if raw[:1] == ["--"] else raw
    if not command:
        parser.error("missing command after --")
    missing = missing_flags(command, cast("list[str]", args.require_flag))
    if missing:
        json.dump(
            {
                "exit_code": None,
                "class": "unsupported-flag",
                "elapsed": 0.0,
                "stdout": "",
                "stderr": f"{command[0]} --help does not list: {', '.join(missing)}",
            },
            sys.stdout,
        )
        _ = sys.stdout.write("\n")
        return 0
    raw_timeout = cast("str", args.timeout)
    try:
        timeout = None if raw_timeout == "none" else float(raw_timeout)
    except ValueError:
        parser.error(f"invalid --timeout {raw_timeout!r}: use seconds or none")
    result = run(command, prompt_file.read_text(encoding="utf-8"), timeout, prompt_file)
    json.dump(result, sys.stdout)
    _ = sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
