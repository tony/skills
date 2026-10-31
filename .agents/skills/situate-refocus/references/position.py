#!/usr/bin/env python3
"""Print the repository position for the situation sweep as JSON.

Read-only: runs only git queries, never fetches, and takes no optional locks.
The root is reported as flags and its basename; untracked paths are relative.

Keys: ``root_name``, ``dotfile_repo`` (root is, or contains, the home
directory), ``has_commits``, ``branch`` (null when detached), ``trunk``,
``trunk_source``, ``trunk_tip_age`` (when the trunk tip commit was made),
``last_fetch`` (age of FETCH_HEAD, or "unknown"), ``upstream``, ``base``, ``base_source``
(``upstream`` only when the upstream is a branch other than trunk, else
``trunk`` or null), ``failed`` (lookups that did not resolve),
``ahead``, ``behind``, ``on_trunk``, ``staged``, ``modified``, ``conflicts``
(unmerged paths, counted once and not in the other two), ``untracked``,
``ignored_untracked`` (environment files filtered out) and ``stashes``.
Failed status or stash queries leave their fields null, not empty or zero.
Exits 2 with a message on stderr outside a git repository.
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_ENV_NAMES = frozenset(
    {
        ".claude",
        ".eval-artifacts",
        ".gitconfig",
        ".idea",
        ".profile",
        ".ripgreprc",
        ".vscode",
        ".zprofile",
    }
)
_UNMERGED = frozenset({"DD", "AU", "UD", "UA", "DU", "AA", "UU"})
_ENV_PREFIXES = (".bash", ".zsh")


def _git(*args: str, strip: bool = True) -> str | None:
    """Return stdout without its final newline, or None on failure.

    >>> _git("definitely-not-a-subcommand") is None
    True
    """
    done = subprocess.run(
        ["git", "--no-optional-locks", *args],  # noqa: S607
        check=False,
        capture_output=True,
    )
    if done.returncode != 0:
        return None
    output = os.fsdecode(done.stdout)
    return output.removesuffix("\n") if strip else output


def _age(seconds: float) -> str:
    """Format an age in seconds as a coarse phrase.

    >>> _age(5), _age(7200), _age(3 * 86400)
    ('just now', '2 hours ago', '3 days ago')
    """
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


def last_fetch_age() -> str:
    """Return the age of FETCH_HEAD, or "unknown" when nothing was fetched."""
    path = _git("rev-parse", "--git-path", "FETCH_HEAD")
    try:
        return _age(time.time() - Path(path).stat().st_mtime) if path else "unknown"
    except OSError:
        return "unknown"


def is_env_entry(path: str) -> bool:
    """Say whether an untracked top-level path is editor or shell state.

    >>> is_env_entry(".zshrc"), is_env_entry(".idea/"), is_env_entry("src/")
    (True, True, False)
    >>> is_env_entry(".github/")
    False
    """
    if "/" in path.rstrip("/"):
        return False
    name = path.rstrip("/")
    return name in _ENV_NAMES or name.startswith(_ENV_PREFIXES)


def _is_dotfile_repo(root: Path, home: Path) -> bool:
    """Say whether root is the home directory or contains it.

    >>> _is_dotfile_repo(Path("/h"), Path("/h")), _is_dotfile_repo(Path("/"), Path("/h"))
    (True, True)
    >>> _is_dotfile_repo(Path("/h/p"), Path("/h"))
    False
    """
    return root == home or root in home.parents


def find_trunk(override: str | None) -> tuple[str | None, str | None]:
    """Return (trunk ref, how it was found).

    >>> find_trunk("origin/dev")
    ('origin/dev', 'given')
    """
    if override:
        return override, "given"
    head = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head:
        return head, "origin/HEAD"
    for ref in ("origin/main", "origin/master"):
        if _git("rev-parse", "--verify", "--quiet", ref):
            return ref, f"assumed {ref}"
    return None, None


def _split_status(raw: str) -> tuple[int, int, int, list[str]]:
    r"""Count staged, modified and conflicted entries and list untracked paths.

    >>> _split_status("M  a\0 M b\0?? c\0?? .zshrc\0")
    (1, 1, 0, ['c', '.zshrc'])

    An unmerged entry is one conflict, not also staged and modified:

    >>> _split_status("UU a\0AA b\0DD c\0")
    (0, 0, 3, [])

    A rename or copy is followed by an entry holding the old path:

    >>> _split_status("R  new\0old\0")
    (1, 0, 0, [])
    """
    staged = modified = conflicts = 0
    untracked: list[str] = []
    skip_next = False
    for entry in raw.split("\0"):
        if skip_next:
            skip_next = False
            continue
        if len(entry) < 3:  # noqa: PLR2004
            continue
        skip_next = "R" in entry[:2] or "C" in entry[:2]
        code, path = entry[:2], entry[3:]
        if code == "??":
            untracked.append(path)
            continue
        if code in _UNMERGED:
            conflicts += 1
            continue
        staged += code[0] not in " ?"
        modified += code[1] not in " ?"
    return staged, modified, conflicts, untracked


def _worktree_status(failed: list[str]) -> dict[str, object]:
    """Read worktree counts, leaving failed observations unknown."""
    raw = _git("status", "--porcelain=v1", "-z", "--untracked-files=normal", strip=False)
    if raw is None:
        failed.append("worktree status")
        return {
            "staged": None,
            "modified": None,
            "conflicts": None,
            "untracked": None,
            "ignored_untracked": None,
        }
    staged, modified, conflicts, untracked = _split_status(raw)
    visible = [p for p in untracked if not is_env_entry(p)]
    return {
        "staged": staged,
        "modified": modified,
        "conflicts": conflicts,
        "untracked": visible,
        "ignored_untracked": len(untracked) - len(visible),
    }


def position(trunk_override: str | None = None) -> dict[str, object]:
    """Gather the position from the current directory."""
    root = _git("rev-parse", "--show-toplevel")
    if root is None:
        msg = "not inside a git repository"
        raise SystemExit(msg)
    out: dict[str, object] = {
        "root_name": Path(root).name,
        "dotfile_repo": _is_dotfile_repo(Path(root).resolve(), Path.home().resolve()),
        "has_commits": _git("rev-parse", "--verify", "--quiet", "HEAD") is not None,
    }
    if out["dotfile_repo"] or not out["has_commits"]:
        return out

    out["branch"] = _git("symbolic-ref", "--short", "--quiet", "HEAD")
    trunk, source = find_trunk(trunk_override)
    out["trunk"], out["trunk_source"] = trunk, source
    out["trunk_tip_age"] = _git("log", "-1", "--format=%cr", trunk) if trunk else None
    out["last_fetch"] = last_fetch_age()

    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    out["upstream"] = upstream
    tracked_branch = _git("config", "--get", f"branch.{out['branch']}.merge")
    own_branch = tracked_branch == f"refs/heads/{out['branch']}"
    stacked = upstream if upstream and upstream != trunk and not own_branch else None

    failed: list[str] = []
    head = _git("rev-parse", "HEAD")
    base, base_source = None, None
    if stacked:
        base = _git("merge-base", "HEAD", stacked)
        base_source = "upstream"
        if base is None:
            failed.append("merge-base with upstream")
    if base == head and not trunk:
        base, base_source = None, None
        failed.append("trunk ref")
    elif (base is None or base == head) and trunk:
        trunk_base = _git("merge-base", "HEAD", trunk)
        if trunk_base is None:
            failed.append("merge-base with trunk")
        else:
            base, base_source = trunk_base, "trunk"
    elif base is None and not stacked:
        failed.append("trunk ref")
    out["base"], out["base_source"], out["failed"] = base, base_source, failed

    counts = _git("rev-list", "--left-right", "--count", f"{trunk}...HEAD") if trunk else None
    if trunk and counts is None:
        failed.append("ahead/behind with trunk")
    behind, ahead = (int(n) for n in counts.split()) if counts else (None, None)
    out["ahead"], out["behind"] = ahead, behind
    out["on_trunk"] = bool(trunk) and ahead == 0 and base == head

    out.update(_worktree_status(failed))
    stash = _git("stash", "list")
    if stash is None:
        failed.append("stash list")
    out["stashes"] = len(stash.splitlines()) if stash is not None else None
    return out


def main(argv: list[str] | None = None) -> int:
    """Print the position as JSON."""
    parser = argparse.ArgumentParser(description="Print the repository position as JSON.")
    parser.add_argument("--trunk", help="trunk ref to use instead of discovering one")
    args = parser.parse_args(argv)
    try:
        result = position(args.trunk)
    except SystemExit as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
