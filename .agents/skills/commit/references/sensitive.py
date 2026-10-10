#!/usr/bin/env python3
"""Classify changed paths as sensitive by name or by content marker.

``scan [--allow PATH]...`` reads the working tree of the current repository
and prints one tab-separated line per changed path::

    <ok|refuse> <staged|partial|unstaged|untracked> <path> <reason>

``partial`` is a path with both staged and unstaged changes. ``reason`` is
``name:<pattern>`` or ``content:<marker>`` for a refusal and empty otherwise.
A matched value is never printed. A path named with ``--allow`` is never
refused. Exit status is 1 when a staged or partial path is refused, so the
commit must not proceed.
"""

# ruff: noqa: S603, S607
# pyright: reportUnusedCallResult=false
from __future__ import annotations

import os
import re
import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

NAME_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.p8",
    "*.keystore",
    "*.gpg",
    "id_*",
    "*credentials*",
    "*secret*",
    "*.tfvars",
    "*.tfstate",
    "*.tfstate.*",
    ".git-credentials",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".pgpass",
    ".htpasswd",
    "kubeconfig",
    "kubeconfig.*",
)
PATH_PATTERNS = (".kube/config", ".docker/config.json")
EXEMPT_SUFFIXES = (".example", ".sample", ".pub")

CONTENT_MARKERS = (
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY( BLOCK)?-----")),
    ("aws-access-key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("stripe-key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}")),
    ("api-key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
)
MAX_BYTES = 1_000_000


def name_reason(path: str) -> str:
    """Return ``name:<pattern>`` when ``path`` is a sensitive name, else ``""``.

    Examples
    --------
    >>> name_reason("config/.env")
    'name:.env'
    >>> name_reason("infra/terraform.tfstate")
    'name:*.tfstate'
    >>> name_reason("home/.docker/config.json")
    'name:.docker/config.json'
    >>> name_reason(".env.example")
    ''
    >>> name_reason("keys/id_ed25519.pub")
    ''
    >>> name_reason("src/app.py")
    ''
    """
    lower = path.lower()
    base = PurePosixPath(lower).name
    if base.endswith(EXEMPT_SUFFIXES):
        return ""
    for pattern in PATH_PATTERNS:
        if lower == pattern or lower.endswith("/" + pattern):
            return f"name:{pattern}"
    for pattern in NAME_PATTERNS:
        if fnmatchcase(base, pattern):
            return f"name:{pattern}"
    return ""


def content_reason(text: str) -> str:
    """Return ``content:<marker>`` for the first marker found in ``text``.

    Examples
    --------
    >>> content_reason("-----BEGIN OPENSSH PRIVATE KEY-----")
    'content:private-key'
    >>> content_reason("token = 'AKIAABCDEFGHIJKLMNOP'")
    'content:aws-access-key'
    >>> content_reason("greeting = 'hello'")
    ''
    """
    for label, pattern in CONTENT_MARKERS:
        if pattern.search(text):
            return f"content:{label}"
    return ""


def _git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if done.returncode:
        sys.stderr.write(done.stderr or "git failed\n")
        raise SystemExit(2)
    return done.stdout


def _names(*args: str) -> list[str]:
    return [p for p in _git(*args, "-z").split("\0") if p]


def _added(*diff_args: str) -> str:
    lines = _git("diff", "-U0", *diff_args).splitlines()
    return "\n".join(x[1:] for x in lines if x.startswith("+") and not x.startswith("+++"))


def _untracked_text(path: str) -> str:
    try:
        with Path(path).open("rb") as handle:
            return handle.read(MAX_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return ""


def scan(allow: set[str]) -> int:
    """Print a verdict for every changed path; return 1 on a refused staged path."""
    os.chdir(_git("rev-parse", "--show-toplevel").strip())
    staged = _names("diff", "--cached", "--name-only")
    unstaged = _names("diff", "--name-only")
    untracked = _names("ls-files", "--others", "--exclude-standard")
    rows: list[tuple[str, str]] = []
    for path in dict.fromkeys(staged + unstaged):
        state = "partial" if path in staged and path in unstaged else "staged"
        rows.append((state if path in staged else "unstaged", path))
    rows += [("untracked", p) for p in untracked]
    blocked = False
    for state, path in rows:
        reason = ""
        if path not in allow:
            reason = name_reason(path)
            if not reason and state in ("staged", "partial"):
                reason = content_reason(_added("--cached", "--", path))
            elif not reason and state == "unstaged":
                reason = content_reason(_added("--", path))
            elif not reason:
                reason = content_reason(_untracked_text(path))
        verdict = "refuse" if reason else "ok"
        blocked = blocked or (verdict == "refuse" and state in ("staged", "partial"))
        sys.stdout.write(f"{verdict}\t{state}\t{path}\t{reason}\n")
    return 1 if blocked else 0


def main(argv: list[str]) -> int:
    """Dispatch the subcommands."""
    if argv[:1] == ["scan"]:
        rest = argv[1:]
        allow: set[str] = set()
        while rest[:1] == ["--allow"] and rest[1:2]:
            allow.add(rest[1])
            rest = rest[2:]
        if not rest:
            return scan(allow)
    sys.stderr.write("usage: sensitive.py scan [--allow PATH]...\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
