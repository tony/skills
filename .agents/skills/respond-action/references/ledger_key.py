#!/usr/bin/env python3
"""Print the feedback digest that keys a screening ledger.

Reads ``<id>`` TAB ``<text>`` lines from a file argument or stdin, or with
``--block <id> <file>`` hashes the whole file as one block under that id, or
with ``--pr <n|url|current>`` fetches the pull request's reviews, issue
comments, and inline review comments itself. The rubric's ledger section
defines the digest.

Exit codes: 0 digest printed, 2 usage, 4 ``gh`` failed (stderr says why; no
digest is printed, so a failed fetch never passes for empty feedback).
"""

# pyright: reportUnusedCallResult=false
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from ghcli import GhError, gh  # pyright: ignore[reportImplicitRelativeImport]

_BLOCK_ARGS = 3
_PR_ARGS = 2
_SURFACES = ("pulls/{n}/reviews", "issues/{n}/comments", "pulls/{n}/comments")


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


def pr_number(ref: str) -> str:
    """Return the number in ``ref``: a bare number, a pull request URL, or ``current``.

    >>> pr_number("12"), pr_number("https://github.com/o/r/pull/34/files")
    ('12', '34')
    """
    if ref.isdigit():
        return ref
    found = re.search(r"/pull/(\d+)", ref)
    if found:
        return found.group(1)
    return gh("pr", "view", "--json", "number", "--jq", ".number").strip()


def fetch_pr_lines(ref: str) -> str:
    """Return ``id<TAB>body`` lines for every comment surface of a pull request."""
    number = pr_number(ref)
    out = [
        gh(
            "api",
            f"repos/{{owner}}/{{repo}}/{surface.format(n=number)}",
            "--paginate",
            "--jq",
            ".[] | [.id, .body] | @tsv",
        )
        for surface in _SURFACES
    ]
    return "".join(chunk if chunk.endswith("\n") or not chunk else chunk + "\n" for chunk in out)


def main(argv: list[str] | None = None) -> int:
    """Print the digest of a file, stdin, or one block."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--block"] and len(args) == _BLOCK_ARGS:
        out = block_digest(args[1], Path(args[2]).read_text(encoding="utf-8"))
    elif args[:1] == ["--pr"] and len(args) == _PR_ARGS:
        try:
            out = digest(fetch_pr_lines(args[1]))
        except GhError as exc:
            sys.stderr.write(f"{exc}\n")
            return 4
    elif len(args) == 1 and not args[0].startswith("--"):
        out = digest(Path(args[0]).read_text(encoding="utf-8"))
    elif not args:
        out = digest(sys.stdin.read())
    else:
        sys.stderr.write("usage: ledger_key.py [FILE | --block ID FILE | --pr N]\n")
        return 2
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
