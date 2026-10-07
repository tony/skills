#!/usr/bin/env python3
"""Deterministic steps for merge-pr: scope, stack order, fingerprints, merge.

``scope [REPO]`` prints ``local`` when REPO is absent or names the repository
behind ``origin``, else ``remote``. ``order [--repo REPO] PR...`` reads each PR
and prints the merge order as JSON. ``fingerprint record RANGE`` stores the
per-commit patch ids of a range and prints the record path;
``fingerprint verify RECORD RANGE`` compares a range against a record.
``message-path`` prints a fresh path for the merge message, and
``merge [--message-file FILE] -- ARGS...`` runs ``gh pr merge`` with that
message passed as arguments, never through a shell.
"""

# ruff: noqa: S603, S607, PLR2004, PLR0911
# pyright: reportUnusedCallResult=false, reportAny=false, reportImplicitStringConcatenation=false
from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PR_FIELDS = "number,baseRefName,headRefName,headRefOid"


def _run(*args: str, stdin: str | None = None) -> str:
    done = subprocess.run(
        args,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        sys.stderr.write(done.stderr or f"{args[0]} failed\n")
        raise SystemExit(1)
    return done.stdout


def repo_slug(text: str) -> str:
    """Reduce a repo spec or remote URL to a lowercase ``owner/name``.

    Examples
    --------
    >>> repo_slug("git@github.com:Acme/Widgets.git")
    'acme/widgets'
    >>> repo_slug("https://github.com/acme/widgets/")
    'acme/widgets'
    >>> repo_slug("github.com/acme/widgets")
    'acme/widgets'
    """
    parts = [p for p in re.split(r"[/:]", text.strip().removesuffix("/")) if p]
    if parts and parts[-1].endswith(".git"):
        parts[-1] = parts[-1][: -len(".git")]
    return "/".join(parts[-2:]).lower()


def scope(repo: str) -> str:
    """Return ``local`` when ``repo`` is empty or the cwd's origin, else ``remote``."""
    if not repo:
        return "local"
    done = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        return "remote"
    return "local" if repo_slug(done.stdout) == repo_slug(repo) else "remote"


def order_prs(prs: list[dict[str, object]]) -> dict[str, object]:
    """Order PRs bottom-up when stacked, else in the order given.

    Parameters
    ----------
    prs
        PR records with ``number``, ``baseRefName``, ``headRefName`` and
        ``headRefOid``, in the order the user gave them.

    Examples
    --------
    >>> prs = [
    ...     {"number": 2, "baseRefName": "a", "headRefName": "b", "headRefOid": "y"},
    ...     {"number": 1, "baseRefName": "main", "headRefName": "a", "headRefOid": "x"},
    ... ]
    >>> out = order_prs(prs)
    >>> out["topology"], out["order"], out["trunk"], out["parents"]
    ('stack', [1, 2], 'main', {'2': 1, '1': None})
    """
    by_head = {str(p["headRefName"]): int(str(p["number"])) for p in prs}
    parents: dict[int, int | None] = {
        int(str(p["number"])): by_head.get(str(p["baseRefName"])) for p in prs
    }
    given = [int(str(p["number"])) for p in prs]
    ordered: list[int] = []
    while len(ordered) < len(given):
        nxt = next(
            (n for n in given if n not in ordered and parents[n] in (None, *ordered)),
            None,
        )
        if nxt is None:
            sys.stderr.write("the PR bases form a cycle\n")
            raise SystemExit(1)
        ordered.append(nxt)
    trunks = sorted({str(p["baseRefName"]) for p in prs if parents[int(str(p["number"]))] is None})
    return {
        "topology": "stack" if any(v is not None for v in parents.values()) else "independent",
        "order": ordered,
        "trunk": trunks[0] if len(trunks) == 1 else None,
        "parents": {str(n): parents[n] for n in given},
        "heads": {str(p["number"]): p["headRefOid"] for p in prs},
    }


def order(repo: str, numbers: list[str]) -> int:
    """Read each PR with ``gh`` and print the merge order as JSON."""
    prs: list[dict[str, object]] = []
    for number in numbers:
        args = ["gh", "pr", "view", number, "--json", PR_FIELDS]
        if repo:
            args += ["--repo", repo]
        prs.append(json.loads(_run(*args)))
    sys.stdout.write(json.dumps(order_prs(prs), indent=2) + "\n")
    return 0


def _patch_ids(rev_range: str) -> list[str]:
    revs = _run("git", "rev-list", "--reverse", rev_range)
    if not revs.strip():
        return []
    patches = _run("git", "diff-tree", "--stdin", "-p", "-U0", stdin=revs)
    ids = _run("git", "patch-id", "--stable", stdin=patches)
    return [line.split(" ", 1)[0] for line in ids.splitlines() if line]


def _write_record(root: Path, text: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=root, prefix="fp-", suffix=".txt", delete=False, encoding="utf-8"
    ) as out:
        out.write(text)
    return out.name


def record(rev_range: str) -> int:
    """Store the patch ids of ``rev_range`` and print the record path.

    Falls back to a fresh temporary directory when the git directory is not
    writable, as in a sandboxed host.
    """
    ids = "".join(f"{pid}\n" for pid in _patch_ids(rev_range))
    root = Path(_run("git", "rev-parse", "--git-path", "merge-pr-fingerprints").strip())
    try:
        name = _write_record(root, ids)
    except OSError:
        name = _write_record(Path(tempfile.mkdtemp(prefix="merge-pr-fp.")), ids)
    sys.stdout.write(f"{name}\n")
    return 0


def verify(record_path: str, rev_range: str, resolved: list[str]) -> int:
    """Compare ``rev_range`` with a record; exit 1 on an unexplained difference.

    A commit whose patch id differs is tolerated when it touches a path in
    ``resolved`` (a file whose conflicts were resolved by hand), even when
    the change goes beyond the conflict hunks.
    """
    old = Path(record_path).read_text(encoding="utf-8").split()
    new = _patch_ids(rev_range)
    if len(old) != len(new):
        sys.stdout.write(f"count differs: recorded {len(old)}, now {len(new)}\n")
        return 1
    shas = _run("git", "rev-list", "--reverse", rev_range).split()
    bad = 0
    for i, (was, now) in enumerate(zip(old, new)):
        if was == now:
            continue
        files = _run("git", "diff-tree", "--no-commit-id", "--name-only", "-r", shas[i]).split()
        tag = "resolved" if set(files) & set(resolved) else "MISMATCH"
        bad += tag == "MISMATCH"
        sys.stdout.write(f"{tag} {i + 1} {shas[i][:7]}\n")
    sys.stdout.write("ok\n" if not bad else "")
    return 1 if bad else 0


def message_path() -> int:
    """Print a fresh path where the merge message is to be written."""
    d = tempfile.mkdtemp(prefix="merge-msg.")
    sys.stdout.write(f"{d}/message.txt\n")
    return 0


def merge(message_file: str, gh_args: list[str]) -> int:
    """Run ``gh pr merge`` with the message from ``message_file`` as arguments.

    The first line of the file is the subject; the body follows a blank line.
    Neither passes through a shell. The file and its directory are removed.
    """
    cmd = ["gh", "pr", "merge", *gh_args]
    msg = Path(message_file) if message_file else None
    body_file: Path | None = None
    try:
        if msg:
            subject, _, body = msg.read_text(encoding="utf-8").partition("\n")
            if not subject.strip():
                sys.stderr.write("the message file has no subject line\n")
                return 1
            cmd += ["-t", subject.strip()]
            if body.strip():
                body_file = msg.with_name("body.txt")
                body_file.write_text(body.strip("\n") + "\n", encoding="utf-8")
                cmd += ["-F", str(body_file)]
        return subprocess.run(cmd, check=False).returncode
    finally:
        for p in (body_file, msg):
            if p:
                p.unlink(missing_ok=True)
        if msg and msg.parent.name.startswith("merge-msg."):
            with contextlib.suppress(OSError):
                msg.parent.rmdir()


def _flag(argv: list[str], name: str) -> str:
    if name in argv:
        i = argv.index(name)
        value = argv[i + 1] if i + 1 < len(argv) else ""
        del argv[i : i + 2]
        return value
    return ""


def main(argv: list[str]) -> int:
    """Dispatch the subcommands."""
    cmd, rest = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "scope" and len(rest) <= 1:
        sys.stdout.write(scope(rest[0] if rest else "") + "\n")
        return 0
    if cmd == "order":
        repo = _flag(rest, "--repo")
        if rest:
            return order(repo, rest)
    if cmd == "fingerprint" and rest[:1] == ["record"] and len(rest) == 2:
        return record(rest[1])
    if cmd == "fingerprint" and rest[:1] == ["verify"] and len(rest) >= 3:
        args = rest[1:]
        resolved: list[str] = []
        while "--resolved" in args:
            resolved.append(_flag(args, "--resolved"))
        if len(args) == 2:
            return verify(args[0], args[1], resolved)
    if cmd == "message-path" and not rest:
        return message_path()
    if cmd == "merge" and "--" in rest:
        i = rest.index("--")
        head, gh_args = rest[:i], rest[i + 1 :]
        message_file = _flag(head, "--message-file")
        if not head and gh_args:
            return merge(message_file, gh_args)
    sys.stderr.write(
        "usage: merge_pr.py scope [REPO]"
        " | order [--repo REPO] PR..."
        " | fingerprint record RANGE"
        " | fingerprint verify RECORD RANGE [--resolved PATH]..."
        " | message-path"
        " | merge [--message-file FILE] -- GH_PR_MERGE_ARGS...\n",
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
