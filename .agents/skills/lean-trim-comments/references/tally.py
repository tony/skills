#!/usr/bin/env python3
"""Print the hero line for a list of comment verdict bullets read from stdin.

Each bullet starts ``- Kept``, ``- Rewrote``, or ``- Deleted``. Prints
``N comments: K kept, R rewritten, D deleted``. Exits 2 with a message on
stderr when a bullet starts with another word or no bullet is present.
"""

# pyright: reportAny=false
import sys

_VERDICTS = {"kept": 0, "rewrote": 1, "deleted": 2}


def tally(text: str) -> str:
    r"""Return the hero line for the verdict bullets in ``text``.

    >>> tally("- Kept a\n- Deleted b\n- Rewrote c\n- Deleted d\n")
    '4 comments: 1 kept, 1 rewritten, 2 deleted'
    >>> tally("- Kept a")
    '1 comment: 1 kept, 0 rewritten, 0 deleted'
    """
    counts = [0, 0, 0]
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        word = line[2:].split(None, 1)[0].lower() if line[2:].strip() else ""
        if word not in _VERDICTS:
            msg = f"unknown verdict: {line!r}"
            raise ValueError(msg)
        counts[_VERDICTS[word]] += 1
    if not sum(counts):
        msg = "no verdict bullets"
        raise ValueError(msg)
    total = sum(counts)
    noun = "comment" if total == 1 else "comments"
    return f"{total} {noun}: {counts[0]} kept, {counts[1]} rewritten, {counts[2]} deleted"


def main() -> int:
    """Run the CLI."""
    try:
        print(tally(sys.stdin.read()))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
