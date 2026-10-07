#!/usr/bin/env python3
r"""Snapshot SKILL.md targets and diff them without temp paths or prior edits.

Usage:
    skill_diff.py snapshot FILE...
    skill_diff.py diff DIR [--work]
    skill_diff.py clean DIR

``snapshot`` copies each FILE twice (``orig`` and ``work``), prints DIR, then one
``<work copy>TAB<label>`` line per file. ``diff`` prints a unified diff of the
snapshot against the live files, or against the work copies with ``--work``.
Labels are cwd-relative paths (basename outside cwd), never temp paths.
"""

# ruff: noqa: D103
# pyright: reportAny=false, reportUnusedCallResult=false

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import sys
import tempfile
from pathlib import Path

PREFIX = "skill-style."


def label_for(path: Path, cwd: Path) -> str:
    """Return the cwd-relative path, or the basename outside cwd.

    >>> label_for(Path("/a/b/SKILL.md"), Path("/a"))
    'b/SKILL.md'
    >>> label_for(Path("/tmp/x/SKILL.md"), Path("/a"))
    'SKILL.md'
    """
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return path.name


def snapshot(targets: list[Path], cwd: Path) -> tuple[Path, list[tuple[Path, str]]]:
    root = Path(tempfile.mkdtemp(prefix=PREFIX))
    (root / "orig").mkdir()
    (root / "work").mkdir()
    entries: list[dict[str, str]] = []
    out: list[tuple[Path, str]] = []
    for i, target in enumerate(targets):
        src = target.resolve()
        shutil.copyfile(src, root / "orig" / str(i))
        shutil.copyfile(src, root / "work" / str(i))
        label = label_for(src, cwd)
        entries.append({"path": str(src), "label": label})
        out.append((root / "work" / str(i), label))
    (root / "manifest.json").write_text(json.dumps(entries))
    return root, out


def diff(root: Path, *, work: bool) -> str:
    entries = json.loads((root / "manifest.json").read_text())
    chunks: list[str] = []
    for i, entry in enumerate(entries):
        after = root / "work" / str(i) if work else Path(entry["path"])
        before_text = (root / "orig" / str(i)).read_text().splitlines(keepends=True)
        after_text = after.read_text().splitlines(keepends=True)
        chunks.extend(
            difflib.unified_diff(
                before_text,
                after_text,
                fromfile=f"a/{entry['label']}",
                tofile=f"b/{entry['label']}",
            )
        )
    return "".join(chunks)


def clean(root: Path) -> None:
    if not root.name.startswith(PREFIX) or not (root / "manifest.json").is_file():
        msg = f"not a skill-style snapshot: {root}"
        raise SystemExit(msg)
    shutil.rmtree(root)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("files", nargs="+", type=Path)
    p_diff = sub.add_parser("diff")
    p_diff.add_argument("dir", type=Path)
    p_diff.add_argument("--work", action="store_true")
    p_clean = sub.add_parser("clean")
    p_clean.add_argument("dir", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "snapshot":
        missing = [str(f) for f in args.files if not f.is_file()]
        if missing:
            print("not a file: " + ", ".join(missing), file=sys.stderr)
            return 2
        root, out = snapshot(args.files, Path.cwd().resolve())
        print(root)
        for work, label in out:
            print(f"{work}\t{label}")
    elif args.cmd == "diff":
        sys.stdout.write(diff(args.dir, work=args.work))
    else:
        clean(args.dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
