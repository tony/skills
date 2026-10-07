#!/usr/bin/env python3
r"""Snapshot SKILL.md targets and diff them without temp paths or prior edits.

Usage:
    skill_diff.py snapshot FILE...
    skill_diff.py snapshot --stdin
    skill_diff.py diff DIR [--work]
    skill_diff.py clean DIR

``snapshot`` copies each FILE twice (``orig`` and ``work``), prints DIR, then one
``<work copy>TAB<label>`` line per file. ``diff`` prints a unified diff of the
snapshot against the live files, or against the work copies with ``--work``.
``snapshot --stdin`` snapshots pasted text read from stdin as ``SKILL.md``; use
``diff --work`` on it. Labels are cwd-relative paths (basename outside cwd, widened with the parent
directory when two targets would share one), never temp paths. ``snapshot`` and
``diff`` exit 2 on a missing or non-UTF-8 target.
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


def labels_for(paths: list[Path], cwd: Path) -> list[str]:
    """Return one unique label per path, widening outside-cwd basenames.

    >>> labels_for([Path("/x/a/SKILL.md"), Path("/x/b/SKILL.md")], Path("/c"))
    ['a/SKILL.md', 'b/SKILL.md']
    >>> labels_for([Path("/x/a/SKILL.md"), Path("/y/a/SKILL.md")], Path("/c"))
    ['1:a/SKILL.md', '2:a/SKILL.md']
    """
    labels = [label_for(p, cwd) for p in paths]
    first = list(labels)
    for i, path in enumerate(paths):
        if first.count(first[i]) > 1 and first[i] == path.name:
            labels[i] = f"{path.parent.name}/{path.name}"
    second = list(labels)
    for i, label in enumerate(second):
        if second.count(label) > 1:
            labels[i] = f"{i + 1}:{label}"
    return labels


def snapshot(
    targets: list[Path], cwd: Path, text: str | None = None
) -> tuple[Path, list[tuple[Path, str]]]:
    if text is None:
        for target in targets:
            target.read_bytes().decode("utf-8")
    root = Path(tempfile.mkdtemp(prefix=PREFIX))
    (root / "orig").mkdir()
    (root / "work").mkdir()
    if text is not None:
        (root / "src").mkdir()
        pasted = root / "src" / "SKILL.md"
        pasted.write_text(text, encoding="utf-8")
        targets = [pasted]
    entries: list[dict[str, str]] = []
    out: list[tuple[Path, str]] = []
    resolved = [t.resolve() for t in targets]
    labels = labels_for(resolved, cwd)
    for i, src in enumerate(resolved):
        shutil.copyfile(src, root / "orig" / f"{i}.md")
        shutil.copyfile(src, root / "work" / f"{i}.md")
        label = labels[i]
        entries.append({"path": str(src), "label": label})
        out.append((root / "work" / f"{i}.md", label))
    (root / "manifest.json").write_text(json.dumps(entries), encoding="utf-8")
    return root, out


def diff(root: Path, *, work: bool) -> str:
    entries = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    chunks: list[str] = []
    for i, entry in enumerate(entries):
        after = root / "work" / f"{i}.md" if work else Path(entry["path"])
        if not after.is_file():
            msg = f"target missing: {entry['label']}"
            raise FileNotFoundError(msg)
        before_text = (root / "orig" / f"{i}.md").read_text(encoding="utf-8")
        after_text = after.read_text(encoding="utf-8")
        before_text = before_text.splitlines(keepends=True)
        after_text = after_text.splitlines(keepends=True)
        for line in difflib.unified_diff(
            before_text,
            after_text,
            fromfile=f"a/{entry['label']}",
            tofile=f"b/{entry['label']}",
        ):
            chunks.append(line)
            if not line.endswith("\n"):
                chunks.append("\n\\ No newline at end of file\n")
    return "".join(chunks)


def clean(root: Path) -> None:
    if not root.name.startswith(PREFIX) or not (root / "manifest.json").is_file():
        msg = f"not a skill-style snapshot: {root}"
        raise SystemExit(msg)
    shutil.rmtree(root)


def _is_utf8(path: Path) -> bool:
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _snapshot_cmd(files: list[Path], *, use_stdin: bool) -> int:
    cwd = Path.cwd().resolve()
    if use_stdin:
        root, out = snapshot([], cwd, sys.stdin.read())
    elif not files:
        print("give FILE... or --stdin", file=sys.stderr)
        return 2
    else:
        missing = [str(f) for f in files if not f.is_file()]
        if missing:
            print("not a file: " + ", ".join(missing), file=sys.stderr)
            return 2
        try:
            root, out = snapshot(files, cwd)
        except UnicodeDecodeError:
            bad = ", ".join(str(f) for f in files if not _is_utf8(f))
            print(f"not UTF-8: {bad}", file=sys.stderr)
            return 2
    print(root)
    for work, label in out:
        print(f"{work}\t{label}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("files", nargs="*", type=Path)
    p_snap.add_argument("--stdin", action="store_true")
    p_diff = sub.add_parser("diff")
    p_diff.add_argument("dir", type=Path)
    p_diff.add_argument("--work", action="store_true")
    p_clean = sub.add_parser("clean")
    p_clean.add_argument("dir", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "snapshot":
        return _snapshot_cmd(args.files, use_stdin=args.stdin)
    if args.cmd == "diff":
        try:
            sys.stdout.write(diff(args.dir, work=args.work))
        except FileNotFoundError as err:
            print(err, file=sys.stderr)
            return 2
        except UnicodeDecodeError:
            print("target is not UTF-8", file=sys.stderr)
            return 2
    else:
        clean(args.dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
