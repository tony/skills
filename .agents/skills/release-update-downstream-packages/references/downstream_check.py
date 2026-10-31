#!/usr/bin/env python3
"""Check a release against its package index and a consumer's lockfile.

``index ECOSYSTEM PACKAGE [VERSION]``  Confirm VERSION (default: the latest) is
                                       published and not yanked. ECOSYSTEM is ``pypi``
                                       or ``npm``, the ecosystems ``bump_pin.py`` edits.
``lock LOCKFILE PACKAGE VERSION``      Confirm every locked entry of PACKAGE is VERSION
                                       and resolves from a registry. Reads ``uv.lock``
                                       and ``package-lock.json`` (lockfileVersion 2 or 3).

Each prints one JSON record on stdout. Exit 0 verified, 1 refused with a
one-line reason on stderr, 2 usage.

Endpoints: PyPI JSON API (``/pypi/<project>/<version>/json``,
https://docs.pypi.org/api/json/) and the npm registry (``/<package>/<version>``,
https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md).
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

_BASES = {"pypi": "https://pypi.org", "npm": "https://registry.npmjs.org"}
_TIMEOUT = 20.0
_NAME = re.compile(r"^[A-Za-z0-9@][A-Za-z0-9._/@-]*$")
_UV_SOURCE = re.compile(r'^source = \{ (\w+) = "([^"]*)"', re.MULTILINE)


class Refusal(Exception):  # noqa: N818
    """The check failed; the message is the one-line reason."""


def _mapping(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _items(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def _get(url: str) -> dict[str, object]:
    request = urllib.request.Request(  # noqa: S310
        url, headers={"Accept": "application/json", "User-Agent": "release-downstream-check"}
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = f"{url} answered HTTP {error.code}"
        raise Refusal(message) from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        message = f"{url} could not be read: {error}"
        raise Refusal(message) from error
    if not isinstance(data, dict):
        message = f"{url} did not return a JSON object"
        raise Refusal(message)
    return cast("dict[str, object]", data)


def index_check(
    ecosystem: str, package: str, version: str | None, base: str | None
) -> dict[str, object]:
    """Confirm the release exists on the index and is not yanked."""
    if ecosystem not in _BASES:
        message = f"ecosystem {ecosystem!r} is not supported; use pypi or npm"
        raise Refusal(message)
    if not _NAME.match(package) or (
        version is not None and not re.match(r"^[0-9A-Za-z][0-9A-Za-z.+!_-]*$", version)
    ):
        message = "package or version is not a plain name"
        raise Refusal(message)
    root = (base or _BASES[ecosystem]).rstrip("/")
    if ecosystem == "pypi":
        project = re.sub(r"[-_.]+", "-", package).lower()
        path = f"/pypi/{project}/{version}/json" if version else f"/pypi/{project}/json"
        data = _get(root + path)
        found = str(_mapping(data.get("info")).get("version"))
        files = [_mapping(item) for item in _items(data.get("urls"))]
        if not files:
            message = f"{package} {found} has no uploaded files on the index"
            raise Refusal(message)
        if all(f.get("yanked") for f in files):
            message = f"{package} {found} is yanked on the index"
            raise Refusal(message)
        stamps = sorted(str(f.get("upload_time_iso_8601")) for f in files)
        return {
            "ecosystem": ecosystem,
            "package": package,
            "version": found,
            "yanked": False,
            "uploaded": stamps[0],
            "deprecated": None,
        }
    encoded = urllib.parse.quote(package, safe="@")
    data = _get(f"{root}/{encoded}/{version or 'latest'}")
    deprecated = data.get("deprecated")
    return {
        "ecosystem": ecosystem,
        "package": package,
        "version": str(data.get("version")),
        "yanked": False,
        "uploaded": None,
        "deprecated": str(deprecated) if deprecated else None,
    }


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _uv_entries(text: str, package: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for block in re.split(r"^\[\[package\]\]\s*$", text, flags=re.MULTILINE)[1:]:
        name = re.search(r'^name = "([^"]*)"', block, re.MULTILINE)
        if not name or _normalize(name.group(1)) != _normalize(package):
            continue
        version = re.search(r'^version = "([^"]*)"', block, re.MULTILINE)
        source = _UV_SOURCE.search(block)
        entries.append(
            {
                "version": version.group(1) if version else "",
                "source": source.group(1) if source else "unknown",
            }
        )
    return entries


def _npm_entries(text: str, package: str) -> list[dict[str, str]]:
    packages = _mapping(_mapping(json.loads(text)).get("packages"))
    if not packages:
        message = "package-lock.json has no packages map (lockfileVersion 2 or 3 is required)"
        raise Refusal(message)
    entries: list[dict[str, str]] = []
    for key, raw in packages.items():
        value = _mapping(raw)
        if not (key + "/").endswith("node_modules/" + package + "/"):
            continue
        resolved = str(value.get("resolved", ""))
        registry = (
            resolved.startswith(("https://", "http://"))
            and "/-/" in resolved
            and not value.get("link")
        )
        entries.append(
            {
                "version": str(value.get("version", "")),
                "source": "registry" if registry else "other",
            }
        )
    return entries


def lock_check(lockfile: Path, package: str, version: str) -> dict[str, object]:
    """Confirm every locked entry of ``package`` is ``version`` from a registry."""
    try:
        text = lockfile.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        message = f"cannot read {lockfile.name}: {error}"
        raise Refusal(message) from error
    if lockfile.name == "uv.lock":
        entries = _uv_entries(text, package)
    elif lockfile.name == "package-lock.json":
        try:
            entries = _npm_entries(text, package)
        except ValueError as error:
            message = f"package-lock.json is not valid JSON: {error}"
            raise Refusal(message) from error
    else:
        message = f"{lockfile.name} is not supported; read its diff by hand"
        raise Refusal(message)
    if not entries:
        message = f"{lockfile.name} has no entry for {package}"
        raise Refusal(message)
    bad = [e for e in entries if e["version"] != version or e["source"] != "registry"]
    if bad:
        shown = ", ".join(f"{e['version'] or '?'} from {e['source']}" for e in bad)
        message = f"{lockfile.name} locks {package} at {shown}, not {version} from a registry"
        raise Refusal(message)
    return {
        "lockfile": lockfile.name,
        "package": package,
        "version": version,
        "entries": len(entries),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    idx = sub.add_parser("index")
    idx.add_argument("ecosystem")
    idx.add_argument("package")
    idx.add_argument("version", nargs="?")
    idx.add_argument("--index-url")
    lock = sub.add_parser("lock")
    lock.add_argument("lockfile", type=Path)
    lock.add_argument("package")
    lock.add_argument("version")
    return parser


def main(argv: Sequence[str]) -> int:
    """Run the command line; return the exit status."""
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as exit_error:
        return 2 if exit_error.code else 0
    try:
        if args.command == "index":
            record = index_check(args.ecosystem, args.package, args.version, args.index_url)
        else:
            record = lock_check(args.lockfile, args.package, args.version)
    except Refusal as refusal:
        sys.stderr.write(f"refused: {refusal}\n")
        return 1
    sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
