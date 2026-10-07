#!/usr/bin/env python3
"""Print the feedback digest that keys a screening ledger.

Reads one ``<id>`` TAB ``<text>`` line per collected comment or pasted block on
stdin: the reviewer's original text, never an agent's paraphrase. Each text's
whitespace is collapsed, the lines are sorted bytewise, and the first 12 hex
characters of their SHA-256 are printed.
"""

# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import sys


def digest(text: str) -> str:
    r"""Return the 12-hex digest of ``id<TAB>text`` lines.

    >>> digest("101\tfirst  text\n202\tsecond\ttext\n") == digest(
    ...     "202\tsecond text\n101\tfirst text"
    ... )
    True
    >>> len(digest("101\tx"))
    12
    """
    lines: list[bytes] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        ident, _, body = raw.partition("\t")
        lines.append(f"{ident.strip()}\t{' '.join(body.split())}\n".encode())
    return hashlib.sha256(b"".join(sorted(lines))).hexdigest()[:12]


def main() -> int:
    """Print the digest of stdin."""
    sys.stdout.write(digest(sys.stdin.read()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
