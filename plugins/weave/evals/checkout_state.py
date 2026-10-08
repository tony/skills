"""Attest that a no-adoption eval preserved working bytes, staging, and HEAD."""

# ruff: noqa: INP001

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import cast


def git(*args: str) -> bytes:
    """Read repository state from the fixture root."""
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        check=True,
    ).stdout


def state() -> dict[str, object]:
    """Hash tracked and nonignored paths without following terminal symlinks."""
    files = {}
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    for raw in sorted(set(paths.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = Path(name)
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            files[name] = {"missing": True}
            continue
        if stat.S_ISLNK(mode):
            files[name] = {"link": str(path.readlink())}
        elif stat.S_ISREG(mode):
            files[name] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "executable": bool(mode & stat.S_IXUSR),
            }
        else:
            files[name] = {"unsupported_mode": mode}
    return {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
        "index": hashlib.sha256(git("ls-files", "--stage", "-v", "-z")).hexdigest(),
        "files": files,
    }


def main() -> int:
    """Capture the baseline, or emit a success marker only for an exact match."""
    root = Path(".eval-state")
    before = root / "checkout-before.json"
    current = state()
    if sys.argv[1:] == ["capture"]:
        _ = before.write_text(json.dumps(current, indent=2) + "\n")
        return 0
    marker = root / "checkout-preserved.json"
    marker.unlink(missing_ok=True)
    expected = cast("dict[str, object]", json.loads(before.read_text()))
    result = {"unchanged": current == expected, "before": expected, "after": current}
    _ = (root / "checkout-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    if result["unchanged"]:
        _ = marker.write_text(json.dumps({"unchanged": True}) + "\n")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
