#!/usr/bin/env python3
"""Run one model-CLI tier and print a JSON result with its failure class.

Usage: run_tier.py --prompt-file FILE [--timeout SECONDS|none]
       [--require-flag=FLAG ...] -- BINARY ARGS...

Each --require-flag=FLAG (the = is required) is checked against
`BINARY [SUBCOMMAND] --help` before the run; a missing flag prints class
"unsupported-flag" and skips the task.

The prompt file's text is appended to the command as its last argument; a
prompt over MAX_ARG_BYTES is replaced by an instruction to read the file.
Stdin is closed. Output keys: exit_code (null on timeout), class, elapsed, stdout,
stderr.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict, cast

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


class RepositoryState(TypedDict):
    """Repository identity and staged/working contents before a tier."""

    head: bytes
    branch: bytes
    paths: dict[str, str]


def repository_state() -> RepositoryState:
    """Read tracked and non-ignored files from the root without Git content filters."""
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
        capture_output=True,
        check=True,
    ).stdout.rstrip(b"\n")
    root = Path(os.fsdecode(top)).resolve()
    home = Path.home().resolve()
    if root == home or root in home.parents:
        msg = "repository contains the home directory"
        raise OSError(msg)

    def git(*args: str) -> bytes:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(root), *args],  # noqa: S607
            capture_output=True,
            check=True,
        ).stdout

    staged: dict[bytes, bytes] = {}
    for entry in git("ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            staged[name] = staged.get(name, b"") + metadata + b"\0"
    names = set(staged) | set(git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0"))
    paths: dict[str, str] = {}
    for raw in sorted(names - {b""}):
        name = os.fsdecode(raw)
        path = root / name
        for parent in path.parents:
            if parent == root:
                break
            if parent.is_symlink():
                msg = "a repository path has a symlinked parent"
                raise OSError(msg)
        digest = hashlib.sha256(staged.get(raw, b""))
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            digest.update(b"missing")
        else:
            digest.update(str(mode).encode())
            if stat.S_ISLNK(mode):
                digest.update(os.fsencode(path.readlink()))
            elif stat.S_ISREG(mode):
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(65536), b""):
                        digest.update(chunk)
            else:
                msg = f"repository state includes a submodule or special file: {name}"
                raise OSError(msg)
        paths[name] = digest.hexdigest()
    return {
        "head": git("rev-parse", "--verify", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "paths": paths,
    }


def check_state(before: RepositoryState | None, reason: str = "") -> dict[str, object]:
    """Compare the whole repository, including staged-only changes and symlinks."""
    if before is None:
        return {"status": "unavailable", "paths": [], "reason": reason}
    try:
        after = repository_state()
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"status": "unavailable", "paths": [], "reason": str(exc)}
    paths = sorted(
        name
        for name in before["paths"].keys() | after["paths"].keys()
        if before["paths"].get(name) != after["paths"].get(name)
    )
    history_changed = before["head"] != after["head"] or before["branch"] != after["branch"]
    return {
        "status": "changed" if paths or history_changed else "unchanged",
        "paths": paths,
        "history_changed": history_changed,
    }


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

    ``codex exec --sandbox read-only`` probes ``codex exec --help``. An unreadable help
    text reports every flag missing.
    """
    if not flags:
        return []
    probe: list[str] = []
    for word in command:
        if word.startswith("-"):
            break
        probe.append(word)
    done = _execute([*probe, "--help"], timeout=30)
    if done["exit_code"] != 0:
        return list(flags)
    text = str(done["stdout"]) + str(done["stderr"])
    return [f for f in flags if not re.search(rf"(?<![\w-]){re.escape(f)}(?![\w-])", text)]


def _stop_group(proc: subprocess.Popen[str]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def _execute(command: list[str], timeout: float | None) -> dict[str, object]:
    """Reap the command and terminate its group before checking repository state."""
    start = time.monotonic()
    try:
        proc = subprocess.Popen(  # noqa: S603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
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
        _stop_group(proc)
        stdout, stderr = proc.communicate()
    finally:
        _stop_group(proc)
    exit_code = None if timed_out else proc.returncode
    return {
        "exit_code": exit_code,
        "class": classify(exit_code=exit_code, timed_out=timed_out, stdout=stdout, stderr=stderr),
        "elapsed": round(time.monotonic() - start, 1),
        "stdout": stdout,
        "stderr": stderr,
    }


def run(
    command: list[str], prompt: str, timeout: float | None, prompt_file: Path | None = None
) -> dict[str, object]:
    """Run with the prompt as one argument, or a file reference above the OS limit."""
    if prompt_file is not None and len(prompt.encode()) > MAX_ARG_BYTES:
        prompt = f"Read the file {prompt_file.resolve()} and follow its instructions exactly."
    return _execute([*command, prompt], timeout)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the tier, and print the JSON result."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--prompt-file", required=True, type=Path)
    _ = parser.add_argument("--timeout", default="540")
    _ = parser.add_argument("--require-flag", action="append", default=[])
    _ = parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    prompt_file = cast("Path", args.prompt_file)
    raw = cast("list[str]", args.command)
    command = raw[1:] if raw[:1] == ["--"] else raw
    if not command:
        parser.error("missing command after --")
    raw_timeout = cast("str", args.timeout)
    timeout_error = f"invalid --timeout {raw_timeout!r}: use positive finite seconds or none"
    try:
        timeout = None if raw_timeout == "none" else float(raw_timeout)
    except ValueError:
        parser.error(timeout_error)
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        parser.error(timeout_error)
    try:
        prompt = prompt_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        parser.error(f"cannot read prompt file: {exc}")
    before_error = ""
    try:
        before = repository_state()
    except (OSError, subprocess.CalledProcessError) as exc:
        before = None
        before_error = str(exc)
    missing = missing_flags(command, cast("list[str]", args.require_flag))
    if missing:
        json.dump(
            {
                "exit_code": None,
                "class": "unsupported-flag",
                "elapsed": 0.0,
                "stdout": "",
                "stderr": f"{command[0]} --help does not list: {', '.join(missing)}",
                "state_check": check_state(before, before_error),
            },
            sys.stdout,
        )
        _ = sys.stdout.write("\n")
        return 0
    result = run(command, prompt, timeout, prompt_file)
    result["state_check"] = check_state(before, before_error)
    json.dump(result, sys.stdout)
    _ = sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
