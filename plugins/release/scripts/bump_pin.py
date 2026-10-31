#!/usr/bin/env python3
"""Replace one package's pinned version inside dependency declarations.

Usage: ``bump_pin.py <manifest> <name> <old> <new>``. Supported manifests:

``pyproject.toml``   Strings in ``project.dependencies``, ``project.optional-dependencies``,
                     ``dependency-groups``, ``build-system.requires`` and the ``tool.uv``
                     dependency arrays. Only exact ``==`` pins change.
``*.txt``, ``*.in``  Requirements lines outside comments and option lines.
``package.json``     The string value of ``name`` inside ``dependencies``,
                     ``devDependencies``, ``peerDependencies`` and ``optionalDependencies``
                     (an optional ``^`` or ``~`` prefix is kept).

Comments, tool settings, scripts and every other byte stay as they were. A
manifest the scanner cannot read unambiguously (multi-line strings in a
dependency array, duplicate JSON keys, unknown syntax) is refused, not guessed.
The edited TOML is parsed and must differ from the original only in the
changed pins.

Prints the number of pins changed. Exits 1 without writing when no pin
matches, 2 on a usage error, 3 on a refusal or an access, decode or write
failure. The edit goes through a same-directory temporary file and a rename
after the original is re-read unchanged; extended attributes and ACLs are not
carried over. Parent-directory aliases and writers that win the final
check-to-rename window are not guarded.
"""

# ruff: noqa: EM101, TRY003, PLR2004
import contextlib
import json
import os
import re
import stat
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast, final

if TYPE_CHECKING:
    from collections.abc import Iterator

_SEP = re.compile(r"[-_.]+")
_AFTER_VERSION = r"(?![0-9A-Za-z.+_-])"
_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+!_-]*$")
_JSON_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_TOML_ARRAYS = (
    ("project", "dependencies"),
    ("build-system", "requires"),
    ("tool", "uv", "dev-dependencies"),
    ("tool", "uv", "constraint-dependencies"),
    ("tool", "uv", "override-dependencies"),
)
_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


class AmbiguousError(ValueError):
    """The manifest cannot be edited without guessing."""


def pin_pattern(name: str, old: str) -> re.Pattern[str]:
    r"""Build the pattern whose group 1 is everything before the old version.

    >>> p = pin_pattern("Foo.Bar", "0.1.1")
    >>> p.sub(r"\g<1>0.2.0", 'deps = ["foo_bar==0.1.1", "foo-bar[x] == 0.1.10"]')
    'deps = ["foo_bar==0.2.0", "foo-bar[x] == 0.1.10"]'
    >>> p.sub(r"\g<1>0.2.0", "baz-foo-bar==0.1.1")
    'baz-foo-bar==0.1.1'
    """
    parts = [re.escape(p) for p in _SEP.split(name.strip())]
    joined = "[-_.]+".join(parts)
    extras = r"(?:\[[^\]]*\])?"
    return re.compile(
        rf"(?<![A-Za-z0-9_.-])({joined}{extras}\s*==\s*){re.escape(old)}{_AFTER_VERSION}",
        re.IGNORECASE,
    )


@final
class _Toml:
    """Locate the string spans of dependency arrays in a TOML document."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.spans: list[tuple[int, int]] = []

    def fail(self, why: str) -> AmbiguousError:
        line = self.text.count("\n", 0, self.pos) + 1
        return AmbiguousError(f"{why} at line {line}")

    def skip(self, *, newlines: bool) -> None:
        text, n = self.text, len(self.text)
        while self.pos < n:
            c = text[self.pos]
            if c in " \t\r" or (newlines and c == "\n"):
                self.pos += 1
            elif c == "#":
                while self.pos < n and text[self.pos] != "\n":
                    self.pos += 1
            else:
                return

    def string(self, *, multiline_ok: bool = True) -> tuple[int, int]:
        text = self.text
        quote = text[self.pos]
        n = len(text)
        if text.startswith(quote * 3, self.pos):
            if not multiline_ok:
                raise self.fail("multi-line string in a dependency array")
            i = self.pos + 3
            while i < n:
                if quote == '"' and text[i] == "\\":
                    i += 2
                elif text.startswith(quote * 3, i):
                    start = self.pos + 3
                    while text.startswith(quote, i + 3):
                        i += 1
                    self.pos = i + 3
                    return start, i
                else:
                    i += 1
            raise self.fail("unterminated string")
        start = self.pos + 1
        i = start
        while i < n and text[i] not in (quote, "\n"):
            i += 2 if quote == '"' and text[i] == "\\" else 1
        if i >= n or text[i] != quote:
            raise self.fail("unterminated string")
        self.pos = i + 1
        return start, i

    def key(self) -> tuple[str, ...]:
        parts: list[str] = []
        while True:
            self.skip(newlines=False)
            c = self.text[self.pos : self.pos + 1]
            if c in ('"', "'"):
                start, end = self.string()
                parts.append(self.text[start:end])
            else:
                m = _BARE_KEY.match(self.text, self.pos)
                if not m:
                    raise self.fail("unreadable key")
                parts.append(m.group())
                self.pos = m.end()
            self.skip(newlines=False)
            if self.text[self.pos : self.pos + 1] != ".":
                return tuple(parts)
            self.pos += 1

    def is_dependency(self, path: tuple[str, ...]) -> bool:
        if path in _TOML_ARRAYS:
            return True
        if len(path) == 3 and path[:2] == ("project", "optional-dependencies"):
            return True
        return len(path) == 2 and path[0] == "dependency-groups"

    def value(self, path: tuple[str, ...]) -> None:
        self.skip(newlines=False)
        c = self.text[self.pos : self.pos + 1]
        if c in ('"', "'"):
            self.string()
        elif c == "[":
            self.array(path)
        elif c == "{":
            self.table(path)
        else:
            m = re.compile(r"[^,\]}\n#]+").match(self.text, self.pos)
            if not m or not m.group().strip():
                raise self.fail("missing value")
            self.pos = m.end()

    def array(self, path: tuple[str, ...]) -> None:
        collect = self.is_dependency(path)
        self.pos += 1
        while True:
            self.skip(newlines=True)
            c = self.text[self.pos : self.pos + 1]
            if c == "]":
                self.pos += 1
                return
            if c == "":
                raise self.fail("unterminated array")
            if c in ('"', "'"):
                span = self.string(multiline_ok=not collect)
                if collect:
                    self.spans.append(span)
            elif c == "[":
                if collect:
                    raise self.fail("nested array in a dependency array")
                self.array(path)
            else:
                self.value(path)
            self.skip(newlines=True)
            if self.text[self.pos : self.pos + 1] == ",":
                self.pos += 1
            elif self.text[self.pos : self.pos + 1] != "]":
                raise self.fail("unreadable array")

    def table(self, path: tuple[str, ...]) -> None:
        self.pos += 1
        while True:
            self.skip(newlines=False)
            c = self.text[self.pos : self.pos + 1]
            if c == "}":
                self.pos += 1
                return
            sub = path + self.key()
            self.skip(newlines=False)
            if self.text[self.pos : self.pos + 1] != "=":
                raise self.fail("expected =")
            self.pos += 1
            self.value(sub)
            self.skip(newlines=False)
            if self.text[self.pos : self.pos + 1] == ",":
                self.pos += 1
            elif self.text[self.pos : self.pos + 1] != "}":
                raise self.fail("unreadable inline table")

    def scan(self) -> list[tuple[int, int]]:
        table: tuple[str, ...] = ()
        n = len(self.text)
        while True:
            self.skip(newlines=True)
            if self.pos >= n:
                return self.spans
            if self.text[self.pos] == "[":
                double = self.text.startswith("[[", self.pos)
                self.pos += 2 if double else 1
                table = self.key()
                closer = "]]" if double else "]"
                if not self.text.startswith(closer, self.pos):
                    raise self.fail("unreadable table header")
                self.pos += len(closer)
            else:
                sub = table + self.key()
                self.skip(newlines=False)
                if self.text[self.pos : self.pos + 1] != "=":
                    raise self.fail("expected =")
                self.pos += 1
                self.value(sub)
            self.skip(newlines=False)
            if self.pos < n and self.text[self.pos] != "\n":
                raise self.fail("unexpected text after value")


def _json_spans(text: str, name: str, old: str) -> list[tuple[int, int]]:
    """Return the spans of ``old`` inside dependency-section values for ``name``."""

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        if len({k for k, _ in pairs}) != len(pairs):
            message = "duplicate JSON key"
            raise AmbiguousError(message)
        return dict(pairs)

    try:
        document = json.loads(text, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as error:
        message = f"invalid JSON: {error}"
        raise AmbiguousError(message) from error
    if not isinstance(document, dict):
        message = "package.json is not an object"
        raise AmbiguousError(message)
    decoder = json.JSONDecoder()
    blank = re.compile(r"\s*")

    def skip(i: int) -> int:
        found = blank.match(text, i)
        return found.end() if found else i

    def members(i: int) -> Iterator[tuple[str, int, int, object]]:
        i = skip(i + 1)
        while text[i] != "}":
            raw_key, i = decoder.raw_decode(text, i)
            i = skip(skip(i) + 1)
            value, end = decoder.raw_decode(text, i)
            yield cast("str", raw_key), i, end, value
            i = skip(end)
            if text[i] == ",":
                i = skip(i + 1)

    spans: list[tuple[int, int]] = []
    for key, start, _end, value in members(skip(0)):
        if key not in _JSON_SECTIONS or not isinstance(value, dict):
            continue
        for member, begin, end, version in members(start):
            m = (
                re.fullmatch(r"([\^~]?)" + re.escape(old), version)
                if isinstance(version, str)
                else None
            )
            if member == name and m and "\\" not in text[begin:end]:
                spans.append((begin + 1 + len(m.group(1)), end - 1))
    return spans


def _requirement_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    offset = 0
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped and not stripped.startswith(("#", "-")):
            comment = re.search(r"(^|\s)#", line)
            spans.append((offset, offset + (comment.start() if comment else len(line))))
        offset += len(line) + 1
    return spans


def _toml_diff(a: object, b: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict) and isinstance(b, dict):
        left, right = cast("dict[str, object]", a), cast("dict[str, object]", b)
        if left.keys() != right.keys():
            return [path]
        return [d for k in left for d in _toml_diff(left[k], right[k], (*path, k))]
    if isinstance(a, list) and isinstance(b, list):
        first, second = cast("list[object]", a), cast("list[object]", b)
        if len(first) != len(second):
            return [path]
        pairs = enumerate(zip(first, second, strict=True))
        return [d for i, (x, y) in pairs for d in _toml_diff(x, y, (*path, i))]
    return [] if a == b else [path]


def _verify_toml(before: str, after: str, count: int) -> None:
    try:
        changed = _toml_diff(tomllib.loads(before), tomllib.loads(after))
    except ValueError as error:
        message = f"the TOML does not parse: {error}"
        raise AmbiguousError(message) from error
    if len(changed) != count:
        message = "the edit changed values beyond the pins"
        raise AmbiguousError(message)


def _spans_for(manifest: Path, text: str, name: str, old: str) -> list[tuple[int, int]]:
    if manifest.name == "package.json":
        return _json_spans(text, name, old)
    if manifest.name == "pyproject.toml":
        return _Toml(text).scan()
    if manifest.suffix in (".txt", ".in"):
        return _requirement_spans(text)
    message = (
        f"unsupported manifest {manifest.name}; only pyproject.toml, requirements *.txt/*.in "
        "and package.json are edited"
    )
    raise AmbiguousError(message)


def _refuse_hashed(text: str, pattern: re.Pattern[str]) -> None:
    for line in re.sub(r"\\\r?\n", " ", text).split("\n"):
        if line.lstrip().startswith(("#", "-")):
            continue
        if "--hash" in line and pattern.search(line):
            message = (
                "the pin carries --hash digests that a version change would invalidate; "
                "regenerate the file with its compile tool"
            )
            raise AmbiguousError(message)


def edit(manifest: Path, text: str, name: str, old: str, new: str) -> tuple[str, int]:
    """Return the edited text and the number of pins changed."""
    spans = _spans_for(manifest, text, name, old)
    if manifest.name == "package.json":
        updated = text
        for start, end in reversed(spans):
            updated = updated[:start] + new + updated[end:]
        return updated, len(spans)
    pattern = pin_pattern(name, old)
    if manifest.suffix in (".txt", ".in"):
        _refuse_hashed(text, pattern)
    updated = text
    count = 0
    for start, end in reversed(spans):
        piece, n = pattern.subn(lambda m: m.group(1) + new, updated[start:end])
        updated = updated[:start] + piece + updated[end:]
        count += n
    if count and manifest.name == "pyproject.toml":
        _verify_toml(text, updated, count)
    return updated, count


def _write_atomic(manifest: Path, before: os.stat_result, original: bytes, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(dir=manifest.parent, prefix=".bump_pin.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).chmod(stat.S_IMODE(before.st_mode))
        now = manifest.lstat()
        if (now.st_ino, now.st_size, now.st_mtime_ns) != (
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) or manifest.read_bytes() != original:
            message = f"{manifest} changed while the edit was prepared; nothing was written"
            raise OSError(message)  # noqa: TRY301
        Path(temporary).replace(manifest)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(temporary).unlink()
        raise


def bump(manifest: Path, name: str, old: str, new: str) -> int:
    """Rewrite matching dependency pins and return how many changed."""
    metadata = manifest.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        message = f"{manifest} is not a regular file with exactly one link"
        raise AmbiguousError(message)
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        message = f"a rewrite of {manifest} would change its owner"
        raise AmbiguousError(message)
    original = manifest.read_bytes()
    updated, count = edit(manifest, original.decode("utf-8"), name, old, new)
    if count:
        _write_atomic(manifest, metadata, original, updated.encode("utf-8"))
    return count


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    if len(argv) != 4:
        sys.stderr.write(__doc__ or "")
        return 2
    manifest, name, old, new = argv
    if not (_VERSION.match(old) and _VERSION.match(new)):
        sys.stderr.write("old and new must be plain version strings\n")
        return 2
    try:
        count = bump(Path(manifest), name, old, new)
    except AmbiguousError as error:
        sys.stderr.write(f"pin update refused for {manifest}: {error}\nNothing was written.\n")
        return 3
    except (OSError, UnicodeError) as error:
        sys.stderr.write(f"pin update failed for {manifest}: {error}\n")
        sys.stderr.write(
            "Stop and inspect the file; a failed write may have changed its content.\n"
        )
        return 3
    if not count:
        sys.stderr.write(f"no dependency pin of {name} at {old} in {manifest}; edit it by hand\n")
        return 1
    sys.stdout.write(f"{count} pin(s) changed in {manifest}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
