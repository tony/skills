#!/usr/bin/env python3
"""Watch disk, inodes, memory, and pressure during a goal; clean only what it owns.

``check`` compares free space, free inodes, available memory, and pressure stall
figures against reserves and prints one line the Claude evaluator can read.
``sample`` runs a command and reports its wall time, CPU time, and the peak RSS
of its process tree. ``register`` records the worktrees a goal owns; ``clean``
removes build-artifact directories inside them that git ignores and no tracked
file lives in, dry by default.

Run ``resources.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import time
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Sequence

GIB = 2**30
ARTIFACT_NAMES = frozenset(
    {
        "target",
        "node_modules",
        "_build",
        "deps",
        "dist",
        "build",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
PROC = Path("/proc")


@dataclasses.dataclass(frozen=True)
class Reserves:
    """The floors a goal keeps free before it launches more work."""

    disk_gib: float = 20
    inodes: int = 10000
    mem_gib: float = 4
    cpu_pressure_pct: float = 60
    mem_pressure_pct: float = 10


class Usage(t.NamedTuple):
    """CPU time and peak RSS of the children this process has waited for."""

    user: float
    system: float
    peak_kib: int


class Args(argparse.Namespace):
    """Typed view of every CLI option."""

    cmd: str = ""
    path: list[str] = []  # noqa: RUF012
    reserve_disk_gib: float = Reserves.disk_gib
    reserve_inodes: int = Reserves.inodes
    reserve_mem_gib: float = Reserves.mem_gib
    cpu_pressure_pct: float = Reserves.cpu_pressure_pct
    mem_pressure_pct: float = Reserves.mem_pressure_pct
    interval: float = 5.0
    command: list[str] = []  # noqa: RUF012
    manifest: str = ""
    roots: list[str] = []  # noqa: RUF012
    apply: bool = False


def _meminfo(proc: Path) -> dict[str, int]:
    """Read ``/proc/meminfo`` into bytes per field."""
    path = proc / "meminfo"
    if not path.is_file():
        return {}
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            values[key] = int(parts[0]) * (1024 if parts[1:] == ["kB"] else 1)
    return values


def _pressure(proc: Path, name: str) -> float | None:
    """Return the ``some avg10`` stall percentage, or None without readable PSI.

    A kernel built with PSI but booted with it off refuses the read.

    Examples
    --------
    >>> _pressure(Path("/nonexistent"), "cpu") is None
    True
    """
    try:
        text = (proc / "pressure" / name).read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("some "):
            for field in line.split()[1:]:
                key, _, value = field.partition("=")
                if key == "avg10":
                    return float(value)
    return None


def _mac_available() -> int | None:
    """Approximate available memory on macOS from free plus inactive pages."""
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout  # noqa: S607
    except (OSError, subprocess.CalledProcessError):
        return None
    page = 4096
    pages = 0
    for line in out.splitlines():
        if "page size of" in line:
            page = int(line.split("page size of")[1].split()[0])
        key, _, value = line.partition(":")
        if key in {"Pages free", "Pages inactive", "Pages speculative"}:
            pages += int(value.strip().rstrip("."))
    return pages * page


def reported_inodes(files: int, favail: int) -> int | None:
    """Return free inodes, or None where the filesystem does not count them.

    WSL's drvfs reports more free inodes than it has; a filesystem with no
    inode table reports zero of each.
    """
    return favail if files > 0 and favail <= files else None


def _filesystem(path: Path) -> dict[str, int | None]:
    if not hasattr(os, "statvfs"):  # Windows: no statvfs and no inode counts
        return {"free_bytes": shutil.disk_usage(path).free, "free_inodes": None}
    stat = os.statvfs(path)
    return {
        "free_bytes": stat.f_bavail * stat.f_frsize,
        "free_inodes": reported_inodes(stat.f_files, stat.f_favail),
    }


def snapshot(paths: list[Path], proc: Path = PROC) -> dict[str, object]:
    """Read free space and inodes per path, available memory, load, and pressure.

    Inodes read as None where the filesystem does not count them; pressure
    reads as None without pressure stall information (macOS, older kernels).
    """
    mem = _meminfo(proc)
    available: int | None = mem.get("MemAvailable")
    if available is None and sys.platform == "darwin":
        available = _mac_available()
    load: list[float] | None = None
    if hasattr(os, "getloadavg"):
        with contextlib.suppress(OSError):
            load = list(os.getloadavg())
    return {
        "filesystems": {str(p): _filesystem(p) for p in paths},
        "mem_available_bytes": available,
        "swap_free_bytes": mem.get("SwapFree"),
        "load": load,
        "cpu_count": os.cpu_count(),
        "cpu_pressure_pct": _pressure(proc, "cpu"),
        "mem_pressure_pct": _pressure(proc, "memory"),
    }


def breaches(snap: dict[str, object], reserves: Reserves) -> list[str]:
    """Name each reserve the snapshot falls below, filesystems first."""
    found: list[str] = []
    filesystems = t.cast("dict[str, dict[str, int | None]]", snap["filesystems"])
    for path, fs in filesystems.items():
        free = fs["free_bytes"]
        if free is not None and free < reserves.disk_gib * GIB:
            found.append(f"disk {path}")
        inodes = fs["free_inodes"]
        if inodes is not None and inodes < reserves.inodes:
            found.append(f"inodes {path}")
    available = t.cast("int | None", snap.get("mem_available_bytes"))
    if available is not None and available < reserves.mem_gib * GIB:
        found.append("memory")
    cpu = t.cast("float | None", snap.get("cpu_pressure_pct"))
    if cpu is not None and cpu > reserves.cpu_pressure_pct:
        found.append("cpu pressure")
    memory = t.cast("float | None", snap.get("mem_pressure_pct"))
    if memory is not None and memory > reserves.mem_pressure_pct:
        found.append("memory pressure")
    return found


def summary_line(snap: dict[str, object], breached: list[str]) -> str:
    """Format the one line a goal prints so its evaluator sees the readings.

    The free figure is the lowest across the checked filesystems.
    """
    filesystems = t.cast("dict[str, dict[str, int | None]]", snap["filesystems"])
    frees = [fs["free_bytes"] for fs in filesystems.values() if fs["free_bytes"] is not None]
    parts = [f"{min(frees) / GIB:.0f} GiB free" if frees else "free space unknown"]
    available = t.cast("int | None", snap.get("mem_available_bytes"))
    parts.append(
        f"{available / GIB:.1f} GiB available" if available is not None else "memory unknown"
    )
    cpu = t.cast("float | None", snap.get("cpu_pressure_pct"))
    parts.append(f"cpu pressure {cpu:.0f}%" if cpu is not None else "cpu pressure unknown")
    head = f"resources low ({', '.join(breached)})" if breached else "resources ok"
    return f"{head}: {', '.join(parts)}"


def _tree_rss_kib(root_pid: int) -> int:
    """Sum the RSS of a process and its descendants, from ``ps``."""
    try:
        rows = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid=,rss="],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return 0
    table: dict[int, tuple[int, int]] = {}
    for row in rows.splitlines():
        fields = row.split()
        if len(fields) == len(("pid", "ppid", "rss")) and all(f.isdigit() for f in fields):
            table[int(fields[0])] = (int(fields[1]), int(fields[2]))
    owned = {root_pid}
    grew = True
    while grew:
        children = {pid for pid, (ppid, _) in table.items() if ppid in owned}
        grew = not children <= owned
        owned |= children
    return sum(table[pid][1] for pid in owned if pid in table)


def _children_usage() -> Usage | None:
    """Read CPU time and peak RSS for waited-for children; None without POSIX ``resource``."""
    try:
        import resource  # noqa: PLC0415 - POSIX only; check, register, and clean run without it
    except ImportError:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    # ru_maxrss is KiB on Linux and bytes on macOS.
    peak = usage.ru_maxrss // 1024 if sys.platform == "darwin" else usage.ru_maxrss
    return Usage(usage.ru_utime, usage.ru_stime, peak)


def sample(command: list[str], interval: float) -> tuple[int, dict[str, object]]:
    """Run a command and report its time and peak memory.

    The peak is the larger of the polled process-tree RSS and the largest single
    child ``getrusage`` reports.
    """
    paths = [Path.cwd()]
    before = snapshot(paths)
    usage = _children_usage()
    start = time.monotonic()
    proc = subprocess.Popen(command)  # noqa: S603
    peak = 0
    while True:
        peak = max(peak, _tree_rss_kib(proc.pid))
        try:
            code = proc.wait(timeout=interval)
            break
        except subprocess.TimeoutExpired:
            continue
    wall = time.monotonic() - start
    after = _children_usage()
    user = system = None
    if usage is not None and after is not None:
        # getrusage catches a child that exited between polls.
        peak = max(peak, after.peak_kib)
        user, system = round(after.user - usage.user, 3), round(after.system - usage.system, 3)
    return code, {
        "exit": code,
        "wall_seconds": round(wall, 3),
        "user_seconds": user,
        "system_seconds": system,
        "max_rss_mib": round(peak / 1024, 1),
        "before": before,
        "after": snapshot(paths),
    }


def _roots(manifest: Path) -> list[str]:
    if not manifest.is_file():
        return []
    data = t.cast("dict[str, list[str]]", json.loads(manifest.read_text(encoding="utf-8")))
    return list(data.get("roots", []))


def register(manifest: Path, roots: list[Path]) -> None:
    """Record worktrees a goal owns, keeping one entry per resolved root."""
    known = _roots(manifest)
    for root in roots:
        path = str(root.resolve())
        if path not in known:
            known.append(path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    _ = manifest.write_text(json.dumps({"roots": known}, indent=2) + "\n", encoding="utf-8")


def _walk_owned(manifest: Path) -> tuple[list[Path], list[Path]]:
    """Find artifact directories in the registered roots, and the nested repositories skipped.

    A directory below a root that holds its own ``.git`` is another worktree or
    clone, with its own tracked files and uncommitted work, so the walk never
    enters it.
    """
    found: list[Path] = []
    nested: list[Path] = []
    for root in _roots(manifest):
        for dirpath, dirnames, _ in os.walk(root):
            keep: list[str] = []
            for name in sorted(dirnames):
                path = Path(dirpath, name)
                if name == ".git":
                    continue
                if (path / ".git").exists():
                    nested.append(path)
                elif name in ARTIFACT_NAMES:
                    found.append(path)
                else:
                    keep.append(name)
            dirnames[:] = keep
    return found, nested


def artifact_candidates(manifest: Path) -> list[Path]:
    """List directories named like build artifacts inside the registered roots."""
    return _walk_owned(manifest)[0]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(root), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _refusal(path: Path, root: Path) -> str | None:
    """Say why a candidate must stay, or None when it is safe to remove."""
    if path.is_symlink():
        return f"{path}: a symlink"
    if not path.resolve().is_relative_to(root.resolve()):
        return f"{path}: outside {root}"
    if _git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        return f"{path}: {root} is not a git worktree"
    if _git(root, "ls-files", "--", str(path)).stdout.strip():
        return f"{path}: holds tracked files"
    if _git(root, "check-ignore", "-q", str(path)).returncode != 0:
        return f"{path}: not ignored by git"
    return None


def clean(manifest: Path, *, apply: bool) -> dict[str, list[str]]:
    """Remove ignored, untracked artifact directories in the owned roots.

    Without ``apply`` nothing is deleted and ``would_remove`` lists what would be.
    """
    result: dict[str, list[str]] = {"removed": [], "would_remove": [], "refused": []}
    roots = [Path(r) for r in _roots(manifest)]
    candidates, nested = _walk_owned(manifest)
    registered = {str(r) for r in roots}
    for path in nested:
        if str(path.resolve()) not in registered:
            result["refused"].append(f"{path}: a nested repository; register it to clean it")
    for path in candidates:
        owners = [r for r in roots if path.is_relative_to(r)]
        root = max(owners, key=lambda r: len(r.parts))
        reason = _refusal(path, root)
        if reason:
            result["refused"].append(reason)
        elif apply:
            shutil.rmtree(path)
            result["removed"].append(str(path))
        else:
            result["would_remove"].append(str(path))
    return result


def _cmd_check(args: Args) -> int:
    reserves = Reserves(
        args.reserve_disk_gib,
        args.reserve_inodes,
        args.reserve_mem_gib,
        args.cpu_pressure_pct,
        args.mem_pressure_pct,
    )
    snap = snapshot([Path(p) for p in args.path] or [Path.cwd()])
    found = breaches(snap, reserves)
    print(summary_line(snap, found))
    print(
        json.dumps({"breaches": found, "snapshot": snap, "reserves": dataclasses.asdict(reserves)})
    )
    return 1 if found else 0


def _cmd_sample(args: Args) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        msg = "give the command after --, for example: sample -- make test"
        raise ValueError(msg)
    code, report = sample(command, args.interval)
    print(json.dumps(report))
    return code


def _cmd_register(args: Args) -> int:
    register(Path(args.manifest), [Path(r) for r in args.roots])
    print(json.dumps({"roots": _roots(Path(args.manifest))}))
    return 0


def _cmd_clean(args: Args) -> int:
    print(json.dumps(clean(Path(args.manifest), apply=args.apply), indent=2))
    return 0


COMMANDS = {
    "check": _cmd_check,
    "sample": _cmd_sample,
    "register": _cmd_register,
    "clean": _cmd_clean,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="resources.py", description=(__doc__ or "").splitlines()[0]
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    check = sub.add_parser("check", help="compare readings against reserves")
    _ = check.add_argument("--path", action="append", default=[], help="filesystem to check")
    _ = check.add_argument("--reserve-disk-gib", type=float, default=Reserves.disk_gib)
    _ = check.add_argument("--reserve-inodes", type=int, default=Reserves.inodes)
    _ = check.add_argument("--reserve-mem-gib", type=float, default=Reserves.mem_gib)
    _ = check.add_argument("--cpu-pressure-pct", type=float, default=Reserves.cpu_pressure_pct)
    _ = check.add_argument("--mem-pressure-pct", type=float, default=Reserves.mem_pressure_pct)

    sampler = sub.add_parser("sample", help="run a command and report time and peak memory")
    _ = sampler.add_argument("--interval", type=float, default=5.0, help="seconds between polls")
    _ = sampler.add_argument("command", nargs=argparse.REMAINDER)

    registrar = sub.add_parser("register", help="record worktrees this goal owns")
    _ = registrar.add_argument("--manifest", required=True)
    _ = registrar.add_argument("roots", nargs="+")

    cleaner = sub.add_parser("clean", help="remove ignored artifact directories in owned roots")
    _ = cleaner.add_argument("--manifest", required=True)
    _ = cleaner.add_argument("--apply", action="store_true", help="delete; default is a dry run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    args = build_parser().parse_args(argv, namespace=Args())
    try:
        return COMMANDS[args.cmd](args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
