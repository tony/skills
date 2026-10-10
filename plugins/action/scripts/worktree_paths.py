#!/usr/bin/env python3
"""Derive branch slugs and worktree paths, and test the home-directory guard.

Subcommands:

``slug --file TITLE_FILE [--prefix PREFIX]``
    Print a branch name: ``PREFIX-`` plus the kebab slug of the title read
    from the file, truncated at a word boundary so the whole name is at most
    60 characters. Without ``--prefix`` print the slug alone.

``path --branch BRANCH [--temp]``
    Print the worktree path for the repository in the current directory:
    ``{main_checkout}-{branch with / flattened to -}``, or with ``--temp``
    ``${TMPDIR:-/tmp}/action-worktrees/{repo}-{cksum}/{flattened}``.

``guard``
    Exit 2 and print ``refuse: <toplevel>`` when the repository root is the
    physical home directory or contains it; print nothing and exit 0
    otherwise. Outside a git repository, exit 1 with ``not a git repository``.

Titles come from tickets and are untrusted, so ``slug`` reads a file and
never takes the title as an argument.
"""

# ruff: noqa: S603, S607
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_NAME = 60
REFUSED = 2
# A name that passes this is inert in a shell word; git's own check is not.
SAFE_BRANCH = re.compile(r"[A-Za-z0-9._/][A-Za-z0-9._/-]*")


def slugify(title: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to ``-``, trim ``-``.

    A title with no ASCII letters or digits gets ``goal-`` and a short hash,
    so the slug is never empty.

    >>> slugify("Fix: login redirect (v2)!")
    'fix-login-redirect-v2'
    >>> slugify("日本語")
    'goal-77710aed'
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if slug:
        return slug
    return "goal-" + hashlib.sha256(title.encode()).hexdigest()[:8]


def branch_name(title: str, prefix: str = "") -> str:
    """Join prefix and slug, truncating the slug at a word boundary.

    >>> branch_name("Fix login redirect", "tea-123")
    'tea-123-fix-login-redirect'
    >>> len(branch_name("word " * 30, "tea-1")) <= 60
    True
    """
    slug = slugify(title)
    head = f"{prefix}-" if prefix and slug else prefix
    room = MAX_NAME - len(head)
    if not prefix:
        room = MAX_NAME
    if room <= 0:
        return prefix
    if len(slug) > room:
        cut = slug[:room]
        if slug[room] != "-" and "-" in cut:
            cut = cut[: cut.rindex("-")]
        slug = cut.strip("-")
    if prefix and not slug:
        return prefix
    return head + slug


def branch_problem(name: str) -> str | None:
    """Return why ``name`` cannot be used as a branch, or ``None``.

    >>> branch_problem("tea-123-fix-login")
    >>> branch_problem("feat/a$(id)b")
    'characters outside A-Z a-z 0-9 . _ / -, or a leading -'
    """
    if not SAFE_BRANCH.fullmatch(name):
        return "characters outside A-Z a-z 0-9 . _ / -, or a leading -"
    ok = subprocess.run(
        ["git", "check-ref-format", "--branch", name],
        capture_output=True,
        check=False,
    )
    return None if ok.returncode == 0 else "git check-ref-format rejects it"


def posix_cksum(data: bytes) -> int:
    """Return the POSIX ``cksum`` CRC of ``data``.

    >>> posix_cksum(b"123456789")
    930766865
    """
    crc = 0
    for byte in data + _length_bytes(len(data)):
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _TABLE[((crc >> 24) ^ byte) & 0xFF]
    return ~crc & 0xFFFFFFFF


def _length_bytes(length: int) -> bytes:
    out = bytearray()
    while length:
        out.append(length & 0xFF)
        length >>= 8
    return bytes(out)


def _make_table() -> list[int]:
    table: list[int] = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else crc << 1
            crc &= 0xFFFFFFFF
        table.append(crc)
    return table


_TABLE = _make_table()


def flatten(branch: str) -> str:
    """Flatten ``/`` to ``-`` for use in a directory name.

    >>> flatten("feat/tea-123-login")
    'feat-tea-123-login'
    """
    return branch.replace("/", "-")


def worktree_path(main: str, branch: str, temp: bool, tmpdir: str) -> str:
    """Return the worktree path for ``branch`` of the checkout at ``main``.

    >>> worktree_path("/work/shop/", "feat/tea-1", False, "/tmp")
    '/work/shop-feat-tea-1'
    >>> worktree_path("/work/shop", "a", True, "/tmp").startswith(
    ...     "/tmp/action-worktrees/shop-")
    True
    """
    main = main.rstrip("/")
    if not temp:
        return f"{main}-{flatten(branch)}"
    digest = posix_cksum(main.encode())
    repo = Path(main).name
    root = tmpdir.rstrip("/") or "/"
    return f"{root}/action-worktrees/{repo}-{digest}/{flatten(branch)}"


def home_inside(top: str, home: str) -> bool:
    """Return whether ``home`` is ``top`` or lies under it.

    >>> home_inside("/", "/home/u")
    True
    >>> home_inside("/home/u", "/home/u")
    True
    >>> home_inside("/home/u/src/app", "/home/u")
    False
    >>> home_inside("/home/ux", "/home/u")
    False
    """
    top = top.rstrip("/")
    return (home.rstrip("/") + "/").startswith(top + "/")


def _git(*args: str) -> str:
    done = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return done.stdout.strip()


def _main_checkout() -> str:
    for line in _git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            return line[len("worktree ") :]
    msg = "no worktree entry"
    raise RuntimeError(msg)


def _check(name: str) -> int:
    problem = branch_problem(name)
    if problem:
        print(f"refuse: {problem}")
        return REFUSED
    print(name)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_slug = sub.add_parser("slug")
    p_slug.add_argument("--file", required=True)
    p_slug.add_argument("--prefix", default="")
    p_path = sub.add_parser("path")
    p_path.add_argument("--branch", required=True)
    p_path.add_argument("--temp", action="store_true")
    sub.add_parser("guard")
    p_check = sub.add_parser("check")
    p_check.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "check":
        return _check(Path(args.file).read_text(encoding="utf-8").strip())

    if args.cmd == "slug":
        title = Path(args.file).read_text(encoding="utf-8")
        print(branch_name(title, args.prefix))
        return 0
    try:
        if args.cmd == "path":
            tmpdir = os.environ.get("TMPDIR") or "/tmp"  # noqa: S108
            print(worktree_path(_main_checkout(), args.branch, args.temp, tmpdir))
            return 0
        top = os.path.realpath(_git("rev-parse", "--show-toplevel"))
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"not a git repository: {exc}", file=sys.stderr)
        return 1
    home = os.path.realpath(Path("~").expanduser())
    if home_inside(top, home):
        print(f"refuse: {top}")
        return REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
