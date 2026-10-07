#!/usr/bin/env python3
"""Print the feedback digest that keys a screening ledger.

Reads ``<id>`` TAB ``<text>`` lines from a file argument or stdin, or with
``--block <id> <file>`` hashes the whole file as one block under that id. The
rubric's ledger section defines the digest.
"""

# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

_BLOCK_ARGS = 3


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


def block_digest(ident: str, text: str) -> str:
    r"""Return the digest of one whole block, newlines included.

    >>> block_digest("paste", "a\nb") == digest("paste\ta b")
    True
    """
    return digest(f"{ident}\t{' '.join(text.split())}")


def main(argv: list[str] | None = None) -> int:
    """Print the digest of a file, stdin, or one block."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--block"] and len(args) == _BLOCK_ARGS:
        out = block_digest(args[1], Path(args[2]).read_text(encoding="utf-8"))
    elif len(args) == 1 and not args[0].startswith("--"):
        out = digest(Path(args[0]).read_text(encoding="utf-8"))
    elif not args:
        out = digest(sys.stdin.read())
    else:
        sys.stderr.write("usage: ledger_key.py [FILE | --block ID FILE]\n")
        return 2
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
