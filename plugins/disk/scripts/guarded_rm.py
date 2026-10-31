#!/usr/bin/env python3
"""Check, list, and optionally delete one approved path.

Usage: guarded_rm.py --scope DIR [--keeper DIR ...] [--allow-history]
       [--delete] TARGET

Resolves TARGET with realpath and refuses (exit 2) when it is missing, is
or contains the scope or home root, lies outside SCOPE, or is, contains, or lies
inside a KEEPER, is, contains, or lies inside an agent-history root (unless
--allow-history), crosses a mount point, or cannot be fully inspected.
Otherwise prints the resolved target, size, and top-level entries (exit 0).
Only --delete removes it, after a synchronous open-handle check with lsof.
Missing or inconclusive probes, including one that exceeds its time limit,
refuse deletion. Symlinks inside
the tree are unlinked, never followed. A completed deletion reports the
filesystem's observed free-space delta, without attributing its cause.
"""

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_REFUSED = 2
LIST_LIMIT = 50
LSOF_TIMEOUT = 30
HISTORY_SUFFIXES = (
    (".claude", "projects"),
    (".codex", "sessions"),
    (".codex", "archived_sessions"),
)
WINDOWS_PROFILES = "/mnt/c/Users"


def contains(parent: str, child: str) -> bool:
    """Return True when child equals parent or lies beneath it."""
    return os.path.commonpath([parent, child]) == parent


def history_roots() -> list[str]:
    """Return existing agent-history roots in the home and Windows profiles."""
    homes = [str(Path.home().resolve())]
    with contextlib.suppress(OSError):
        homes += [e.path for e in os.scandir(WINDOWS_PROFILES) if e.is_dir()]
    return [str(Path(h, *suffix)) for h in homes for suffix in HISTORY_SUFFIXES]


def history_refusal(target: str) -> str | None:
    """Return the history root target is, contains, or lies inside, else None."""
    parts = Path(target).parts
    for suffix in HISTORY_SUFFIXES:
        width = len(suffix)
        for i in range(len(parts) - width + 1):
            if parts[i : i + width] == suffix:
                return str(Path(*parts[: i + width]))
    for root in history_roots():
        if contains(target, root):
            return root
    return None


def overlap_refusal(target: str, keepers: list[str], allow_history: bool) -> str | None:
    """Return why target overlaps a keeper or agent history, else None."""
    for keeper in keepers:
        if contains(keeper, target) or contains(target, keeper):
            return f"target overlaps a keeper ({keeper})"
    root = None if allow_history else history_refusal(target)
    if root:
        return f"target is, contains, or lies inside agent history ({root})"
    return None


def refusal(target: str, scope: str, keepers: list[str], allow_history: bool = False) -> str | None:
    """Return why a resolved target must not be removed, else None."""
    if not os.path.lexists(target):
        return "target does not exist"
    if contains(target, scope) or contains(target, str(Path.home().resolve())):
        return "target is or contains the approved scope or home directory"
    if not contains(scope, target):
        return "target resolves outside the approved scope"
    overlap = overlap_refusal(target, keepers, allow_history)
    if overlap:
        return overlap
    try:
        return crossing_mount(target, scope)
    except (OSError, ValueError, IndexError) as exc:
        return f"could not inspect the target's mount boundaries: {exc}"


def crossing_mount(target: str, scope: str) -> str | None:
    """Refuse mounted targets, nested mounts, and incomplete inspection."""
    dev = os.lstat(target).st_dev
    if os.path.ismount(target) or dev != os.lstat(scope).st_dev:
        return "target is a mount point or lies on another filesystem"
    if sys.platform.startswith("linux"):
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            mount = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), line.split()[4])
            if contains(target, mount) or (
                mount != scope and contains(scope, mount) and contains(mount, target)
            ):
                return f"target crosses a mount point ({mount})"
    if not Path(target).is_dir():
        return None

    def fail(error: OSError) -> None:
        raise error

    for root, dirs, files in os.walk(target, onerror=fail):
        for name in dirs + files:
            path = str(Path(root) / name)
            if os.lstat(path).st_dev != dev or os.path.ismount(path):
                return f"target holds a mount point or other filesystem ({path})"
    return None


def size_of(path: str) -> int:
    """Sum allocated bytes under path without following symlinks."""
    total = 0
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                total += (Path(root) / name).lstat().st_blocks * 512
            except OSError:
                continue
    return total


def _open_file_refusal(target: str) -> str | None:
    """Require a completed, error-free probe before any unlink."""
    lsof = shutil.which("lsof")
    if not lsof:
        return "lsof is required for open-handle inspection"
    command = [lsof, "-nP", "+w"]
    if Path(target).is_dir():
        command.append("+D")
    command.append(target)
    try:
        result = subprocess.run(  # noqa: S603
            command, capture_output=True, timeout=LSOF_TIMEOUT, check=False
        )
    except OSError, subprocess.TimeoutExpired:
        return "open-handle inspection failed or was incomplete"
    if result.stderr or result.returncode not in (0, 1):
        return "open-handle inspection failed or was incomplete"
    if result.returncode == 0 or result.stdout:
        return "target has open handles"
    return None


def human(nbytes: int) -> str:
    """Format bytes as GiB at or above 1 GiB, else MiB or KiB."""
    if nbytes >= 2**30:
        return f"{nbytes / 2**30:.2f} GiB"
    if nbytes >= 2**20:
        return f"{nbytes / 2**20:.1f} MiB"
    return f"{nbytes / 2**10:.0f} KiB"


def main(argv: list[str]) -> int:
    """Run the guard and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--keeper", action="append", default=[])
    parser.add_argument(
        "--allow-history",
        action="store_true",
        help="permit agent-history targets; pass only after the user names that history",
    )
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("target")
    args = parser.parse_args(argv[1:])
    target = os.path.realpath(args.target)
    scope = os.path.realpath(args.scope)
    keepers = [os.path.realpath(k) for k in args.keeper]
    reason = refusal(target, scope, keepers, args.allow_history)
    if reason:
        print(f"REFUSED - {reason}: {target}")
        return EXIT_REFUSED
    print(f"target: {target}")
    if Path(target).is_dir():
        print(f"size: {human(size_of(target))}")
        names: list[str] = sorted(entry.name for entry in os.scandir(target))
        for name in names[:LIST_LIMIT]:
            print(f"  {name}")
        if len(names) > LIST_LIMIT:
            print(f"  ... {len(names) - LIST_LIMIT} more")
    if not args.delete:
        print("OK - --delete checks open handles before removal")
        return EXIT_OK
    reason = _open_file_refusal(target)
    if reason:
        print(f"REFUSED - {reason}: {target}")
        return EXIT_REFUSED
    try:
        before = os.statvfs(scope)
    except OSError:
        print("REFUSED - could not measure filesystem free space")
        return EXIT_REFUSED
    print("open handles: none visible")
    if Path(target).is_dir() and not Path(target).is_symlink():
        shutil.rmtree(target)
    else:
        Path(target).unlink()
    print("DELETED")
    try:
        after = os.statvfs(scope)
    except OSError:
        print("filesystem free-space delta: unmeasured")
    else:
        delta = after.f_bavail * after.f_frsize - before.f_bavail * before.f_frsize
        sign = "+" if delta > 0 else "-" if delta < 0 else ""
        print(f"filesystem free-space delta: {sign}{human(abs(delta))}; cause not checked")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
