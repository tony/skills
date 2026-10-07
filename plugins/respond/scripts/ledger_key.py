#!/usr/bin/env python3
"""Print the feedback digest that keys a screening ledger.

Reads one ``<source>`` TAB ``<claim>`` line per finding on stdin, as collected
and before dedup. Each claim's whitespace is collapsed, the lines are sorted
bytewise, and the first 12 hex characters of their SHA-256 are printed.
"""

# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import sys


def digest(text: str) -> str:
    r"""Return the 12-hex digest of ``source<TAB>claim`` lines.

    >>> digest("alex\tfirst  claim\nlint-bot\tsecond\tclaim\n") == digest(
    ...     "lint-bot\tsecond claim\nalex\tfirst claim"
    ... )
    True
    >>> len(digest("alex\tx"))
    12
    """
    lines: list[bytes] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        source, _, claim = raw.partition("\t")
        lines.append(f"{source.strip()}\t{' '.join(claim.split())}\n".encode())
    return hashlib.sha256(b"".join(sorted(lines))).hexdigest()[:12]


def main() -> int:
    """Print the digest of stdin."""
    sys.stdout.write(digest(sys.stdin.read()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
