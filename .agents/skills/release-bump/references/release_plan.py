#!/usr/bin/env python3
"""Deterministic release preflight: version order, tags, changelog, leftovers.

Subcommands, each printing one JSON record on stdout:

``compare OLD NEW``   Require NEW to sort after OLD (PEP 440 or SemVer 2.0.0).
``candidates``        List the next-version candidates for ``--current``.
``tags``              Group a repository's tags into namespaces; resolve the tag
                      prefix of ``--version`` and whether the tag for ``--new`` exists.
``unreleased FILE``   Find the unreleased changelog section and say if it is empty.
``leftover``          List tracked and unignored files that still hold ``--old``.

Exit status: 0 verified, 1 refused with a one-line reason on stderr, 2 usage.
Tags are ordered by parsed version, never by ``git tag --sort``, which ranks a
prerelease above its own final unless ``versionsort.suffix`` is set.
"""

# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, final

if TYPE_CHECKING:
    from collections.abc import Sequence

_PEP_TAIL = r"(?:\.post(?P<post>\d+))?(?:\.dev(?P<dev>\d+))?$"
_PEP440 = re.compile(rf"^(?P<release>\d+(?:\.\d+)*)(?:(?P<letter>a|b|rc)(?P<pre>\d+))?{_PEP_TAIL}")
_SEMVER_PRE = r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$"
_SEMVER = re.compile(rf"^(?P<release>\d+\.\d+\.\d+){_SEMVER_PRE}")
_PLAIN = re.compile(r"^\d+(?:\.\d+)*$")
_TAG = re.compile(
    r"^(?P<prefix>.*?)(?P<version>\d+\.\d+(?:\.\d+)*(?:[-.+]?[0-9A-Za-z][0-9A-Za-z.+-]*)?)$"
)
_LETTERS = ("a", "b", "rc")
_LOCKFILES = re.compile(r"(?:\.lock|^package-lock\.json|^npm-shrinkwrap\.json|^pnpm-lock\.yaml)$")
_CHANGELOGS = re.compile(r"^(?:CHANGES|CHANGELOG|HISTORY|NEWS|MIGRATION)(?:\.\w+)?$", re.IGNORECASE)
_UNRELEASED = re.compile(
    r"\bunreleased\b|yet to be released|\bnext release\b|\d\.x\b", re.IGNORECASE
)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
_PLACEHOLDER = re.compile(r"^[_*]Notes on the upcoming release will go here\.?[_*]$", re.IGNORECASE)
_MAX_FILE = 2 * 1024 * 1024
_MAX_LISTED = 100


@final
class Refusal(Exception):  # noqa: N818
    """A precondition failed; the message is the one-line reason."""

    def __init__(self, message: str, record: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.record = record


class Version(NamedTuple):
    """A parsed version; ``scheme`` is ``pep440``, ``semver`` or ``plain``."""

    text: str
    scheme: str
    release: tuple[int, ...]
    letter: str | None
    pre: tuple[str, ...]
    number: int | None
    post: int | None
    dev: int | None

    @property
    def is_pre(self) -> bool:
        """Whether this is a prerelease of its release."""
        return self.letter is not None or bool(self.pre)

    def key(self, scheme: str) -> tuple[Any, ...]:
        """Return the sort key of this version under ``scheme``."""
        release = list(self.release)
        while len(release) > 1 and release[-1] == 0:
            release.pop()
        if scheme == "mixed":
            return (tuple(release), 0 if self.is_pre else 1, self.text)
        if scheme == "semver":
            if not self.pre:
                return (tuple(release), 1, ())
            ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in self.pre)
            return (tuple(release), 0, ids)
        if self.letter is not None:
            pre_key = (_LETTERS.index(self.letter), self.number or 0)
        elif self.post is None and self.dev is not None:
            pre_key = (-1, 0)
        else:
            pre_key = (len(_LETTERS), 0)
        post = -1 if self.post is None else self.post
        dev = 10**9 if self.dev is None else self.dev
        return (tuple(release), pre_key, post, dev)


def parse_version(text: str) -> Version:
    """Parse ``text`` as SemVer, PEP 440 or a plain dotted release, else refuse.

    >>> parse_version("0.1.9a2").letter
    'a'
    >>> parse_version("0.1.0-next.11").pre
    ('next', '11')
    """
    semver = _SEMVER.match(text)
    if semver and semver.group("pre"):
        release = tuple(int(p) for p in semver.group("release").split("."))
        pre = tuple(semver.group("pre").split("."))
        return Version(text, "semver", release, None, pre, None, None, None)
    pep = _PEP440.match(text)
    if pep and (pep.group("letter") or pep.group("post") or pep.group("dev")):
        release = tuple(int(p) for p in pep.group("release").split("."))
        number = pep.group("pre")
        post, dev = pep.group("post"), pep.group("dev")
        return Version(
            text,
            "pep440",
            release,
            pep.group("letter"),
            (),
            int(number) if number is not None else None,
            int(post) if post is not None else None,
            int(dev) if dev is not None else None,
        )
    if _PLAIN.match(text):
        release = tuple(int(p) for p in text.split("."))
        return Version(text, "plain", release, None, (), None, None, None)
    message = f"{text!r} is not a SemVer, PEP 440 or plain dotted version"
    raise Refusal(message)


def shared_scheme(*versions: Version) -> str:
    """Return the one scheme the versions share (plain adopts the other)."""
    schemes = {v.scheme for v in versions if v.scheme != "plain"}
    if len(schemes) > 1:
        message = "versions mix SemVer prerelease and PEP 440 segments: " + ", ".join(
            v.text for v in versions
        )
        raise Refusal(message)
    return next(iter(schemes), "pep440")


def compare(old: str, new: str) -> dict[str, object]:
    """Require ``new`` to sort after ``old``."""
    a, b = parse_version(old), parse_version(new)
    scheme = shared_scheme(a, b)
    ka, kb = a.key(scheme), b.key(scheme)
    if kb <= ka:
        relation = "equal to" if kb == ka else "before"
        message = f"{new} does not sort after {old}: it sorts {relation} it under {scheme}"
        raise Refusal(message)
    return {"old": old, "new": new, "scheme": scheme, "order": "after"}


class TagInfo(NamedTuple):
    """One parsed tag."""

    name: str
    prefix: str
    version: Version


def parse_tags(names: Sequence[str]) -> tuple[list[TagInfo], int]:
    """Split tag names into prefix and version; return them and the skipped count.

    >>> tags, skipped = parse_tags(["v1.0.0", "pkg@0.1.9", "latest"])
    >>> [(t.prefix, t.version.text) for t in tags], skipped
    ([('v', '1.0.0'), ('pkg@', '0.1.9')], 1)
    """
    tags: list[TagInfo] = []
    skipped = 0
    for name in names:
        match = _TAG.match(name)
        if not match:
            skipped += 1
            continue
        try:
            version = parse_version(match.group("version"))
        except Refusal:
            skipped += 1
            continue
        tags.append(TagInfo(name, match.group("prefix"), version))
    return tags, skipped


def namespaces(tags: Sequence[TagInfo]) -> list[dict[str, object]]:
    """Group tags by prefix; the latest tag is the greatest parsed version."""
    grouped: dict[str, list[TagInfo]] = {}
    for tag in tags:
        grouped.setdefault(tag.prefix, []).append(tag)
    result: list[dict[str, object]] = []
    for prefix in sorted(grouped):
        members = grouped[prefix]
        record: dict[str, object] = {"prefix": prefix, "tags": len(members)}
        mixed = False
        try:
            scheme = shared_scheme(*(t.version for t in members))
        except Refusal:
            scheme, mixed = "mixed", True
        latest = max(members, key=lambda t: t.version.key(scheme))
        record.update(
            scheme=scheme,
            mixed=mixed,
            latest=latest.version.text,
            latest_tag=latest.name,
            pre_style=None if mixed else pre_style(members, scheme),
            letters=sorted({t.version.letter for t in members if t.version.letter}),
        )
        result.append(record)
    return result


def pre_style(members: Sequence[TagInfo], scheme: str) -> str | None:
    """Name the prerelease vocabulary of the newest prerelease tag, if any."""
    pres = [t for t in members if t.version.is_pre]
    if not pres:
        return None
    newest = max(pres, key=lambda t: t.version.key(scheme))
    if newest.version.letter is not None:
        return "pep440:a"
    return f"semver:{newest.version.pre[0]}"


def resolve_prefix(
    tags: Sequence[TagInfo], current: str | None
) -> tuple[str | None, str, list[str]]:
    """Pick the tag prefix: that of the current version's tag, else the only namespace."""
    prefixes = sorted({t.prefix for t in tags})
    if current is not None:
        matched = sorted({t.prefix for t in tags if t.version.text == current})
        if len(matched) == 1:
            return matched[0], "current-version", matched
        if len(matched) > 1:
            return None, "ambiguous", matched
    if not prefixes:
        return "v", "default", []
    if len(prefixes) == 1:
        return prefixes[0], "only-namespace", prefixes
    return None, "ambiguous", prefixes


def list_tags(repo: Path) -> list[str]:
    """Return every tag name of ``repo``."""
    out = _git(repo, "tag", "--list")
    return [line for line in out.splitlines() if line]


def _git(repo: Path, *args: str) -> str:
    try:
        run = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo), *args],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=30,
            env=None,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        message = f"git {args[0]} failed: {error}"
        raise Refusal(message) from error
    if run.returncode != 0:
        detail = run.stderr.decode("utf-8", "replace").strip()
        message = f"git {args[0]} failed: {detail}"
        raise Refusal(message)
    return run.stdout.decode("utf-8", "replace")


def tags_command(repo: Path, version: str | None, new: str | None) -> dict[str, object]:
    """Describe tag namespaces, the prefix to use, and whether the new tag exists."""
    names = list_tags(repo)
    tags, skipped = parse_tags(names)
    prefix, basis, candidates_ = resolve_prefix(tags, version)
    record: dict[str, object] = {
        "namespaces": namespaces(tags),
        "skipped": skipped,
        "tag_prefix": prefix,
        "basis": basis,
        "prefixes": candidates_,
    }
    if new is not None:
        parse_version(new)
        if prefix is None:
            record["new_tag"] = None
            record["new_tag_exists"] = None
        else:
            record["new_tag"] = prefix + new
            record["new_tag_exists"] = (prefix + new) in set(names)
    return record


class Candidate(NamedTuple):
    """One next-version option."""

    kind: str
    version: str


def candidates_for(
    current: str, style: str | None, letters: Sequence[str]
) -> tuple[list[Candidate], list[str]]:
    """Enumerate next versions of ``current``; return them and notes on what was skipped."""
    cur = parse_version(current)
    notes: list[str] = []
    if cur.post is not None or cur.dev is not None:
        message = f"{current} carries .post or .dev; supply the next version explicitly"
        raise Refusal(message)
    base = ".".join(str(n) for n in cur.release)
    result: list[Candidate] = []
    if cur.letter is not None:
        number = cur.number or 0
        result.append(Candidate("prerelease", f"{base}{cur.letter}{number + 1}"))
        result.append(Candidate("final", base))
        following = _LETTERS.index(cur.letter) + 1
        if following < len(_LETTERS):
            nxt = _LETTERS[following]
            if nxt in letters:
                result.append(Candidate("promote", f"{base}{nxt}0"))
            else:
                notes.append(f"promotion to {nxt} skipped: the tag history never used it")
        return result, notes
    if cur.pre:
        if not cur.pre[-1].isdigit():
            message = f"{current} has no trailing numeric prerelease identifier"
            raise Refusal(message)
        head = ".".join(cur.pre[:-1])
        bumped = ".".join(filter(None, [head, str(int(cur.pre[-1]) + 1)]))
        result.append(Candidate("prerelease", f"{base}-{bumped}"))
        result.append(Candidate("final", base))
        return result, notes
    if len(cur.release) != 3:  # noqa: PLR2004
        message = f"{current} is not MAJOR.MINOR.PATCH; supply the next version explicitly"
        raise Refusal(message)
    major, minor, patch = cur.release
    patch_v, minor_v = f"{major}.{minor}.{patch + 1}", f"{major}.{minor + 1}.0"
    result += [
        Candidate("patch", patch_v),
        Candidate("minor", minor_v),
        Candidate("major", f"{major + 1}.0.0"),
    ]
    if style is None:
        notes.append("prerelease series skipped: no prerelease vocabulary in the tag history")
    else:
        for target in (patch_v, minor_v):
            result.append(Candidate("prerelease", _series_start(target, style)))
    return result, notes


def _series_start(base: str, style: str) -> str:
    family, _, word = style.partition(":")
    if family == "pep440" and word in _LETTERS:
        return f"{base}{word}0"
    if family == "semver" and re.fullmatch(r"[0-9A-Za-z-]+", word):
        return f"{base}-{word}.0"
    message = f"unknown prerelease style {style!r}; use pep440:a|b|rc or semver:<word>"
    raise Refusal(message)


def candidates_command(
    current: str,
    kind: str | None,
    style: str | None,
    repo: Path | None,
    prefix: str | None,
) -> dict[str, object]:
    """List candidates, reading prerelease vocabulary from the repo's tags when given."""
    letters: list[str] = []
    if repo is not None:
        tags, _ = parse_tags(list_tags(repo))
        chosen = prefix if prefix is not None else resolve_prefix(tags, current)[0]
        members = [t for t in tags if t.prefix == chosen] if chosen is not None else []
        letters = sorted({t.version.letter for t in members if t.version.letter})
        if style is None and members:
            style = pre_style(members, shared_scheme(*(t.version for t in members)))
    found, notes = candidates_for(current, style, letters)
    if kind is not None:
        found = [c for c in found if c.kind == kind]
        if not found:
            message = f"no {kind} candidate for {current}"
            raise Refusal(message)
    return {
        "current": current,
        "candidates": [c._asdict() for c in found],
        "ambiguous": len({c.kind for c in found}) < len(found),
        "notes": notes,
    }


def unreleased_command(path: Path, placeholders: Sequence[str]) -> dict[str, object]:
    """Locate the unreleased section of a Markdown changelog and decide if it is empty."""
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeError) as error:
        message = f"cannot read {path.name}: {error}"
        raise Refusal(message) from error
    headings: list[tuple[int, int, str]] = []
    for number, line in enumerate(lines):
        match = _HEADING.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    found = [h for h in headings if _UNRELEASED.search(h[2])]
    if len(found) != 1:
        message = f"{path.name} has {len(found)} unreleased headings; exactly one is supported"
        raise Refusal(message)
    start, level, text = found[0]
    end = len(lines)
    for number, depth, _ in headings:
        if number > start and depth <= level:
            end = number
            break
    body = "\n".join(lines[start + 1 : end])
    if body.count("<!--") != body.count("-->"):
        message = f"{path.name} has an unterminated comment in the unreleased section"
        raise Refusal(message)
    stripped = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    known = {p.strip().strip("_*").lower() for p in placeholders}
    entries = headings_only = 0
    for raw in stripped.split("\n"):
        line = raw.strip()
        if not line or _PLACEHOLDER.match(line) or line.strip("_*").lower() in known:
            continue
        if _HEADING.match(line):
            headings_only += 1
            continue
        entries += 1
    return {
        "file": path.name,
        "heading": text,
        "heading_line": start + 1,
        "end_line": end,
        "entry_lines": entries,
        "subheadings": headings_only,
        "empty": entries == 0,
    }


def _old_pattern(old: str) -> re.Pattern[str]:
    return re.compile(r"(?<![0-9.])" + re.escape(old) + r"(?![0-9A-Za-z+]|\.[0-9]|-[0-9A-Za-z])")


def leftover_command(repo: Path, old: str) -> dict[str, object]:
    """Find files outside lockfiles and changelogs that still hold ``old``."""
    parse_version(old)
    pattern = _old_pattern(old)
    listing = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    found: list[dict[str, object]] = []
    total = 0
    for name in sorted(filter(None, listing.split("\0"))):
        base = name.rsplit("/", 1)[-1]
        path = repo / name
        if _LOCKFILES.search(base) or _CHANGELOGS.match(base):
            continue
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_FILE:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8000]:
            continue
        for number, line in enumerate(data.decode("utf-8", "replace").split("\n"), 1):
            if pattern.search(line):
                total += 1
                if len(found) < _MAX_LISTED:
                    found.append({"path": name, "line": number})
    record: dict[str, object] = {"old": old, "total": total, "occurrences": found}
    if total:
        message = f"{total} occurrence(s) of {old} remain outside lockfiles and changelogs"
        raise Refusal(message, record)
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("old")
    cmp_.add_argument("new")
    cand = sub.add_parser("candidates")
    cand.add_argument("--current", required=True)
    cand.add_argument(
        "--kind", choices=["patch", "minor", "major", "prerelease", "final", "promote"]
    )
    cand.add_argument("--pre-style")
    cand.add_argument("--repo", type=Path)
    cand.add_argument("--prefix")
    tag = sub.add_parser("tags")
    tag.add_argument("--repo", type=Path, default=Path())
    tag.add_argument("--version")
    tag.add_argument("--new")
    unr = sub.add_parser("unreleased")
    unr.add_argument("file", type=Path)
    unr.add_argument("--placeholder", action="append", default=[])
    left = sub.add_parser("leftover")
    left.add_argument("--repo", type=Path, default=Path())
    left.add_argument("--old", required=True)
    return parser


def _dispatch(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "compare":
        return compare(args.old, args.new)
    if args.command == "candidates":
        return candidates_command(args.current, args.kind, args.pre_style, args.repo, args.prefix)
    if args.command == "tags":
        return tags_command(args.repo, args.version, args.new)
    if args.command == "unreleased":
        return unreleased_command(args.file, args.placeholder)
    return leftover_command(args.repo, args.old)


def main(argv: Sequence[str]) -> int:
    """Run the command line; return the exit status."""
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as exit_error:
        return 2 if exit_error.code else 0
    try:
        record = _dispatch(args)
    except Refusal as refusal:
        if refusal.record is not None:
            sys.stdout.write(json.dumps(refusal.record, sort_keys=True) + "\n")
        sys.stderr.write(f"refused: {refusal}\n")
        return 1
    sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
