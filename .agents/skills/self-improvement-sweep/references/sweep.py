#!/usr/bin/env python3
"""Deterministic counting and the findings ledger for the sweep and apply skills.

``counts`` turns a prompt-history file (and optionally a log of skill-tool
launches) into per-skill invocation counts, an era split, and project spread;
``--window`` adds a windowed numerator and denominator for a finding's ratio.
``catalog`` lists the skills with their rename map, birth dates, and era
boundary from git history. ``ledger-save`` writes the findings ledger outside
the working tree and ``ledger-verify`` recomputes its key before any edit.
``tree-check`` reports uncommitted changes that would mix with a catalog edit.
``autosquash`` folds ``fixup!`` commits into their targets without an editor.

Run ``sweep.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import typing as t
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

SLASH_RE = re.compile(r"^/([a-z0-9-]+(?::[a-z0-9-]+)?)")
TOOL_RE = re.compile(r"Launching skill: ([a-z0-9-]+(?::[a-z0-9-]+)?)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LEDGER_VERSION = 1
MIN_RATIO_INVOCATIONS = 10
VERDICTS = ("absent", "not-binding")


class Args(argparse.Namespace):
    """Typed view of every CLI option."""

    cmd: str = ""
    history: str = ""
    boundary: str = ""
    tool_log: str | None = None
    catalog: str | None = None
    alias: list[str] = []  # noqa: RUF012
    findings: str = ""
    resweep_on: str = ""
    resweep_days: int = 30
    names_out: str | None = None
    ignore: list[str] = []  # noqa: RUF012
    out: str | None = None
    onto: str = ""
    ledger: str | None = None
    tool_unavailable: bool = False
    root: str = "."
    catalog_glob: str = "plugins/*/skills/*/SKILL.md"
    window: list[str] = []  # noqa: RUF012


class Row(t.NamedTuple):
    """One slash-channel invocation."""

    day: str
    skill: str
    project: str
    text: str = ""


class Prompt(t.NamedTuple):
    """One prompt-history record."""

    day: str
    text: str
    project: str


def parse_history(
    lines: Iterable[str], bare: Iterable[str] = ()
) -> tuple[list[Row], list[Prompt], int, int]:
    """Extract slash invocations and every prompt from prompt-history JSONL.

    A prompt counts as an invocation only when ``display`` starts with
    ``/plugin:skill``, so a prompt that merely mentions one does not. A bare
    ``/skill`` counts only when its name is in ``bare`` (the catalog), so
    built-in commands such as ``/clear`` stay out.

    Parameters
    ----------
    lines : Iterable[str]
        One JSON object per line, with ``display``, ``timestamp`` (epoch
        milliseconds), and ``project``.
    bare : Iterable[str]
        Catalog names that may appear without a plugin prefix.

    Returns
    -------
    tuple[list[Row], list[Prompt], int, int]
        Invocation rows, all prompts, records read, and malformed lines skipped.

    Examples
    --------
    >>> rows, prompts, records, bad = parse_history([
    ...     '{"display": "the `spike-probe` skill x", "timestamp": 1700000000000, "project": "/a"}',
    ...     '{"display": "see the `spike-probe` skill", "timestamp": 1700000000000}',
    ...     '{"display": "/clear", "timestamp": 1700000000000}',
    ...     '{"display": "/tidy now", "timestamp": 1700000000000}',
    ...     "not json",
    ... ], bare=["tidy"])
    >>> [(r.skill, r.text) for r in rows]
    [('spike:probe', 'the `spike-probe` skill x'), ('tidy', '/tidy now')]
    >>> (len(prompts), records, bad)
    (4, 4, 1)
    """
    known = set(bare)
    rows: list[Row] = []
    prompts: list[Prompt] = []
    records = 0
    malformed = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            loaded = t.cast("object", json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(loaded, dict):
            malformed += 1
            continue
        rec = t.cast("dict[str, object]", loaded)
        records += 1
        display = rec.get("display")
        if not isinstance(display, str):
            continue
        stamp = rec.get("timestamp")
        day = ""
        if isinstance(stamp, (int, float)):
            day = datetime.fromtimestamp(stamp / 1000, tz=UTC).date().isoformat()
        project = rec.get("project")
        proj = project if isinstance(project, str) else ""
        prompts.append(Prompt(day, display, proj))
        match = SLASH_RE.match(display)
        if match is None or (":" not in match.group(1) and match.group(1) not in known):
            continue
        rows.append(Row(day, match.group(1), proj, display))
    return rows, prompts, records, malformed


def parse_tool_log(lines: Iterable[str]) -> list[str]:
    """Return one skill name per ``Launching skill:`` occurrence.

    Examples
    --------
    >>> parse_tool_log(["x Launching skill: a:b y", "Launching skill: a:b", "none"])
    ['a:b', 'a:b']
    """
    return [m.group(1) for line in lines for m in TOOL_RE.finditer(line)]


def parse_aliases(pairs: Sequence[str]) -> dict[str, str]:
    """Map old skill names to current ones from ``old=new`` strings.

    Examples
    --------
    >>> parse_aliases(["a:old=a:new"])
    {'a:old': 'a:new'}
    """
    out: dict[str, str] = {}
    for pair in pairs:
        old, sep, new = pair.partition("=")
        if not sep or not old or not new:
            msg = f"alias must be old=new: {pair!r}"
            raise ValueError(msg)
        out[old] = new
    return out


def summarize(
    rows: Sequence[Row],
    tool_names: Sequence[str],
    boundary: str,
    aliases: dict[str, str],
    catalog: Iterable[str] = (),
) -> dict[str, object]:
    """Count invocations per skill, all-time and since the era boundary.

    The era split and project spread come from the slash channel only; the
    tool channel carries no date. Aliases sum renamed skills into one row.
    An empty ``boundary`` means no era: the ``*_era`` fields and ``rank_era``
    are omitted.

    Examples
    --------
    >>> rows = [
    ...     Row("2026-01-01", "a:old", "/p"),
    ...     Row("2026-03-01", "a:new", "/q"),
    ...     Row("2026-03-02", "a:new", "/q"),
    ... ]
    >>> out = summarize(rows, ["a:new"], "2026-02-01", {"a:old": "a:new"}, ["b:idle"])
    >>> out["skills"]["a:new"]
    {'slash_all': 3, 'slash_era': 2, 'tool_all': 1, 'all_time': 4, 'projects_all': 2, 'projects_era': 1}
    >>> out["skills"]["b:idle"]["all_time"]
    0
    >>> out["rank_all"]
    ['a:new', 'b:idle']
    >>> flat = summarize(rows, [], "", {"a:old": "a:new"})
    >>> flat["skills"]["a:new"]
    {'slash_all': 3, 'tool_all': 0, 'all_time': 3, 'projects_all': 2}
    >>> (flat["rank_all"], flat["rank_era"])
    (['a:new'], [])
    """  # noqa: E501
    slash_all: Counter[str] = Counter()
    slash_era: Counter[str] = Counter()
    tool_all: Counter[str] = Counter()
    proj_all: defaultdict[str, set[str]] = defaultdict(set)
    proj_era: defaultdict[str, set[str]] = defaultdict(set)
    for row in rows:
        name = aliases.get(row.skill, row.skill)
        slash_all[name] += 1
        if row.project:
            proj_all[name].add(row.project)
        if boundary and row.day and row.day >= boundary:
            slash_era[name] += 1
            if row.project:
                proj_era[name].add(row.project)
    for raw in tool_names:
        tool_all[aliases.get(raw, raw)] += 1
    names = set(slash_all) | set(tool_all) | set(catalog)
    skills: dict[str, dict[str, int]] = {}
    for n in sorted(names):
        row_out = {
            "slash_all": slash_all[n],
            "slash_era": slash_era[n],
            "tool_all": tool_all[n],
            "all_time": slash_all[n] + tool_all[n],
            "projects_all": len(proj_all[n]),
            "projects_era": len(proj_era[n]),
        }
        if not boundary:
            del row_out["slash_era"], row_out["projects_era"]
        skills[n] = row_out
    rank_era = sorted(skills, key=lambda n: (-skills[n]["slash_era"], n)) if boundary else []
    return {
        "boundary": boundary,
        "skills": skills,
        "rank_all": sorted(skills, key=lambda n: (-skills[n]["all_time"], n)),
        "rank_era": rank_era,
    }


def resolve_since(value: str, today: date | None = None) -> str:
    """Return ``YYYY-MM-DD`` for a date or an ``<n>d`` offset before today.

    Examples
    --------
    >>> resolve_since("2026-02-01")
    '2026-02-01'
    >>> resolve_since("90d", date(2026, 10, 7))
    '2026-07-09'
    """
    if DATE_RE.match(value):
        return value
    m = re.fullmatch(r"(\d+)d", value)
    if m is None:
        msg = f"since must be YYYY-MM-DD or <n>d: {value!r}"
        raise ValueError(msg)
    base = today or date.today()  # noqa: DTZ011
    return (base - timedelta(days=int(m.group(1)))).isoformat()


def window_count(
    rows: Sequence[Row],
    prompts: Sequence[Prompt],
    spec: str,
    aliases: dict[str, str],
    today: date | None = None,
) -> dict[str, object]:
    """Count a pattern and its denominator in a window.

    ``spec`` is ``SKILL@SINCE@REGEX``. With a skill, ``invocations`` is that
    skill's slash invocations since ``SINCE`` (renames summed), ``matched`` is
    those whose text matches ``REGEX`` (all of them when the regex is empty),
    and ``ratio`` is their quotient, ``null`` below 10 invocations. With an
    empty skill, ``matched`` counts non-slash prompts matching ``REGEX`` and
    there is no denominator.

    Examples
    --------
    >>> rows = [
    ...     Row("2026-03-01", "a:b", "/p", "/a:b x, no trailer"),
    ...     Row("2026-03-02", "a:b", "/q", "/a:b y"),
    ...     Row("2026-01-01", "a:b", "/q", "/a:b no trailer"),
    ... ]
    >>> w = window_count(rows, [], "a:b@2026-02-01@no trailer", {})
    >>> (w["invocations"], w["matched"], w["projects"], w["ratio"])
    (2, 1, 1, None)
    >>> p = [Prompt("2026-03-01", "run lint then test", "/p"), Prompt("", "run lint", "/q")]
    >>> window_count([], p, "@2026-02-01@run lint", {})["matched"]
    1
    """
    skill, sep1, rest = spec.partition("@")
    since_raw, _, regex = rest.partition("@")
    if not sep1 or not since_raw or (not skill and not regex):
        msg = f"window must be SKILL@SINCE[@REGEX], regex required without a skill: {spec!r}"
        raise ValueError(msg)
    since = resolve_since(since_raw, today)
    pattern = re.compile(regex) if regex else None
    out: dict[str, object] = {"skill": skill, "since": since, "regex": regex}
    if skill:
        pool = [
            r for r in rows if aliases.get(r.skill, r.skill) == skill and r.day and r.day >= since
        ]
        hit = [r for r in pool if pattern is None or pattern.search(r.text)]
        out["invocations"] = len(pool)
        out["matched"] = len(hit)
        out["projects"] = len({r.project for r in hit if r.project})
        enough = len(pool) >= MIN_RATIO_INVOCATIONS
        out["ratio"] = round(len(hit) / len(pool), 2) if enough else None
    else:
        found = [
            p
            for p in prompts
            if p.day and p.day >= since and not p.text.startswith("/") and re.search(regex, p.text)
        ]
        out["matched"] = len(found)
        out["projects"] = len({p.project for p in found if p.project})
    return out


def ledger_key(head: str, findings: Sequence[dict[str, object]]) -> str:
    r"""Return the ledger key: sha256 hex of ``head`` and the finding set.

    The hashed text is ``<head>\n`` followed by each finding as compact JSON
    with sorted keys, the findings sorted by that text.

    Examples
    --------
    >>> f1 = {"id": "f1", "verdict": "x", "skill": "a:b", "expected_change": "y"}
    >>> f2 = {"id": "f2", "verdict": "absent", "skill": "a:c", "expected_change": "z"}
    >>> a = ledger_key("abc", [f2, f1])
    >>> a == ledger_key("abc", [f1, f2]) and len(a) == 64
    True
    >>> a == ledger_key("abd", [f1, f2])
    False
    >>> a == ledger_key("abc", [f1, {**f2, "skill": "a:d"}])
    False
    >>> a == ledger_key("abc", [f1, {**f2, "expected_change": "w"}])
    False
    >>> a == ledger_key("abc", [f1, {**f2, "prompt": "w"}])
    False
    """
    lines = sorted(json.dumps(f, sort_keys=True, separators=(",", ":")) + "\n" for f in findings)
    return hashlib.sha256((head + "\n" + "".join(lines)).encode()).hexdigest()


def validate_findings(data: object) -> list[dict[str, object]]:
    """Check the findings list and return it.

    Every finding needs a unique ``id``, a ``verdict``, the ``skill`` it
    edits (or proposes), and an ``expected_change`` naming the observable
    shift in usage it predicts.

    Examples
    --------
    >>> ok = {"id": "f1", "verdict": "absent", "skill": "a:b", "expected_change": "x"}
    >>> validate_findings([ok])[0]["id"]
    'f1'
    >>> validate_findings([{"id": "f1"}])
    Traceback (most recent call last):
    ValueError: finding 0 needs a non-empty verdict
    """
    if not isinstance(data, list) or not data:
        msg = "findings must be a non-empty JSON list"
        raise ValueError(msg)
    out: list[dict[str, object]] = []
    seen: set[str] = set()
    for i, item in enumerate(t.cast("list[object]", data)):
        if not isinstance(item, dict):
            msg = f"finding {i} must be an object"
            raise TypeError(msg)
        rec = t.cast("dict[str, object]", item)
        for field in ("id", "verdict", "skill", "expected_change"):
            value = rec.get(field)
            if not isinstance(value, str) or not value.strip():
                msg = f"finding {i} needs a non-empty {field}"
                raise ValueError(msg)
        if rec["verdict"] not in VERDICTS:
            msg = f"finding {i} has unknown verdict {rec['verdict']!r}"
            raise ValueError(msg)
        fid = t.cast("str", rec["id"])
        if fid in seen:
            msg = f"duplicate finding id {fid!r}"
            raise ValueError(msg)
        seen.add(fid)
        out.append(rec)
    return out


def verify_ledger(ledger: object, head: str) -> tuple[bool, str]:
    """Recompute a loaded ledger's key against the current ``head``.

    Examples
    --------
    >>> f = [{"id": "f1", "verdict": "absent", "skill": "a:b", "expected_change": "x"}]
    >>> led = {"head": "h1", "findings": f, "key": ledger_key("h1", f)}
    >>> verify_ledger(led, "h1")
    (True, 'ok')
    >>> verify_ledger(led, "h2")
    (False, 'head moved: ledger h1, catalog h2')
    >>> verify_ledger({**led, "findings": [{**f[0], "skill": "a:c"}]}, "h1")
    (False, 'findings changed since the ledger was saved')
    """
    if not isinstance(ledger, dict):
        return False, "ledger is not a JSON object"
    rec = t.cast("dict[str, object]", ledger)
    try:
        findings = validate_findings(rec.get("findings"))
    except ValueError as exc:
        return False, f"ledger findings invalid: {exc}"
    saved_head = rec.get("head")
    if not isinstance(saved_head, str):
        return False, "ledger has no head"
    if ledger_key(saved_head, findings) != rec.get("key"):
        return False, "findings changed since the ledger was saved"
    if saved_head != head:
        return False, f"head moved: ledger {saved_head[:7]}, catalog {head[:7]}"
    return True, "ok"


DEFAULT_GLOB = "plugins/*/skills/*/SKILL.md"
FRONTMATTER_PARTS = 3
RENAME_COLS = 3
REBUILD_MIN_SKILLS = 3
RENAME_SUBJECT_RE = "renam|replac|supersed|merge|split"


def _git(*args: str, cwd: str | None = None) -> str:
    done = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if done.returncode:
        raise subprocess.CalledProcessError(
            done.returncode, ["git", *args], done.stdout, done.stderr
        )
    return done.stdout.strip()


def _skill_text(root: str, path: str) -> str | None:
    """Return a skill file from ``HEAD``, else the working tree, else ``None``."""
    try:
        return _git("show", f"HEAD:{path}", cwd=root)
    except subprocess.CalledProcessError:
        pass
    try:
        return (Path(root) / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def skill_name(path: str) -> str | None:
    """Return ``plugin:skill`` under ``plugins/<plugin>/skills/``, else the bare name.

    A skill under any other ``skills/`` directory (``skills/``,
    ``.claude/skills/``) has no plugin prefix.

    Examples
    --------
    >>> root = "plugins"
    >>> skill_name(f"{root}/a/skills/b/file")
    'a:b'
    >>> skill_name(".claude/skills/b/SKILL.md")
    'b'
    >>> skill_name(f"{root}/a/file") is None
    True
    """
    parts = path.split("/")
    for i, part in enumerate(parts[:-2]):
        if part == "skills":
            if parts[0] == "plugins" and i == 2:  # noqa: PLR2004
                return f"{parts[1]}:{parts[i + 1]}"
            return parts[i + 1]
    return None


def catalog_root(glob: str) -> str:
    """Return the directory a catalog glob starts in.

    Examples
    --------
    >>> catalog_root("plugins/*/skills/*/SKILL.md")
    'plugins'
    >>> catalog_root(".claude/skills/*/SKILL.md")
    '.claude/skills'
    """
    return glob.split("*", 1)[0].rstrip("/") or "."


def is_gated(text: str) -> bool:
    r"""Return whether the frontmatter sets ``disable-model-invocation: true``.

    Examples
    --------
    >>> is_gated("---\nname: x\ndisable-model-invocation: true\n---\nbody")
    True
    >>> is_gated("---\nname: x\n---\ndisable-model-invocation: true")
    False
    """
    parts = text.split("---", 2)
    if not text.startswith("---") or len(parts) < FRONTMATTER_PARTS:
        return False
    return re.search(r"^disable-model-invocation:\s*true\s*$", parts[1], re.MULTILINE) is not None


def parse_renames(log: str, current: Iterable[str]) -> dict[str, str]:
    r"""Map retired skill names to current ones from ``git log --name-status`` output.

    Chains (a to b to c) resolve to the final name. A name that is still in
    the catalog is not retired, so it is not mapped.

    Examples
    --------
    >>> log = (
    ...     "R100\tplugins/p/skills/a/SKILL.md\tplugins/p/skills/b/SKILL.md\n"
    ...     "R090\tplugins/p/skills/a/x.md\tplugins/p/skills/b/x.md\n"
    ...     "R100\tplugins/p/skills/b/SKILL.md\tplugins/q/skills/c/SKILL.md\n"
    ...     "R100\tplugins/p/skills/b/y.md\tplugins/p/skills/b/z.md\n"
    ... )
    >>> parse_renames(log, ["q:c"])
    {'p:a': 'q:c', 'p:b': 'q:c'}
    >>> parse_renames(log, ["q:c", "p:a"])
    {'p:b': 'q:c'}
    """
    step: dict[str, str] = {}
    for line in log.splitlines():
        cols = line.split("\t")
        if len(cols) != RENAME_COLS or not cols[0].startswith("R"):
            continue
        old, new = skill_name(cols[1]), skill_name(cols[2])
        if old and new and old != new:
            _ = step.setdefault(old, new)
    live = set(current)
    out: dict[str, str] = {}
    for old, first in step.items():
        if old in live:
            continue
        final, hops = first, 0
        while final in step and final not in live and hops < len(step):
            final, hops = step[final], hops + 1
        out[old] = final
    return out


def era_boundary(births: dict[str, str]) -> dict[str, object]:
    """Pick the era boundary from skill birth dates.

    A rebuild is a day on which at least 3 skills were born and at least 10%
    of the catalog. The latest rebuild is the boundary; the rest are
    runners-up, largest first. ``date`` is empty when no day qualifies.

    Examples
    --------
    >>> b = {f"p:s{i}": "2026-02-01" for i in range(3)}
    >>> b.update({f"p:t{i}": "2026-03-01" for i in range(4)})
    >>> b.update({f"p:u{i}": f"2026-04-{i + 1:02d}" for i in range(13)})
    >>> era_boundary(b)
    {'date': '2026-03-01', 'size': 4, 'runners_up': [{'date': '2026-02-01', 'size': 3}]}
    >>> era_boundary({"p:a": "2026-01-01"})["date"]
    ''
    """
    by_day: Counter[str] = Counter(births.values())
    total = len(births)
    rebuilds = {d: n for d, n in by_day.items() if n >= REBUILD_MIN_SKILLS and n * 10 >= total}
    if not rebuilds:
        return {"date": "", "size": 0, "runners_up": []}
    latest = max(rebuilds)
    others = sorted(
        ((d, n) for d, n in rebuilds.items() if d != latest), key=lambda x: (-x[1], x[0])
    )
    return {
        "date": latest,
        "size": rebuilds[latest],
        "runners_up": [{"date": d, "size": n} for d, n in others],
    }


def default_ledger_path() -> Path:
    """Resolve the per-worktree ledger path under the git directory.

    ``git rev-parse --git-path`` handles linked worktrees, where ``.git`` is a
    file. The directory sits outside the working tree, so a sweep leaves no
    untracked files behind.
    """
    return Path(_git("rev-parse", "--git-path", "self-improvement/ledger.json")).resolve()


def _cmd_counts(args: Args) -> int:
    history = Path(args.history)
    catalog: list[str] = []
    if args.catalog:
        catalog = [
            ln.strip()
            for ln in Path(args.catalog).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    with history.open(encoding="utf-8", errors="replace") as fh:
        rows, prompts, records, malformed = parse_history(fh, catalog)
    tool_names: list[str] = []
    tool_status = "unavailable" if args.tool_unavailable else "absent"
    if args.tool_log and not args.tool_unavailable:
        with Path(args.tool_log).open(encoding="utf-8", errors="replace") as fh:
            tool_names = parse_tool_log(fh)
        tool_status = "read" if tool_names else "empty"
    aliases = parse_aliases(args.alias)
    out = summarize(rows, tool_names, args.boundary, aliases, catalog)
    out["windows"] = [window_count(rows, prompts, spec, aliases) for spec in args.window]
    slash_status = "empty" if records == 0 else "partial" if malformed else "complete"
    out["channels"] = {
        "slash": {"status": slash_status, "records": records, "malformed": malformed},
        "tool": {"status": tool_status, "occurrences": len(tool_names)},
    }
    out["complete"] = slash_status == "complete" and tool_status in {"read", "unavailable"}
    print(json.dumps(out, indent=2))
    return 0


def _cmd_catalog(args: Args) -> int:
    root = args.root
    glob = args.catalog_glob
    shallow = _git("rev-parse", "--is-shallow-repository", cwd=root) == "true"
    paths = sorted(_git("ls-files", "--", glob, cwd=root).splitlines())
    skills: list[dict[str, object]] = []
    births: dict[str, str] = {}
    for path in paths:
        name = skill_name(path)
        if name is None:
            continue
        days = (
            ""
            if shallow
            else _git("log", "--follow", "--format=%ad", "--date=short", "--", path, cwd=root)
        )
        born = min(days.splitlines()) if days else ""
        if born:
            births[name] = born
        text = _skill_text(root, path)
        if text is None:
            continue
        skills.append({"name": name, "path": path, "gated": is_gated(text), "born": born})
    renames = _git(
        "log",
        "--diff-filter=R",
        "--name-status",
        "--format=",
        "--",
        glob.rsplit("/", 1)[0],
        cwd=root,
    )
    subjects = _git(
        "log",
        "--extended-regexp",
        "--regexp-ignore-case",
        f"--grep={RENAME_SUBJECT_RE}",
        "--format=%h %s",
        "--",
        glob.rsplit("/", 1)[0],
        cwd=root,
    )
    out = {
        "shallow": shallow,
        "skills": skills,
        "renames": parse_renames(renames, births),
        "rename_subjects": subjects.splitlines(),
        "era": era_boundary(births),
    }
    if args.names_out:
        _ = Path(args.names_out).write_text(
            "".join(f"{s['name']}\n" for s in skills), encoding="utf-8"
        )
    print(json.dumps(out, indent=2))
    return 0


def _tracked_changes_without_head() -> list[str]:
    """List staged or modified paths in a repository that has no commit yet."""
    porcelain = _git("status", "--porcelain", "--untracked-files=no")
    return [ln[3:].split(" -> ")[-1] for ln in porcelain.splitlines() if ln[3:]]


def _autosquash_refusal(base: str) -> str:
    """Return why a rebase from ``base`` must not run, or an empty string."""
    ancestor = subprocess.run(  # noqa: S603
        ["git", "merge-base", "--is-ancestor", base, "HEAD"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        return f"{base} is not an ancestor of HEAD"
    if _git("branch", "--remotes", "--contains", base):
        return f"{base} is already on a remote branch"
    if _git("status", "--porcelain", "--untracked-files=no"):
        return "tracked files have uncommitted changes"
    return ""


def _cmd_autosquash(args: Args) -> int:
    """Fold ``fixup!`` commits into their targets, starting at ``--onto``."""
    base = args.onto
    refusal = _autosquash_refusal(base)
    if refusal:
        print(f"error: {refusal}; nothing rewritten", file=sys.stderr)
        print(json.dumps({"squashed": False, "refused": refusal}))
        return 2
    parent = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--verify", "--quiet", f"{base}^"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    start = [f"{base}^"] if parent.returncode == 0 else ["--root"]
    env = {**os.environ, "GIT_SEQUENCE_EDITOR": "true"}
    done = subprocess.run(  # noqa: S603
        ["git", "rebase", "-i", "--autosquash", *start],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if done.returncode != 0:
        _ = subprocess.run(["git", "rebase", "--abort"], check=False, capture_output=True)  # noqa: S607
        print(done.stderr.strip() or done.stdout.strip(), file=sys.stderr)
        print(
            "error: fixup conflicts with a later commit; rebase aborted, branch unchanged",
            file=sys.stderr,
        )
        print(json.dumps({"squashed": False, "aborted": True}))
        return 2
    span = "HEAD" if start == ["--root"] else f"{base}^..HEAD"
    left = [
        ln
        for ln in _git("log", "--format=%s", span).splitlines()
        if ln.startswith(("fixup! ", "squash! ", "amend! "))
    ]
    print(json.dumps({"squashed": not left, "unsquashed": left}))
    return 0 if not left else 1


def _cmd_tree_check(args: Args) -> int:
    ignored = {Path(p).resolve() for p in args.ignore}
    try:
        tracked = _git("diff", "--name-only", "--relative", "HEAD", "--").splitlines()
    except subprocess.CalledProcessError:
        tracked = _tracked_changes_without_head()
    untracked = _git(
        "ls-files", "--others", "--exclude-standard", "--", ":/" + catalog_root(args.catalog_glob)
    ).splitlines()
    dirty = sorted(p for p in {*tracked, *untracked} if Path(p).resolve() not in ignored)
    print(json.dumps({"clean": not dirty, "dirty": dirty}))
    return 0 if not dirty else 1


def _cmd_ledger_path(_args: Args) -> int:
    print(default_ledger_path())
    return 0


def _cmd_ledger_save(args: Args) -> int:
    today = date.today()  # noqa: DTZ011
    resweep_on = args.resweep_on or (today + timedelta(days=args.resweep_days)).isoformat()
    if not DATE_RE.match(resweep_on):
        print("--resweep-on must be YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        findings = validate_findings(
            t.cast("object", json.loads(Path(args.findings).read_text(encoding="utf-8")))
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    head = _git("rev-parse", "HEAD")
    out = Path(args.out) if args.out else default_ledger_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "version": LEDGER_VERSION,
        "created": today.isoformat(),
        "resweep_on": resweep_on,
        "head": head,
        "key": ledger_key(head, findings),
        "findings": findings,
    }
    _ = out.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"path": str(out), "key": ledger["key"], "head": head, "resweep_on": resweep_on})
    )
    return 0


def _cmd_ledger_verify(args: Args) -> int:
    path = Path(args.ledger) if args.ledger else default_ledger_path()
    try:
        ledger = t.cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "reason": f"ledger unreadable: {exc.__class__.__name__}"}))
        return 1
    ok, reason = verify_ledger(ledger, _git("rev-parse", "HEAD"))
    print(json.dumps({"ok": ok, "reason": reason}))
    return 0 if ok else 1


COMMANDS: dict[str, Callable[[Args], int]] = {
    "catalog": _cmd_catalog,
    "counts": _cmd_counts,
    "tree-check": _cmd_tree_check,
    "autosquash": _cmd_autosquash,
    "ledger-path": _cmd_ledger_path,
    "ledger-save": _cmd_ledger_save,
    "ledger-verify": _cmd_ledger_verify,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="cmd", required=True)

    glob_help = (
        "git pathspec of the catalog's SKILL.md files, such as skills/*/SKILL.md "
        f"or .claude/skills/*/SKILL.md; default {DEFAULT_GLOB}"
    )
    cat = sub.add_parser("catalog", help="skills, rename map, birth dates, era boundary as JSON")
    _ = cat.add_argument("--root", default=".", help="repository root; default is the cwd")
    _ = cat.add_argument("--catalog-glob", default=DEFAULT_GLOB, help=glob_help)
    _ = cat.add_argument("--names-out", help="also write the skill names, one per line, here")

    tree = sub.add_parser(
        "tree-check", help="exit 1 on tracked changes or untracked files under the catalog"
    )
    _ = tree.add_argument(
        "--ignore", action="append", default=[], help="path to leave out, repeatable"
    )
    _ = tree.add_argument("--catalog-glob", default=DEFAULT_GLOB, help=glob_help)

    squash = sub.add_parser(
        "autosquash",
        help="fold fixup! commits since --onto; exit 1 if any remain, 2 if refused or aborted",
    )
    _ = squash.add_argument("--onto", required=True, help="commit the earliest fixup targets")

    counts = sub.add_parser("counts", help="per-skill counts, era split, spread as JSON")
    _ = counts.add_argument("--history", required=True, help="prompt-history JSONL file")
    _ = counts.add_argument(
        "--boundary", default="", help="era boundary, YYYY-MM-DD; omit to rank all-time only"
    )
    _ = counts.add_argument(
        "--tool-log", help="text file with one Launching skill: line per launch"
    )
    _ = counts.add_argument(
        "--tool-unavailable",
        action="store_true",
        help="host writes no Launching skill: line; count the slash channel only",
    )
    _ = counts.add_argument("--catalog", help="file of current skill names, one per line")
    _ = counts.add_argument(
        "--window",
        action="append",
        default=[],
        help=(
            "SKILL@SINCE[@REGEX], repeatable: invocations since a date (or <n>d ago), "
            "those matching REGEX, and their spread; empty SKILL counts non-slash "
            "prompts and needs REGEX"
        ),
    )
    _ = counts.add_argument(
        "--alias", action="append", default=[], help="old=new rename, repeatable"
    )

    _ = sub.add_parser("ledger-path", help="print the default ledger path")

    save = sub.add_parser("ledger-save", help="write the ledger with its key")
    _ = save.add_argument("--findings", required=True, help="JSON list of findings")
    _ = save.add_argument("--resweep-on", help="date to sweep again, YYYY-MM-DD")
    _ = save.add_argument(
        "--resweep-days", type=int, default=30, help="days from today when --resweep-on is absent"
    )
    _ = save.add_argument("--out", help="ledger path; default is the per-worktree path")

    verify = sub.add_parser("ledger-verify", help="recompute the key; exit 1 on mismatch")
    _ = verify.add_argument(
        "ledger", nargs="?", help="ledger path; default is the per-worktree path"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    args = build_parser().parse_args(argv, namespace=Args())
    try:
        return COMMANDS[args.cmd](args)
    except subprocess.CalledProcessError as exc:
        stderr = t.cast("str", exc.stderr or "")
        detail = stderr.strip() or str(exc)
        print(f"error: {detail}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
