#!/usr/bin/env python3
"""Measure, lint, and file ``/goal`` prompts for Claude Code and Codex.

``measure`` counts a goal the way each host does. ``catalog`` lists the skills
installed on this machine with their gating. ``lint`` checks a goal against the
host's rules and that catalog.

Run ``goal.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Sequence

HOSTS = ("claude", "codex")
CLAUDE_TARGET = 4000 - 200
"""Claude's drafting target: 200 units under the cap stay free for the user's addendum."""
CAP = 4000
"""Both hosts store at most 4,000 characters: UTF-16 units in Claude Code, code points in Codex."""

SKILL_TOKEN_RE = re.compile(r"(?<![\w/$])([/$])([a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*)\b")
HOME_PATH_RE = re.compile(r"(?<![\w.])(?:/home/|/Users/|/mnt/[a-z]/Users/)[\w.-]+/\S*")
DONE_WHEN_RE = re.compile(r"\b(?:done|finished|met|complete) when\b", re.IGNORECASE)
EVIDENCE_RE = re.compile(r"\b(?:print|prints|printed|show|shows|shown)\b", re.IGNORECASE)
BOUND_RE = re.compile(
    r"\bstop after \d+ (?:turns?|minutes?|hours?)\b|\bwithin \d+ (?:minutes?|hours?)\b",
    re.IGNORECASE,
)
TURN_COUNTER_RE = re.compile(r"\bturn N of (?:\d+|M)\b")
EVIDENCE_WINDOW = 400
"""Characters after a done-when clause searched for the evidence it asks the agent to print."""


@dataclasses.dataclass(frozen=True)
class Skill:
    """One installed skill as a goal can name it."""

    name: str
    gated: bool
    path: str


class Args(argparse.Namespace):
    """Typed view of every CLI option."""

    cmd: str = ""
    host: str = "claude"
    budget: int | None = None
    no_spill: bool = False
    file: str = "-"
    root: list[str] = []  # noqa: RUF012
    catalog_root: list[str] = []  # noqa: RUF012
    ledger_root: str | None = None


def parse_frontmatter(text: str) -> dict[str, str]:
    r"""Read flat ``key: value`` frontmatter, stripping one layer of quotes.

    Examples
    --------
    >>> parse_frontmatter('---\nname: demo\ndescription: "Use when x."\n---\nbody')
    {'name': 'demo', 'description': 'Use when x.'}
    >>> parse_frontmatter("no frontmatter")
    {}
    """
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if not sep or not key or key.startswith((" ", "#")):
            continue
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        meta[key.strip()] = value
    return meta


def strip_frontmatter(text: str) -> str:
    r"""Return the text below a frontmatter block, or the text unchanged.

    Examples
    --------
    >>> strip_frontmatter("---\ntopic: p\n---\n/goal Fix it.\n")
    '/goal Fix it.\n'
    >>> strip_frontmatter("/goal Fix it.")
    '/goal Fix it.'
    """
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    return text if end < 0 else text[end + len("\n---\n") :]


def measure_text(
    text: str, host: str, budget: int | None = None, *, spill: bool = True
) -> dict[str, object]:
    r"""Count a goal as its host counts it and judge it against the host's limits.

    Parameters
    ----------
    text : str
        The goal exactly as it will be pasted.
    host : str
        ``claude`` or ``codex``.
    budget : int | None
        A drafting target that replaces the default; the cap never moves.
    spill : bool
        Codex only: whether the entry point writes an oversized objective to a
        file (the TUI) rather than rejecting it (``codex exec``, the API).

    Returns
    -------
    dict[str, object]
        ``utf16``, ``codepoints``, ``host``, ``target``, ``cap``, and ``verdict``
        (``ok``, ``over-target``, ``over-cap``, or ``spills``).

    Examples
    --------
    >>> measure_text("/goal \N{ROCKET}", "claude")["utf16"]
    8
    >>> measure_text("x" * 4001, "codex")["verdict"]
    'spills'
    """
    if host not in HOSTS:
        msg = f"unknown host {host!r}; use one of {', '.join(HOSTS)}"
        raise ValueError(msg)
    utf16 = len(text.encode("utf-16-le")) // 2
    codepoints = len(text)
    if host == "claude":
        target: int | None = budget or CLAUDE_TARGET
        size = utf16
    else:
        target = budget
        size = codepoints
    if size > CAP:
        verdict = "spills" if host == "codex" and spill else "over-cap"
    elif target is not None and size > target:
        verdict = "over-target"
    else:
        verdict = "ok"
    return {
        "utf16": utf16,
        "codepoints": codepoints,
        "host": host,
        "target": target,
        "cap": CAP,
        "verdict": verdict,
    }


def _version_key(version: str) -> tuple[tuple[int, str], ...]:
    """Order version directory names numerically where they are numbers.

    Examples
    --------
    >>> _version_key("0.10.0") > _version_key("0.9.0")
    True
    """
    return tuple((int(p), "") if p.isdigit() else (-1, p) for p in re.split(r"[.+-]", version))


def default_skill_roots(home: Path | None = None) -> list[Path]:
    """Return the places Claude Code and Codex install skills on this machine."""
    home = home or Path.home()
    return [
        home / ".claude" / "plugins" / "cache",
        home / ".codex" / "plugins" / "cache",
        home / ".claude" / "skills",
        home / ".agents" / "skills",
    ]


def _read_skill(path: Path, plugin: str | None) -> Skill:
    meta = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    name = meta.get("name") or path.parent.name
    gated = meta.get("disable-model-invocation", "").lower() == "true"
    return Skill(f"{plugin}:{name}" if plugin else name, gated, str(path))


def discover_skills(roots: list[Path] | None = None) -> list[Skill]:
    """List installed skills, newest plugin version only, sorted by name.

    A root is read in each layout it holds: a plugin cache
    (``<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md``), a plugin
    checkout (``<plugin>/skills/<skill>/SKILL.md``), or a bare skill directory
    (``<skill>/SKILL.md``).
    """
    newest: dict[tuple[str, str], tuple[tuple[tuple[int, str], ...], Path]] = {}
    found: dict[str, Skill] = {}
    for root in default_skill_roots() if roots is None else roots:
        if not root.is_dir():
            continue
        for path in root.glob("*/*/*/skills/*/SKILL.md"):
            plugin, version = path.parents[3].name, path.parents[2].name
            key = (str(path.parents[4]), plugin)
            best = newest.get(key)
            if best is None or _version_key(version) > best[0]:
                newest[key] = (_version_key(version), path.parents[2])
        for path in root.glob("*/skills/*/SKILL.md"):
            skill = _read_skill(path, path.parents[2].name)
            _ = found.setdefault(skill.name, skill)
        for path in root.glob("*/SKILL.md"):
            skill = _read_skill(path, None)
            _ = found.setdefault(skill.name, skill)
    for (_, plugin), (_, version_dir) in newest.items():
        for path in sorted(version_dir.glob("skills/*/SKILL.md")):
            skill = _read_skill(path, plugin)
            _ = found.setdefault(skill.name, skill)
    return sorted(found.values(), key=lambda s: s.name)


def _issue(rule: str, text: str, start: int, detail: str) -> dict[str, object]:
    return {"rule": rule, "line": text.count("\n", 0, start) + 1, "detail": detail}


def lint_goal(
    text: str, host: str, skills: list[Skill], ledger_root: Path | None = None
) -> dict[str, list[dict[str, object]]]:
    """Check a goal against its host's rules and the installed skill catalog.

    An empty ``skills`` list means no catalog: skill names are then not checked.

    Returns
    -------
    dict[str, list[dict[str, object]]]
        ``errors`` and ``warnings``, each item with ``rule``, ``line``, and ``detail``.
    """
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    measured = measure_text(text, host)
    if measured["verdict"] == "over-cap":
        errors.append(_issue("length", text, 0, f"{measured['utf16']} UTF-16 units; cap {CAP}"))
    elif measured["verdict"] == "over-target":
        detail = f"{measured['utf16']} UTF-16 units; target {measured['target']}"
        warnings.append(_issue("length", text, 0, detail))
    elif measured["verdict"] == "spills":
        detail = "spills to a file in the TUI; use a pointer goal for codex exec or the API"
        warnings.append(_issue("length", text, 0, detail))

    catalog = {s.name: s for s in skills}
    for match in SKILL_TOKEN_RE.finditer(text):
        sigil, name = match.group(1), match.group(2)
        if catalog:
            skill = catalog.get(name)
            if skill is None:
                errors.append(
                    _issue("unknown-skill", text, match.start(), f"{name} is not installed")
                )
            elif skill.gated:
                detail = f"{name} is gated; a goal cannot invoke it"
                errors.append(_issue("gated-skill", text, match.start(), detail))
        if host == "claude" and sigil == "$":
            detail = f"Claude invokes {name} as /{name}"
            errors.append(_issue("host-syntax", text, match.start(), detail))
        elif host == "codex" and sigil == "/":
            detail = f"Codex invokes {name} as ${name}"
            warnings.append(_issue("host-syntax", text, match.start(), detail))

    root = str(ledger_root.resolve()) if ledger_root else None
    for match in HOME_PATH_RE.finditer(text):
        if root and match.group(0).startswith(root):
            continue
        detail = f"{match.group(0)} names one machine's home directory"
        warnings.append(_issue("home-path", text, match.start(), detail))

    if host == "claude":
        done = DONE_WHEN_RE.search(text)
        if done is None:
            detail = "no done-when clause for the evaluator to judge"
            errors.append(_issue("done-when", text, 0, detail))
        elif not EVIDENCE_RE.search(text, done.end(), done.end() + EVIDENCE_WINDOW):
            detail = "the done-when clause asks for no printed evidence"
            warnings.append(_issue("evidence", text, done.start(), detail))
        bound = BOUND_RE.search(text)
        if bound is None:
            detail = "no turn or time bound"
            warnings.append(_issue("bound", text, 0, detail))
        elif not TURN_COUNTER_RE.search(text):
            detail = "the bound fires exactly only when each turn prints `turn N of M`"
            warnings.append(_issue("bound", text, bound.start(), detail))
    return {"errors": errors, "warnings": warnings}


def _read_input(path: str) -> str:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return strip_frontmatter(text)


def _cmd_measure(args: Args) -> int:
    result = measure_text(_read_input(args.file), args.host, args.budget, spill=not args.no_spill)
    print(json.dumps(result))
    return 1 if result["verdict"] == "over-cap" else 0


def _cmd_catalog(args: Args) -> int:
    roots = [Path(r) for r in args.root] or None
    print(json.dumps([dataclasses.asdict(s) for s in discover_skills(roots)], indent=2))
    return 0


def _cmd_lint(args: Args) -> int:
    skills = discover_skills([Path(r) for r in args.catalog_root] or None)
    ledger = Path(args.ledger_root) if args.ledger_root else None
    result = lint_goal(_read_input(args.file), args.host, skills, ledger)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


COMMANDS = {"measure": _cmd_measure, "catalog": _cmd_catalog, "lint": _cmd_lint}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(prog="goal.py", description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    measure = sub.add_parser("measure", help="count a goal as its host counts it")
    _ = measure.add_argument("--host", choices=HOSTS, default="claude")
    _ = measure.add_argument("--budget", type=int, help="drafting target to use instead")
    _ = measure.add_argument(
        "--no-spill", action="store_true", help="Codex entry points that reject oversized goals"
    )
    _ = measure.add_argument("file", nargs="?", default="-")

    catalog = sub.add_parser("catalog", help="list installed skills and their gating")
    _ = catalog.add_argument("--root", action="append", default=[], help="skill root to read")

    lint = sub.add_parser("lint", help="check a goal against its host and the catalog")
    _ = lint.add_argument("--host", choices=HOSTS, default="claude")
    _ = lint.add_argument("--catalog-root", action="append", default=[])
    _ = lint.add_argument("--ledger-root", help="paths under it are not machine-specific")
    _ = lint.add_argument("file", nargs="?", default="-")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    args = build_parser().parse_args(argv, namespace=Args())
    try:
        return COMMANDS[args.cmd](args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
