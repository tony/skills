#!/usr/bin/env python3
"""Measure, lint, and file ``/goal`` prompts for Claude Code and Codex.

``measure`` counts a goal the way each host does. ``catalog`` lists the skills
installed on this machine with their gating. ``lint`` checks a goal against the
host's rules and that catalog. ``ledger`` resolves the Documents root and saves
or lists numbered goals and objectives. ``find`` gathers earlier goals from the
ledger, Codex's goal database and spill files, and a prompt-history export.
``harvest`` counts the sentences retyped across goal prompts in that export.

Run ``goal.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sqlite3
import sys
import typing as t
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

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

KINDS = {"goal": "goals", "objective": "objectives"}
STATUSES = ("draft", "set", "achieved", "superseded")
TOPIC_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SAVE_ATTEMPTS = 5
WINDOWS_USERS = Path("/mnt/c/Users")
SERVICE_PROFILES = frozenset(
    {"All Users", "Default", "Default User", "Public", "WDAGUtilityAccount", "defaultuser0"}
)
GOAL_REQUEST_RE = re.compile(
    r"\b(?:print|draft|write|make|reword|synthesi[sz]e)\b.{0,40}\b(?:goals?|/goal)\b",
    re.IGNORECASE | re.DOTALL,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
MIN_SENTENCE = 50
"""Shorter fragments recur by accident; a retyped guardrail is a full sentence."""
POINTER_RE = re.compile(r"^Read the Codex goal objective file at (.+) before continuing\.$")
"""Codex's TUI stores this pointer in place of an objective it spilled to a file."""


@dataclasses.dataclass(frozen=True)
class Skill:
    """One installed skill as a goal can name it."""

    name: str
    gated: bool
    path: str


class RootError(ValueError):
    """Several Windows profiles could hold the Documents root and none is this user's."""

    def __init__(self, candidates: list[str]) -> None:
        self.candidates: list[str] = candidates
        names = ", ".join(candidates)
        super().__init__(f"Documents folders under several Windows users ({names}); pass --root")


class Args(argparse.Namespace):
    """Typed view of every CLI option."""

    cmd: str = ""
    ledger_cmd: str = ""
    host: str = "claude"
    budget: int | None = None
    no_spill: bool = False
    file: str = "-"
    skill_roots: list[str] = []  # noqa: RUF012
    catalog_root: list[str] = []  # noqa: RUF012
    ledger_root: str | None = None
    root: str | None = None
    topic: str | None = None
    kind: str = "goal"
    status: str = "draft"
    objective: str | None = None
    parent: str | None = None
    day: str | None = None
    text: str | None = None
    codex_home: str | None = None
    history: str | None = None
    limit: int = 20
    min_count: int = 5
    min_projects: int = 2
    days: int = 30
    today: str | None = None


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


def default_profile(env: Mapping[str, str]) -> Path:
    """Return where this machine's goal-planner profile lives."""
    home = Path(env.get("HOME") or Path.home())
    config = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    return config / "goal-planner" / "profile.md"


def resolve_root(
    flag: str | None,
    env: Mapping[str, str],
    profile: Path | None,
    mnt: Path = WINDOWS_USERS,
) -> tuple[Path, str]:
    """Resolve the Documents root and say where it came from.

    Precedence: the flag, ``GOAL_PLANNER_ROOT``, the profile's ``documents:``
    (``auto`` skips it), the Windows Documents folder on WSL, then
    ``~/Documents``. On WSL a Windows profile matching ``$USER`` or named in
    ``$PATH`` wins; a tie raises ``RootError``.
    """
    if flag:
        return Path(flag).expanduser(), "flag"
    if env.get("GOAL_PLANNER_ROOT"):
        return Path(env["GOAL_PLANNER_ROOT"]).expanduser(), "env"
    if profile is not None and profile.is_file():
        documents = parse_frontmatter(profile.read_text(encoding="utf-8")).get("documents", "")
        if documents and documents != "auto":
            path = Path(documents).expanduser()
            return (path if path.is_absolute() else profile.parent / path), "profile"
    if mnt.is_dir():
        users = sorted(
            p.name
            for p in mnt.iterdir()
            if p.name not in SERVICE_PROFILES and (p / "Documents").is_dir()
        )
        user = env.get("USER", "").lower()
        chosen = [u for u in users if u.lower() == user] or [
            u for u in users if f"{mnt}/{u}/" in env.get("PATH", "")
        ]
        if len(users) == 1:
            chosen = users
        if len(chosen) == 1:
            return mnt / chosen[0] / "Documents", "wsl"
        if users:
            raise RootError(users)
    return Path(env.get("HOME") or Path.home()) / "Documents", "home"


def next_number(root: Path, topic: str, kind: str) -> int:
    """Return one past the highest number this topic and kind has in any dated folder."""
    pattern = re.compile(rf"^{re.escape(topic)}-(\d{{3,}})\.md$")
    best = 0
    for path in root.glob(f"*/{KINDS[kind]}/{topic}-*.md"):
        match = pattern.match(path.name)
        if match and DATE_DIR_RE.match(path.parent.parent.name):
            best = max(best, int(match.group(1)))
    return best + 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _local_today() -> date:
    return datetime.now(timezone.utc).astimezone().date()


def save_entry(  # noqa: PLR0913, PLR0917
    root: Path, topic: str, kind: str, body: str, meta: dict[str, str], day: date
) -> Path:
    """Write the next numbered goal or objective; never overwrite an existing file.

    The file is frontmatter followed by ``body`` exactly. A number another
    session took first moves the save to the next one.
    """
    if not TOPIC_RE.match(topic):
        msg = f"topic {topic!r} must be a kebab-case slug such as parser-fix"
        raise ValueError(msg)
    if kind not in KINDS:
        msg = f"kind {kind!r} must be one of {', '.join(KINDS)}"
        raise ValueError(msg)
    status = meta.get("status", "draft")
    if status not in STATUSES:
        msg = f"status {status!r} must be one of {', '.join(STATUSES)}"
        raise ValueError(msg)
    host = meta.get("host", "")
    measured = measure_text(body, host if host in HOSTS else "claude")
    folder = root / day.isoformat() / KINDS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    number = next_number(root, topic, kind)
    for _ in range(SAVE_ATTEMPTS):
        fields = [("topic", topic), ("kind", kind), ("number", str(number))]
        fields += [("host", host), ("status", status)]
        fields += [(k, meta[k]) for k in ("objective", "parent") if meta.get(k)]
        fields += [("utf16", str(measured["utf16"])), ("codepoints", str(measured["codepoints"]))]
        fields.append(("created", _utc_now()))
        head = "---\n" + "".join(f"{key}: {value}\n" for key, value in fields) + "---\n"
        path = folder / f"{topic}-{number:03d}.md"
        try:
            with path.open("x", encoding="utf-8", newline="") as handle:
                _ = handle.write(head + body)
        except FileExistsError:
            number += 1
            continue
        return path
    msg = f"no free number for {topic} after {SAVE_ATTEMPTS} attempts"
    raise ValueError(msg)


def list_entries(root: Path, topic: str | None) -> list[dict[str, object]]:
    """List saved goals and objectives, by topic, kind, then number."""
    entries: list[dict[str, object]] = []
    for kind, folder in KINDS.items():
        for path in root.glob(f"*/{folder}/*.md"):
            name, _, number = path.stem.rpartition("-")
            if not number.isdigit() or not DATE_DIR_RE.match(path.parent.parent.name):
                continue
            if topic and name != topic:
                continue
            meta = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            entries.append(
                {
                    "topic": name,
                    "kind": kind,
                    "number": int(number),
                    "date": path.parent.parent.name,
                    "path": str(path),
                    "status": meta.get("status", ""),
                    "host": meta.get("host", ""),
                    "objective": meta.get("objective", ""),
                    "created": meta.get("created", ""),
                }
            )
    entries.sort(key=lambda e: (str(e["topic"]), str(e["kind"]), t.cast("int", e["number"])))
    return entries


def _iso_from_ms(value: object) -> str:
    if not isinstance(value, int):
        return ""
    return datetime.fromtimestamp(value / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _codex_hits(codex_home: Path) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    database = codex_home / "goals_1.sqlite"
    if database.is_file():
        con = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
        try:
            query = "select thread_id, objective, status, updated_at_ms from thread_goals"
            rows = t.cast("list[tuple[str, str, str, object]]", con.execute(query).fetchall())
        finally:
            con.close()
        for thread_id, objective, status, updated in rows:
            pointer = POINTER_RE.match(objective)
            spilled = Path(pointer.group(1)) if pointer else None
            missing = spilled is not None and not spilled.is_file()
            text = spilled.read_text(encoding="utf-8") if spilled and not missing else objective
            hits.append(
                {
                    "source": "codex-db",
                    "when": _iso_from_ms(updated),
                    "ref": thread_id,
                    "text": text,
                    "missing": missing,
                    "status": status,
                }
            )
    for path in sorted((codex_home / "attachments").glob("*/goal-objective.md")):
        stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        hits.append(
            {
                "source": "codex-attachment",
                "when": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ref": str(path),
                "text": path.read_text(encoding="utf-8"),
                "missing": False,
            }
        )
    return hits


def _history_hits(history: Path) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for line in history.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        record = t.cast("dict[str, object]", json.loads(line))
        text = str(record.get("text", ""))
        if record.get("kind") == "prompt" and text.lstrip().startswith("/goal "):
            hits.append(
                {
                    "source": "history",
                    "when": str(record.get("timestamp") or ""),
                    "ref": str(record.get("session_id") or record.get("path") or ""),
                    "text": text,
                    "missing": False,
                    "agent": str(record.get("agent", "")),
                }
            )
    return hits


def find_goals(
    root: Path | None,
    codex_home: Path | None,
    history: Path | None,
    text: str | None,
    topic: str | None,
) -> list[dict[str, object]]:
    """Gather earlier goals, newest first, each with its verbatim text and source.

    A Codex pointer objective is replaced by the file it names; when that file
    is gone the hit keeps the pointer and sets ``missing``. ``topic`` narrows
    ledger hits only; ``text`` matches every source, ignoring case.
    """
    hits: list[dict[str, object]] = []
    if root is not None and root.is_dir():
        for entry in list_entries(root, topic):
            path = Path(str(entry["path"]))
            hits.append(
                {
                    "source": "ledger",
                    "when": str(entry["created"] or entry["date"]),
                    "ref": str(path),
                    "text": strip_frontmatter(path.read_text(encoding="utf-8")),
                    "missing": False,
                    "kind": entry["kind"],
                }
            )
    if codex_home is not None:
        hits.extend(_codex_hits(codex_home))
    if history is not None and history.is_file():
        hits.extend(_history_hits(history))
    if text:
        needle = text.lower()
        hits = [h for h in hits if needle in str(h["text"]).lower()]
    hits.sort(key=lambda h: str(h["when"]), reverse=True)
    return hits


def harvest(
    history: Path,
    *,
    min_count: int = 5,
    min_projects: int = 2,
    days: int = 30,
    today: date | None = None,
) -> list[dict[str, object]]:
    """Count sentences retyped across goal prompts, keeping those that clear the bar.

    A sentence counts once per prompt. It is kept when it appears in at least
    ``min_count`` prompts from at least ``min_projects`` working directories,
    the latest within ``days`` of ``today``. Codex records carry no working
    directory, so a Codex-only sentence never clears the project bar.
    """
    counts: dict[str, int] = {}
    projects: dict[str, set[str]] = {}
    hosts: dict[str, set[str]] = {}
    last: dict[str, str] = {}
    for line in history.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        record = t.cast("dict[str, object]", json.loads(line))
        text = str(record.get("text", "")).strip()
        if record.get("kind") != "prompt":
            continue
        if not (text.startswith("/goal") or GOAL_REQUEST_RE.search(text)):
            continue
        origin = t.cast("dict[str, object]", record.get("origin") or {})
        where = str(origin.get("cwd") or "")
        day = str(record.get("timestamp") or "")[:10]
        body = text[len("/goal") :].strip() if text.startswith("/goal") else text
        parts = {
            part.strip().lower()
            for part in SENTENCE_SPLIT_RE.split(body)
            if len(part.strip()) >= MIN_SENTENCE
        }
        for sentence in parts:
            counts[sentence] = counts.get(sentence, 0) + 1
            if where:
                projects.setdefault(sentence, set()).add(where)
            hosts.setdefault(sentence, set()).add(str(record.get("agent", "")))
            last[sentence] = max(last.get(sentence, ""), day)
    since = ((today or _local_today()) - timedelta(days=days)).isoformat()
    kept: list[dict[str, object]] = [
        {
            "sentence": sentence,
            "count": count,
            "projects": len(projects.get(sentence, set())),
            "last_seen": last[sentence],
            "hosts": sorted(hosts[sentence]),
            "skills": sorted({m.group(2) for m in SKILL_TOKEN_RE.finditer(sentence)}),
        }
        for sentence, count in counts.items()
        if count >= min_count
        and len(projects.get(sentence, set())) >= min_projects
        and last[sentence] >= since
    ]
    kept.sort(key=lambda row: (-t.cast("int", row["count"]), str(row["sentence"])))
    return kept


def _ledger_root(args: Args) -> Path:
    env = dict(os.environ)
    return resolve_root(args.root, env, default_profile(env))[0]


def _read_input(path: str) -> str:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return strip_frontmatter(text)


def _cmd_measure(args: Args) -> int:
    result = measure_text(_read_input(args.file), args.host, args.budget, spill=not args.no_spill)
    print(json.dumps(result))
    return 1 if result["verdict"] == "over-cap" else 0


def _cmd_catalog(args: Args) -> int:
    roots = [Path(r) for r in args.skill_roots] or None
    print(json.dumps([dataclasses.asdict(s) for s in discover_skills(roots)], indent=2))
    return 0


def _cmd_lint(args: Args) -> int:
    skills = discover_skills([Path(r) for r in args.catalog_root] or None)
    ledger = Path(args.ledger_root) if args.ledger_root else None
    result = lint_goal(_read_input(args.file), args.host, skills, ledger)
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


def _cmd_ledger(args: Args) -> int:
    if args.ledger_cmd == "root":
        env = dict(os.environ)
        path, source = resolve_root(args.root, env, default_profile(env))
        print(json.dumps({"root": str(path), "source": source}))
        return 0
    root = _ledger_root(args)
    if args.ledger_cmd == "next":
        topic = args.topic or ""
        number = next_number(root, topic, args.kind)
        today = _local_today().isoformat()
        path = root / today / KINDS[args.kind] / f"{topic}-{number:03d}.md"
        print(json.dumps({"number": number, "path": str(path)}))
        return 0
    if args.ledger_cmd == "save":
        meta = {"host": args.host, "status": args.status}
        meta.update(
            {k: v for k, v in (("objective", args.objective), ("parent", args.parent)) if v}
        )
        day = date.fromisoformat(args.day) if args.day else _local_today()
        body = _read_input(args.file)
        path = save_entry(root, args.topic or "", args.kind, body, meta, day)
        number = int(path.stem.rpartition("-")[2])
        measured = measure_text(body, args.host)
        print(json.dumps({"path": str(path), "number": number, **measured}))
        return 0
    print(json.dumps(list_entries(root, args.topic), indent=2))
    return 0


def _cmd_find(args: Args) -> int:
    env = dict(os.environ)
    try:
        root: Path | None = resolve_root(args.root, env, default_profile(env))[0]
    except RootError as exc:
        print(f"warning: ledger skipped: {exc}", file=sys.stderr)
        root = None
    codex_default = Path(env.get("CODEX_HOME") or Path.home() / ".codex")
    codex_home = Path(args.codex_home) if args.codex_home else codex_default
    history = Path(args.history) if args.history else None
    hits = find_goals(root, codex_home, history, args.text, args.topic)[: args.limit]
    print(json.dumps(hits, indent=2))
    return 0


def _cmd_harvest(args: Args) -> int:
    today = date.fromisoformat(args.today) if args.today else None
    found = harvest(
        Path(args.history or ""),
        min_count=args.min_count,
        min_projects=args.min_projects,
        days=args.days,
        today=today,
    )
    print(json.dumps(found, indent=2))
    return 0


COMMANDS = {
    "harvest": _cmd_harvest,
    "measure": _cmd_measure,
    "catalog": _cmd_catalog,
    "lint": _cmd_lint,
    "ledger": _cmd_ledger,
    "find": _cmd_find,
}


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
    _ = catalog.add_argument(
        "--root", dest="skill_roots", action="append", default=[], help="skill root to read"
    )

    lint = sub.add_parser("lint", help="check a goal against its host and the catalog")
    _ = lint.add_argument("--host", choices=HOSTS, default="claude")
    _ = lint.add_argument("--catalog-root", action="append", default=[])
    _ = lint.add_argument("--ledger-root", help="paths under it are not machine-specific")
    _ = lint.add_argument("file", nargs="?", default="-")

    ledger = sub.add_parser("ledger", help="resolve the Documents root; save or list goals")
    ledger_sub = ledger.add_subparsers(dest="ledger_cmd", required=True)
    for name, text in (
        ("root", "print the resolved Documents root and its source"),
        ("next", "print the next number and path for a topic"),
        ("save", "save a goal or objective under the next number"),
        ("list", "list saved goals and objectives"),
    ):
        action = ledger_sub.add_parser(name, help=text)
        _ = action.add_argument("--root", help="Documents root; overrides every other source")
        if name in {"next", "save", "list"}:
            _ = action.add_argument("--topic", required=name != "list")
        if name in {"next", "save"}:
            _ = action.add_argument("--kind", choices=tuple(KINDS), default="goal")
        if name == "save":
            _ = action.add_argument("--host", choices=HOSTS, default="claude")
            _ = action.add_argument("--status", choices=STATUSES, default="draft")
            _ = action.add_argument("--objective", help="objective path relative to the root")
            _ = action.add_argument("--parent", help="parent goal path relative to the root")
            _ = action.add_argument("--date", dest="day", help="YYYY-MM-DD; default today")
            _ = action.add_argument("file", nargs="?", default="-")

    find = sub.add_parser("find", help="gather earlier goals from every source")
    _ = find.add_argument("--root", help="Documents root")
    _ = find.add_argument("--text", help="keep hits containing this text")
    _ = find.add_argument("--topic", help="keep ledger hits for this topic")
    _ = find.add_argument("--codex-home", help="default $CODEX_HOME or ~/.codex")
    _ = find.add_argument("--history", help="agentgrep NDJSON export of prompt history")
    _ = find.add_argument("--limit", type=int, default=20)

    harvester = sub.add_parser("harvest", help="count guardrail sentences retyped into goals")
    _ = harvester.add_argument("--history", required=True, help="agentgrep NDJSON export")
    _ = harvester.add_argument("--min-count", type=int, default=5)
    _ = harvester.add_argument("--min-projects", type=int, default=2)
    _ = harvester.add_argument("--days", type=int, default=30)
    _ = harvester.add_argument("--today", help="YYYY-MM-DD; default today")
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
