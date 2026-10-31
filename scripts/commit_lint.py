#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""Check commit messages against the AGENTS.md format.

Usage: commit_lint.py BASE [HEAD]

Checks every non-merge commit in BASE..HEAD (HEAD defaults to HEAD). Prints one
line per problem and exits 1 when there is any.
"""

import re
import subprocess
import sys

SUBJECT_MAX = 64
BODY_MAX = 72
_PR_REF_RE = re.compile(r"\s\(#\d+\)$")
_URL_RE = re.compile(r"https?://")
_SEPARATOR = "\x1e"


def check_message(label: str, message: str) -> list[str]:
    r"""Return one problem line per rule ``message`` breaks.

    Examples
    --------
    >>> check_message("abc", "scope(fix) Short\n\nwhy: A.\n\nwhat:\n- B\n")
    []
    >>> check_message("abc", "x" * 62 + " (#12)\n")
    []
    >>> check_message("abc", "x" * 65)
    ['abc: subject is 65 chars (max 64)']
    >>> check_message("abc", "s\n\n" + "y" * 73)
    ['abc: body line 3 is 73 chars (max 72)']
    >>> check_message("abc", "s\n\nsee https://example.test/" + "y" * 80)
    []
    >>> check_message("abc", "s\n\nwhy: A.\nwhat:\n- B")
    ['abc: why: and what: blocks need a blank line between them']
    """
    lines = message.rstrip("\n").split("\n")
    problems: list[str] = []
    subject = _PR_REF_RE.sub("", lines[0])
    if len(subject) > SUBJECT_MAX:
        problems.append(f"{label}: subject is {len(subject)} chars (max {SUBJECT_MAX})")
    problems.extend(
        f"{label}: body line {number} is {len(line)} chars (max {BODY_MAX})"
        for number, line in enumerate(lines[1:], start=2)
        if len(line) > BODY_MAX and not _URL_RE.search(line)
    )
    for number, line in enumerate(lines[1:], start=1):
        if line.startswith("what:") and lines[number - 1].strip():
            if any(earlier.startswith("why:") for earlier in lines[:number]):
                problems.append(f"{label}: why: and what: blocks need a blank line between them")
            break
    return problems


def commits(base: str, head: str) -> list[tuple[str, str]]:
    """Return ``(short sha, message)`` for each non-merge commit in ``base..head``."""
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "log",
            "--no-merges",
            f"--format=%h{_SEPARATOR}%B{_SEPARATOR}",
            f"{base}..{head}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"cannot list commits in {base}..{head}", file=sys.stderr)
        raise SystemExit(1)
    fields = result.stdout.split(_SEPARATOR)
    return [
        (fields[i].strip(), fields[i + 1])
        for i in range(0, len(fields) - 1, 2)
        if fields[i].strip()
    ]


def main(argv: list[str]) -> int:
    """Lint ``BASE..HEAD`` and return the exit status."""
    if not 1 <= len(argv) <= 2:  # noqa: PLR2004
        print("usage: commit_lint.py BASE [HEAD]", file=sys.stderr)
        return 2
    problems = [
        problem
        for sha, message in commits(argv[0], argv[1] if len(argv) == 2 else "HEAD")  # noqa: PLR2004
        for problem in check_message(sha, message)
    ]
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
