#!/usr/bin/env python3
"""Back up a PR description, verify the copy, and detect edits since.

``save [PR]`` fetches the PR once, writes ``body.md`` and ``title.txt`` into a
new directory under the git ``pr-backups`` path, checks the copy with ``cmp``
against the fetched body, and prints the directory. ``check DIR`` refetches
the body and exits 1 when it differs from ``DIR/body.md``.
"""

# ruff: noqa: S603, S607, PLR2004
# pyright: reportUnusedCallResult=false, reportAny=false
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def _run(*args: str) -> str:
    done = subprocess.run(args, capture_output=True, text=True, check=False)
    if done.returncode:
        sys.stderr.write(done.stderr or f"{args[0]} failed\n")
        raise SystemExit(1)
    return done.stdout


def _fetch(pr: str) -> dict[str, object]:
    args = ["gh", "pr", "view", *([pr] if pr else []), "--json", "number,title,body"]
    return json.loads(_run(*args))


def _same(path: Path, text: str) -> bool:
    """Compare a file to text with cmp, byte for byte."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="") as tmp:
        tmp.write(text)
        tmp.flush()
        return subprocess.run(["cmp", "-s", str(path), tmp.name], check=False).returncode == 0


def save(pr: str) -> int:
    """Back up the PR body and title; print the backup directory."""
    pr_json = _fetch(pr)
    body = str(pr_json["body"])
    root = Path(_run("git", "rev-parse", "--git-path", "pr-backups").strip())
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    out = root / f"{stamp}-pr{pr_json['number']}"
    out.mkdir(parents=True)
    (out / "body.md").write_text(body, encoding="utf-8", newline="")
    (out / "title.txt").write_text(str(pr_json["title"]), encoding="utf-8", newline="")
    (out / "number.txt").write_text(str(pr_json["number"]), encoding="utf-8")
    if not _same(out / "body.md", body):
        sys.stderr.write("backup does not match the fetched body\n")
        return 1
    sys.stdout.write(f"{out}\n")
    return 0


def check(directory: str) -> int:
    """Return 1 when the PR body differs from the backup."""
    out = Path(directory)
    number = (out / "number.txt").read_text(encoding="utf-8").strip()
    body = str(_fetch(number)["body"])
    if _same(out / "body.md", body):
        sys.stdout.write("unchanged\n")
        return 0
    sys.stderr.write("the PR body changed since the backup\n")
    return 1


def main(argv: list[str]) -> int:
    """Dispatch ``save`` or ``check``."""
    if argv[:1] == ["save"] and len(argv) <= 2:
        return save(argv[1] if len(argv) == 2 else "")
    if argv[:1] == ["check"] and len(argv) == 2:
        return check(argv[1])
    sys.stderr.write("usage: pr_backup.py save [PR] | check BACKUP_DIR\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
