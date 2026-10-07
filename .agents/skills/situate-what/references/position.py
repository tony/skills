#!/usr/bin/env python3
"""Print the repository position for the situation sweep as JSON.

Read-only: runs only git queries, never fetches, and takes no optional locks.
Paths are never printed; the root is reported as flags and its basename.

Keys: ``root_name``, ``dotfile_repo`` (root is, or contains, the home
directory), ``has_commits``, ``branch`` (null when detached), ``trunk``,
``trunk_source``, ``trunk_age``, ``upstream``, ``base``, ``base_source``
(``upstream``, ``trunk`` or null), ``failed`` (lookups that did not resolve),
``ahead``, ``behind``, ``on_trunk``, ``staged``, ``modified``, ``untracked``,
``ignored_untracked`` (environment files filtered out) and ``stashes``.
Exits 2 with a message on stderr outside a git repository.
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_ENV_NAMES = frozenset(
    {
        ".claude",
        ".eval-artifacts",
        ".gitconfig",
        ".idea",
        ".mcp.json",
        ".profile",
        ".ripgreprc",
        ".vscode",
    }
)
_ENV_PREFIXES = (".bash", ".zsh")


def _git(*args: str, strip: bool = True) -> str | None:
    """Return stdout (stripped unless ``strip`` is false), or None on failure.

    >>> _git("definitely-not-a-subcommand") is None
    True
    """
    done = subprocess.run(
        ["git", "--no-optional-locks", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return None
    return done.stdout.strip() if strip else done.stdout


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


def _split_status(raw: str) -> tuple[int, int, list[str]]:
    r"""Count staged and modified entries and list untracked paths.

    >>> _split_status("M  a\0 M b\0?? c\0?? .zshrc\0")
    (1, 1, ['c', '.zshrc'])
    """
    staged = modified = 0
    untracked: list[str] = []
    for entry in raw.split("\0"):
        if len(entry) < 3:  # noqa: PLR2004
            continue
        code, path = entry[:2], entry[3:]
        if code == "??":
            untracked.append(path)
            continue
        staged += code[0] not in " ?"
        modified += code[1] not in " ?"
    return staged, modified, untracked


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
    out["trunk_age"] = _git("log", "-1", "--format=%cr", trunk) if trunk else None

    upstream = _git("rev-parse", "--abbrev-ref", "@{upstream}")
    own = f"origin/{out['branch']}"
    if upstream == own:
        upstream = None
    out["upstream"] = upstream

    failed: list[str] = []
    head = _git("rev-parse", "HEAD")
    base, base_source = None, None
    if upstream:
        base = _git("merge-base", "HEAD", upstream)
        base_source = "upstream"
        if base is None:
            failed.append("merge-base with upstream")
    if (base is None or base == head) and trunk:
        trunk_base = _git("merge-base", "HEAD", trunk)
        if trunk_base is None:
            failed.append("merge-base with trunk")
        else:
            base, base_source = trunk_base, "trunk"
    elif base is None:
        failed.append("trunk ref")
    out["base"], out["base_source"], out["failed"] = base, base_source, failed

    counts = _git("rev-list", "--left-right", "--count", f"{trunk}...HEAD") if trunk else None
    behind, ahead = (int(n) for n in counts.split()) if counts else (None, None)
    out["ahead"], out["behind"] = ahead, behind
    out["on_trunk"] = bool(trunk) and ahead == 0 and base == head

    raw = _git("status", "--porcelain=v1", "-z", "--untracked-files=normal", strip=False) or ""
    staged, modified, untracked = _split_status(raw)
    out["staged"], out["modified"] = staged, modified
    out["untracked"] = [p for p in untracked if not is_env_entry(p)]
    out["ignored_untracked"] = len(untracked) - len(out["untracked"])
    stash = _git("stash", "list") or ""
    out["stashes"] = len(stash.splitlines())
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
