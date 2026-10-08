#!/usr/bin/env python3
r"""Run the slop registry's regex signatures over files, a diff, or commit messages.

Usage:
  slop_detect.py files    --registry PATH [--override PATH] [--added-base SHA] [PATH ...]
  slop_detect.py diff     --registry PATH [--override PATH] [--historical]
  slop_detect.py messages --registry PATH [--override PATH] [--historical]
  slop_detect.py present  --findings FILE [--rev REV] [--out FILE]

Every scanning mode takes ``--out FILE``: the JSON goes to the file and stdout
gets a count per tier and signature. ``present`` drops the diff findings whose
text is gone from its file at REV (default HEAD); text and path reach ``git grep``
as argv elements, never through a shell.

``files`` reads NUL-separated paths from stdin when none are given
(``git ls-files -z``). ``diff`` reads a unified diff or ``git log -p`` output
from stdin. ``messages`` reads ``git log -z --format=%H%x1f%B`` output.

Prints one JSON object: ``loaded`` counts and ``findings``. Exits 2 on a
registry or override error. Only ``kind: regex`` signatures run.

Feed ``diff`` with ``git -c core.quotepath=off log -p``: git otherwise quotes
non-ASCII paths and the file name is lost.

A signature with ``demote-if-conventions`` drops one tier when that regex matches
the project's conventions files (``AGENTS.md``, ``CLAUDE.md``, ``CONTRIBUTING.md``,
``.github/CONTRIBUTING.md`` under the current directory).

A pattern that starts with ``^\\+`` judges added lines only. In ``files`` mode a
line counts as added when ``git diff BASE HEAD`` added it; without
``--added-base`` no line does. A match on a pre-existing line is marked
``pre_existing`` and demoted one tier (A to B, B to C).
"""

# ruff: noqa: ANN401, PLR2004
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, final

Sig = dict[str, Any]

HEX_ESCAPE = re.compile(r"\\x\{([0-9A-Fa-f]+)\}")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class RegistryError(Exception):
    """Registry or override file is malformed."""


def _scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw[:1] in {"'", '"'} and (len(raw) < 2 or raw[-1] != raw[0]):
        msg = f"unterminated quoted scalar: {raw!r}"
        raise RegistryError(msg)
    if raw[:1] in {"&", "*", "!", "{", "|", ">", "%", "@", "`"}:
        msg = (
            f"unsupported YAML syntax (anchor, alias, tag, flow mapping, or block scalar): {raw!r}"
        )
        raise RegistryError(msg)
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1].replace("''", "'")
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return json.loads(raw)
    if raw in {"true", "false"}:
        return raw == "true"
    return raw


def _flow_list(raw: str) -> list[Any]:
    if not raw.strip().endswith("]"):
        msg = f"flow lists must close on the same line: {raw!r}"
        raise RegistryError(msg)
    inner = raw.strip()[1:-1]
    items: list[str] = []
    buf = ""
    quote = ""
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf += ch
            if ch == quote:
                if quote == "'" and inner[i + 1 : i + 2] == "'":
                    buf += "'"
                    i += 1
                else:
                    quote = ""
        elif ch in "'\"":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
        i += 1
    if buf.strip():
        items.append(buf)
    return [_scalar(item) for item in items]


def _value(raw: str) -> Any:
    raw = raw.strip()
    return _flow_list(raw) if raw.startswith("[") else _scalar(raw)


def _check_line(line: str, indent: int) -> None:
    """Reject line shapes the subset parser would otherwise misplace."""
    stripped = line.strip()
    name, colon, rest = stripped.partition(":")
    if "\t" in line[:indent] or stripped in {"---", "..."}:
        msg = f"unsupported YAML syntax (tab indent or document marker): {line!r}"
        raise RegistryError(msg)
    if stripped.startswith("- "):
        return
    if not colon or name.startswith("<<") or (indent > 0 and not rest.strip()):
        msg = f"unsupported line (nested mapping, merge key, or stray text): {line!r}"
        raise RegistryError(msg)


def _block_scalar(lines: list[str], start: int, indent: int) -> tuple[str, int]:
    """Join the lines indented deeper than ``indent``; return the text and next index."""
    block: list[str] = []
    i = start
    while i < len(lines) and (
        not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent
    ):
        block.append(lines[i].strip())
        i += 1
    return " ".join(b for b in block if b), i


def parse_yaml(text: str) -> dict[str, Any]:
    r"""Parse the registry subset of YAML: top-level scalars and lists of mappings.

    Examples
    --------
    >>> parse_yaml("version: 1\nsignatures:\n  - id: a.b\n    tier: A\n")["signatures"]
    [{'id': 'a.b', 'tier': 'A'}]
    >>> parse_yaml("delete:\n  - a.b\n")
    {'delete': ['a.b']}

    Anchors, aliases, tags, flow mappings, multi-line flow lists, tab
    indentation, document markers, nested mappings, and lines the subset
    cannot place raise ``RegistryError``.
    """
    lines = text.splitlines()
    out: dict[str, Any] = {}
    key: str | None = None
    item: Any = None
    item_indent = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        _check_line(line, indent)
        if indent == 0:
            name, _, rest = stripped.partition(":")
            if rest.strip():
                out[name] = _value(rest)
                key = None
            else:
                out[name] = []
                key = name
            item = None
            continue
        if key is None:
            msg = f"unexpected indented line: {line!r}"
            raise RegistryError(msg)
        if stripped.startswith("- "):
            body = stripped[2:]
            if ":" in body and not body.startswith(("'", '"')):
                name, _, rest = body.partition(":")
                if not rest.strip():
                    msg = f"nested mappings are unsupported: {line!r}"
                    raise RegistryError(msg)
                item = {name.strip(): _value(rest)}
                item_indent = indent + 2
                out[key].append(item)
            else:
                item = None
                out[key].append(_scalar(body))
            continue
        if not isinstance(item, dict) or indent < item_indent:
            msg = f"unexpected line under {key}: {line!r}"
            raise RegistryError(msg)
        name, _, rest = stripped.partition(":")
        if rest.strip() in {"|", ">"}:
            item[name], i = _block_scalar(lines, i, indent)
        else:
            item[name] = _value(rest)
    return out


def load_registry(registry: Path, override: Path | None = None) -> tuple[list[Sig], dict[str, int]]:
    r"""Load built-in signatures and apply ``replace`` / ``append`` / ``delete``.

    Examples
    --------
    >>> import tempfile, pathlib
    >>> d = pathlib.Path(tempfile.mkdtemp())
    >>> _ = (d / "r.yml").write_text("signatures:\n  - id: a.b\n    tier: A\n")
    >>> load_registry(d / "r.yml")[1]["builtin"]
    1
    """
    sigs = parse_yaml(registry.read_text(encoding="utf-8")).get("signatures", [])
    counts = {"builtin": len(sigs), "replaced": 0, "appended": 0, "deleted": 0}
    if override is None or not override.is_file():
        return sigs, counts
    data = parse_yaml(override.read_text(encoding="utf-8"))
    unknown = set(data) - {"version", "replace", "append", "delete"}
    if unknown:
        msg = f"{override}: unknown top-level keys {sorted(unknown)}"
        raise RegistryError(msg)
    seen: set[str] = set()
    for section in ("replace", "append", "delete"):
        for entry in data.get(section, []):
            sid = entry["id"] if isinstance(entry, dict) else entry
            if sid in seen:
                msg = f"{override}: id {sid!r} appears under more than one key or twice"
                raise RegistryError(msg)
            seen.add(sid)
    by_id = {s["id"]: s for s in sigs}
    for entry in data.get("replace", []):
        if entry["id"] not in by_id:
            msg = f"{override}: replace names unknown id {entry['id']!r}"
            raise RegistryError(msg)
        by_id[entry["id"]].update(entry)
        counts["replaced"] += 1
    for entry in data.get("append", []):
        if entry["id"] in by_id:
            msg = f"{override}: append id {entry['id']!r} already exists"
            raise RegistryError(msg)
        sigs.append(entry)
        by_id[entry["id"]] = entry
        counts["appended"] += 1
    for sid in data.get("delete", []):
        if sid not in by_id:
            msg = f"{override}: delete names unknown id {sid!r}"
            raise RegistryError(msg)
        sigs = [s for s in sigs if s["id"] != sid]
        counts["deleted"] += 1
    return sigs, counts


CONVENTION_FILES = ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", ".github/CONTRIBUTING.md")


def conventions_text() -> str:
    """Concatenate the conventions files present under the current directory."""
    parts: list[str] = []
    for name in CONVENTION_FILES:
        try:
            parts.append(Path(name).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return "\n".join(parts)


def demote_by_conventions(rules: list[Rule], findings: list[dict[str, Any]]) -> None:
    """Demote findings one tier when the conventions text matches ``demote-if-conventions``."""
    text = conventions_text()
    ids = {
        r.sig["id"]
        for r in rules
        if r.sig.get("demote-if-conventions")
        and re.search(str(r.sig["demote-if-conventions"]), text)
    }
    for f in findings:
        if f["signature_id"] in ids and f["tier"] in {"A", "B"}:
            f.setdefault("registry_tier", f["tier"])
            f["tier"] = {"A": "B", "B": "C"}[f["tier"]]
            f["demoted_by"] = "conventions"


def compile_pattern(pattern: str) -> re.Pattern[str]:
    r"""Compile a registry pattern with Python's ``re``.

    ``\x{H}`` becomes a literal code point escape.

    Examples
    --------
    >>> bool(compile_pattern(r"[\x{1F300}-\x{1FAFF}]").search("ship \U0001f680"))
    True
    """
    translated = HEX_ESCAPE.sub(lambda m: f"\\U{int(m.group(1), 16):08x}", pattern)
    return re.compile(translated)


@final
class Rule:
    """A regex signature ready to match lines."""

    def __init__(self, sig: Sig) -> None:
        self.sig = sig
        pattern = str(sig["pattern"])
        self.added_only = pattern.startswith("^\\+")
        self.skipped = pattern.startswith("^-")
        if self.added_only:
            pattern = "^" + pattern[3:]
        self.regex = compile_pattern(pattern)
        self.targets: list[str] = list(sig.get("target", []))
        self.skip_paths = [re.compile(p, re.IGNORECASE) for p in sig.get("skip-paths", [])]

    def path_skipped(self, path: str) -> bool:
        """Whether a ``skip-paths`` regex matches the path."""
        return any(rx.search(path) for rx in self.skip_paths)


def build_rules(sigs: list[Sig]) -> list[Rule]:
    """Rules for every regex signature that matches lines of present content."""
    rules = [Rule(s) for s in sigs if s.get("kind") == "regex" and s.get("pattern")]
    return [r for r in rules if not r.skipped]


def _finding(
    rule: Rule, line: str, *, pre_existing: bool = False, historical: bool = False, **where: Any
) -> dict[str, Any]:
    sig = rule.sig
    tier = str(sig["tier"])
    if pre_existing:
        tier = {"A": "B", "B": "C"}.get(tier, tier)
    guard = str(sig.get("fp-guard", ""))
    out: dict[str, Any] = {
        **where,
        "signature_id": sig["id"],
        "tier": tier,
        "action": sig.get("action"),
        "confidence": "regex",
        "text": line.strip()[:200],
    }
    if pre_existing:
        out["pre_existing"] = True
    if tier != sig["tier"]:
        out["registry_tier"] = sig["tier"]
    if historical:
        out["historical_only"] = True
    if guard and not guard.startswith("None"):
        out["fp_guard"] = guard
    return out


def added_lines(base: str) -> dict[str, set[int]]:
    """Map each path to the line numbers ``git diff BASE HEAD`` added."""
    proc = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "git",
            "-c",
            "core.quotepath=off",
            "diff",
            "-U0",
            "--no-color",
            "--no-renames",
            base,
            "HEAD",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    result: dict[str, set[int]] = {}
    path = ""
    for line in proc.stdout.splitlines():
        if line.startswith("+++ "):
            path = line[6:].rstrip("\t") if line.startswith("+++ b/") else ""
            continue
        m = HUNK.match(line)
        if m and path:
            start = int(m.group(1))
            count = int(m.group(2)) if m.group(2) is not None else 1
            result.setdefault(path, set()).update(range(start, start + count))
    return result


def scan_files(
    rules: list[Rule], paths: list[str], added: dict[str, set[int]] | None
) -> list[dict[str, Any]]:
    """Match every ``file`` / ``diff`` rule against each line of each file."""
    found: list[dict[str, Any]] = []
    for path in paths:
        if Path(path).is_symlink():
            continue
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new = (added or {}).get(path, set())
        for number, line in enumerate(text.splitlines(), start=1):
            for rule in rules:
                if not ({"file", "diff"} & set(rule.targets)) or rule.path_skipped(path):
                    continue
                if rule.regex.search(line):
                    found.append(
                        _finding(
                            rule,
                            line,
                            pre_existing=rule.added_only and number not in new,
                            file=path,
                            line_start=number,
                        )
                    )
    return found


def scan_diff(rules: list[Rule], text: str, *, historical: bool) -> list[dict[str, Any]]:
    """Match every ``diff`` rule against the added lines of a diff or ``log -p``."""
    found: list[dict[str, Any]] = []
    commit = ""
    path = ""
    number = 0
    in_hunk = False
    for line in text.splitlines():
        if in_hunk and line[:1] in ("+", "-", " ", "\\"):
            if line[0] == "+":
                for rule in rules:
                    if "diff" not in rule.targets or rule.path_skipped(path):
                        continue
                    if rule.regex.search(line[1:]):
                        where: dict[str, Any] = {"file": path, "line_start": number}
                        if commit:
                            where["commit_sha"] = commit
                        found.append(_finding(rule, line[1:], historical=historical, **where))
            if line[0] in ("+", " "):
                number += 1
            continue
        in_hunk = False
        if line.startswith("commit "):
            commit = line.split()[1]
        elif line.startswith("+++ "):
            path = line[6:].rstrip("\t") if line.startswith("+++ b/") else ""
        elif (m := HUNK.match(line)) is not None:
            number = int(m.group(1))
            in_hunk = True
    return found


def scan_messages(rules: list[Rule], text: str, *, historical: bool) -> list[dict[str, Any]]:
    """Match message-subject and message-body rules against each commit message."""
    found: list[dict[str, Any]] = []
    for record in text.split("\0"):
        sha, sep, message = record.strip("\n").partition("\x1f")
        if not sep:
            continue
        for number, line in enumerate(message.splitlines(), start=1):
            kind = "message-subject" if number == 1 else "message-body"
            found.extend(
                _finding(rule, line, historical=historical, commit_sha=sha, line_start=number)
                for rule in rules
                if kind in rule.targets and rule.regex.search(line)
            )
    return found


def emit(doc: dict[str, Any], out: Path | None) -> None:
    """Print the JSON, or write it to ``out`` and print per-signature counts."""
    if out is None:
        json.dump(doc, sys.stdout)
        sys.stdout.write("\n")
        return
    out.write_text(json.dumps(doc), encoding="utf-8")
    counts: dict[str, int] = {}
    for f in doc["findings"]:
        key = f"{f['tier']} {f['signature_id']}"
        counts[key] = counts.get(key, 0) + 1
    print(f"findings: {len(doc['findings'])} (full JSON in the --out file)")
    for key, n in sorted(counts.items()):
        print(f"{n:6d}  {key}")


def still_present(finding: dict[str, Any], rev: str) -> bool:
    """Whether a diff finding's text is still in its file at ``rev``.

    Text and path travel as argv elements, never through a shell.
    """
    if "file" not in finding or "text" not in finding:
        return True
    proc = subprocess.run(  # noqa: S603
        ["git", "grep", "-F", "-q", "-e", str(finding["text"]), rev, "--", str(finding["file"])],  # noqa: S607
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def run_present(findings_file: Path | None, rev: str, out: Path | None) -> int:
    """Drop findings whose text a later commit removed; print the rest as JSON."""
    if findings_file is None:
        print("detect: present needs --findings", file=sys.stderr)
        return 2
    try:
        doc = json.loads(findings_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"detect: {exc}", file=sys.stderr)
        return 2
    doc["findings"] = [f for f in doc.get("findings", []) if still_present(f, rev)]
    emit(doc, out)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the requested mode; return the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["files", "diff", "messages", "present"])
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--override", type=Path)
    parser.add_argument("--added-base")
    parser.add_argument("--historical", action="store_true")
    parser.add_argument("--out", type=Path, help="write the JSON here and print a summary")
    parser.add_argument("--findings", type=Path, help="present: detector JSON to filter")
    parser.add_argument("--rev", default="HEAD", help="present: revision to search")
    args = parser.parse_intermixed_args(argv)

    if args.mode == "present":
        return run_present(args.findings, args.rev, args.out)

    if args.registry is None:
        print("detect: --registry is required", file=sys.stderr)
        return 2
    try:
        sigs, counts = load_registry(args.registry, args.override)
        rules = build_rules(sigs)
    except (RegistryError, re.error, KeyError, OSError) as exc:
        print(f"detect: {exc}", file=sys.stderr)
        return 2

    if args.mode == "files":
        paths = args.paths or [p for p in sys.stdin.read().split("\0") if p]
        added = added_lines(args.added_base) if args.added_base else None
        findings = scan_files(rules, paths, added)
    elif args.mode == "diff":
        findings = scan_diff(rules, sys.stdin.read(), historical=args.historical)
    else:
        findings = scan_messages(rules, sys.stdin.read(), historical=args.historical)

    demote_by_conventions(rules, findings)
    emit({"loaded": {**counts, "active": len(sigs)}, "findings": findings}, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
