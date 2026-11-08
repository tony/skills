#!/usr/bin/env python3
"""Render ``references/apply-template.sh`` into a run directory's ``apply.sh``.

Usage: render_apply.py --run-dir DIR --baseline SHA --trunk-ref REF [--registry PATH]

Computes the registry SHA-256, substitutes the four placeholders, writes
``DIR/apply.sh`` (mode 0755), and prints its path.
"""

import argparse
import hashlib
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "references" / "apply-template.sh"
REGISTRY = TEMPLATE.parent / "signatures.yml"
UNSAFE = frozenset('"$`\\\n')


def render(
    template: str,
    registry_path: str,
    registry_sha256: str,
    baseline_sha: str,
    trunk_ref: str,
) -> str:
    """Substitute the template placeholders.

    Examples
    --------
    >>> render("a __BASELINE_SHA__ b", "r", "h", "abc123", "origin/main")
    'a abc123 b'
    """
    values = {
        "__REGISTRY_PATH__": registry_path,
        "__REGISTRY_SHA256__": registry_sha256,
        "__BASELINE_SHA__": baseline_sha,
        "__TRUNK_REF__": trunk_ref,
    }
    for value in values.values():
        if UNSAFE & set(value):
            msg = f"value cannot be embedded in a double-quoted shell string: {value!r}"
            raise ValueError(msg)
    for key, value in values.items():
        template = template.replace(key, value)
    return template


def main(argv: list[str] | None = None) -> int:
    """Render apply.sh; return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--trunk-ref", required=True)
    args = parser.parse_args(argv)

    registry = args.registry.resolve()
    if not registry.is_file():
        print(f"render_apply: registry not found: {registry}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(registry.read_bytes()).hexdigest()
    try:
        text = render(
            TEMPLATE.read_text(encoding="utf-8"),
            str(registry),
            digest,
            args.baseline,
            args.trunk_ref,
        )
    except ValueError as exc:
        print(f"render_apply: {exc}", file=sys.stderr)
        return 1
    out = args.run_dir / "apply.sh"
    out.write_text(text, encoding="utf-8")
    out.chmod(0o755)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
