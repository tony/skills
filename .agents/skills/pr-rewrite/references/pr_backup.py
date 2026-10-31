#!/usr/bin/env python3
"""Back up a PR description, verify the copy, and detect edits since.

``save [PR]`` fetches the PR once, writes ``body.md`` and ``title.txt`` into a
new directory under the git ``pr-backups`` path (a ``mktemp -d`` directory
when that path is unwritable), checks the copy with ``cmp``
against the fetched body, and prints the directory. ``check DIR`` refetches
the PR and exits 1 when its body or title differs from ``DIR/body.md`` or
``DIR/title.txt``. ``verify DIR BODY [TITLE]`` refetches the PR after an edit
and exits 1 unless its body (and title, when given) equals the files, ignoring
CRLF versus LF.
"""

# ruff: noqa: S603, S607, PLR2004
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast


def _run(*args: str) -> str:
    done = subprocess.run(args, capture_output=True, text=True, check=False)
    if done.returncode:
        sys.stderr.write(done.stderr or f"{args[0]} failed\n")
        raise SystemExit(1)
    return done.stdout


def _fetch(pr: str) -> dict[str, object]:
    args = ["gh", "pr", "view", *([pr] if pr else []), "--json", "number,title,body"]
    pr_json: object = json.loads(_run(*args))
    if not isinstance(pr_json, dict):
        sys.stderr.write("gh pr view returned unexpected JSON\n")
        raise SystemExit(1)
    return cast("dict[str, object]", pr_json)


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
    root = Path(_run("git", "rev-parse", "--git-path", "pr-backups").strip()).resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    name = f"{stamp}-pr{pr_json['number']}"
    try:
        out = root / name
        out.mkdir(parents=True)
    except OSError:
        out = Path(tempfile.mkdtemp(prefix=f"pr-backup-{name}."))
    (out / "body.md").write_bytes(body.encode("utf-8"))
    (out / "title.txt").write_bytes(str(pr_json["title"]).encode("utf-8"))
    (out / "number.txt").write_text(str(pr_json["number"]), encoding="utf-8")
    if not _same(out / "body.md", body):
        sys.stderr.write("backup does not match the fetched body\n")
        return 1
    sys.stdout.write(f"{out}\n")
    return 0


def check(directory: str) -> int:
    """Return 1 when the PR body or title differs from the backup."""
    out = Path(directory)
    number = (out / "number.txt").read_text(encoding="utf-8").strip()
    pr_json = _fetch(number)
    if _same(out / "body.md", str(pr_json["body"])) and _same(
        out / "title.txt", str(pr_json["title"])
    ):
        sys.stdout.write("unchanged\n")
        return 0
    sys.stderr.write("the PR body or title changed since the backup\n")
    return 1


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def verify(directory: str, body: str, title: str | None) -> int:
    """Return 1 when the PR does not read back as the edit files."""
    number = (Path(directory) / "number.txt").read_text(encoding="utf-8").strip()
    pr_json = _fetch(number)
    want_body = Path(body).read_text(encoding="utf-8")
    ok = _norm(str(pr_json["body"])) == _norm(want_body)
    if title is not None:
        want_title = Path(title).read_text(encoding="utf-8").rstrip("\n")
        ok = ok and str(pr_json["title"]) == want_title
    if not ok:
        sys.stderr.write("the PR does not read back as the edited text\n")
        return 1
    sys.stdout.write("verified\n")
    return 0


def main(argv: list[str]) -> int:
    """Dispatch ``save`` or ``check``."""
    if argv[:1] == ["save"] and len(argv) <= 2:
        return save(argv[1] if len(argv) == 2 else "")
    if argv[:1] == ["check"] and len(argv) == 2:
        return check(argv[1])
    if argv[:1] == ["verify"] and len(argv) in {3, 4}:
        return verify(argv[1], argv[2], argv[3] if len(argv) == 4 else None)
    sys.stderr.write(
        "usage: pr_backup.py save [PR] | check BACKUP_DIR | verify BACKUP_DIR BODY [TITLE]\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
