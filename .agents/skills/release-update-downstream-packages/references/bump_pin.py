#!/usr/bin/env python3
"""Replace one package's pinned version in a manifest.

Usage: ``bump_pin.py <manifest> <name> <old> <new>``. Rewrites ``==`` pins
in ``pyproject.toml`` and requirements files, and ``"name": "<old>"`` entries
(with an optional ``^``/``~`` range prefix) in ``package.json``. Prints the
number of pins changed. Exits 1 and leaves the file untouched when no pin
matches; exits 2 on a usage error.
"""

# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import re
import sys
from pathlib import Path

_SEP = re.compile(r"[-_.]+")
_AFTER_VERSION = r"(?![0-9A-Za-z.+_-])"


def pin_pattern(manifest: str, name: str, old: str) -> re.Pattern[str]:
    r"""Build the pattern whose group 1 is everything before the old version.

    >>> p = pin_pattern("pyproject.toml", "Foo.Bar", "0.1.1")
    >>> p.sub(r"\g<1>0.2.0", 'deps = ["foo_bar==0.1.1", "foo-bar[x] == 0.1.10"]')
    'deps = ["foo_bar==0.2.0", "foo-bar[x] == 0.1.10"]'
    >>> p.sub(r"\g<1>0.2.0", "baz-foo-bar==0.1.1")
    'baz-foo-bar==0.1.1'
    >>> q = pin_pattern("package.json", "@s/pkg", "1.0.0")
    >>> q.sub(r"\g<1>2.0.0", '"@s/pkg": "^1.0.0", "@s/pkg-x": "1.0.0"')
    '"@s/pkg": "^2.0.0", "@s/pkg-x": "1.0.0"'
    """
    version = re.escape(old)
    if Path(manifest).name == "package.json":
        return re.compile(
            rf'("{re.escape(name)}"\s*:\s*"[\^~]?){version}(?=")',
        )
    parts = [re.escape(p) for p in _SEP.split(name.strip())]
    joined = "[-_.]+".join(parts)
    extras = r"(?:\[[^\]]*\])?"
    return re.compile(
        rf"(?<![A-Za-z0-9_.-])({joined}{extras}\s*==\s*){version}{_AFTER_VERSION}",
        re.IGNORECASE,
    )


def bump(manifest: Path, name: str, old: str, new: str) -> int:
    """Rewrite matching pins in place and return how many changed."""
    text = manifest.read_text(encoding="utf-8")
    pattern = pin_pattern(manifest.name, name, old)
    updated, count = pattern.subn(lambda m: m.group(1) + new, text)
    if count:
        manifest.write_text(updated, encoding="utf-8")
    return count


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    if len(argv) != 4:  # noqa: PLR2004
        sys.stderr.write(__doc__ or "")
        return 2
    manifest, name, old, new = argv
    count = bump(Path(manifest), name, old, new)
    if not count:
        sys.stderr.write(f"no pin of {name} at {old} in {manifest}; edit it by hand\n")
        return 1
    sys.stdout.write(f"{count} pin(s) changed in {manifest}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
