#!/usr/bin/env python3
"""Deterministic counting and the findings ledger for the sweep and apply skills.

``counts`` turns a prompt-history file (and optionally a log of skill-tool
launches) into per-skill invocation counts, an era split, and project spread.
``ledger-save`` writes the findings ledger outside the working tree and
``ledger-verify`` recomputes its key before any edit.

Run ``sweep.py <command> --help`` for each command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import typing as t
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

SLASH_RE = re.compile(r"^/([a-z0-9-]+:[a-z0-9-]+)")
TOOL_RE = re.compile(r"Launching skill: ([a-z0-9-]+(?::[a-z0-9-]+)?)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LEDGER_VERSION = 1


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
    out: str | None = None
    ledger: str | None = None


class Row(t.NamedTuple):
    """One slash-channel invocation."""

    day: str
    skill: str
    project: str


def parse_history(lines: Iterable[str]) -> tuple[list[Row], int, int]:
    """Extract slash invocations from prompt-history JSONL.

    A prompt counts only when ``display`` starts with ``/plugin:skill``, so a
    prompt that merely mentions one does not. Bare ``/skill`` names of
    user-level skills are not matched.

    Parameters
    ----------
    lines : Iterable[str]
        One JSON object per line, with ``display``, ``timestamp`` (epoch
        milliseconds), and ``project``.

    Returns
    -------
    tuple[list[Row], int, int]
        Invocation rows, records read, and malformed lines skipped.

    Examples
    --------
    >>> rows, records, bad = parse_history([
    ...     '{"display": "/spike:probe x", "timestamp": 1700000000000, "project": "/a"}',
    ...     '{"display": "see /spike:probe", "timestamp": 1700000000000}',
    ...     "not json",
    ... ])
    >>> rows
    [Row(day='2023-11-14', skill='spike:probe', project='/a')]
    >>> (records, bad)
    (2, 1)
    """
    rows: list[Row] = []
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
        match = SLASH_RE.match(display) if isinstance(display, str) else None
        if match is None:
            continue
        stamp = rec.get("timestamp")
        day = ""
        if isinstance(stamp, int | float):
            day = datetime.fromtimestamp(stamp / 1000, tz=UTC).date().isoformat()
        project = rec.get("project")
        rows.append(Row(day, match.group(1), project if isinstance(project, str) else ""))
    return rows, records, malformed


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
        if row.day and row.day >= boundary:
            slash_era[name] += 1
            if row.project:
                proj_era[name].add(row.project)
    for raw in tool_names:
        tool_all[aliases.get(raw, raw)] += 1
    names = set(slash_all) | set(tool_all) | set(catalog)
    skills = {
        n: {
            "slash_all": slash_all[n],
            "slash_era": slash_era[n],
            "tool_all": tool_all[n],
            "all_time": slash_all[n] + tool_all[n],
            "projects_all": len(proj_all[n]),
            "projects_era": len(proj_era[n]),
        }
        for n in sorted(names)
    }
    return {
        "boundary": boundary,
        "skills": skills,
        "rank_all": sorted(skills, key=lambda n: (-skills[n]["all_time"], n)),
        "rank_era": sorted(skills, key=lambda n: (-skills[n]["slash_era"], n)),
    }


def ledger_key(head: str, findings: Sequence[dict[str, object]]) -> str:
    r"""Return the ledger key: sha256 hex of ``head`` and the finding set.

    The hashed text is ``<head>\n`` followed by one ``<id>\t<verdict>\n``
    line per finding, sorted by id. Evidence fields do not enter the key.

    Examples
    --------
    >>> a = ledger_key("abc", [{"id": "f2", "verdict": "absent"}, {"id": "f1", "verdict": "x"}])
    >>> b = ledger_key("abc", [{"id": "f1", "verdict": "x"}, {"id": "f2", "verdict": "absent"}])
    >>> a == b and len(a) == 64
    True
    >>> a == ledger_key("abd", [{"id": "f1", "verdict": "x"}, {"id": "f2", "verdict": "absent"}])
    False
    """
    lines = sorted(f"{f['id']}\t{f['verdict']}\n" for f in findings)
    return hashlib.sha256((head + "\n" + "".join(lines)).encode()).hexdigest()


def validate_findings(data: object) -> list[dict[str, object]]:
    """Check the findings list and return it.

    Every finding needs a unique ``id``, a ``verdict``, and an
    ``expected_change`` naming the observable shift in usage it predicts.

    Examples
    --------
    >>> validate_findings([{"id": "f1", "verdict": "absent", "expected_change": "x"}])[0]["id"]
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
        for field in ("id", "verdict", "expected_change"):
            value = rec.get(field)
            if not isinstance(value, str) or not value.strip():
                msg = f"finding {i} needs a non-empty {field}"
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
    >>> f = [{"id": "f1", "verdict": "absent", "expected_change": "x"}]
    >>> led = {"head": "h1", "findings": f, "key": ledger_key("h1", f)}
    >>> verify_ledger(led, "h1")
    (True, 'ok')
    >>> verify_ledger(led, "h2")
    (False, 'head moved: ledger h1, catalog h2')
    >>> verify_ledger({**led, "findings": [{**f[0], "verdict": "y"}]}, "h1")
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


def _git(*args: str) -> str:
    done = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def default_ledger_path() -> Path:
    """Resolve the per-worktree ledger path under the git directory.

    ``git rev-parse --git-path`` handles linked worktrees, where ``.git`` is a
    file. The directory sits outside the working tree, so a sweep leaves no
    untracked files behind.
    """
    return Path(_git("rev-parse", "--git-path", "self-improvement/ledger.json")).resolve()


def _cmd_counts(args: Args) -> int:
    history = Path(args.history)
    with history.open(encoding="utf-8", errors="replace") as fh:
        rows, records, malformed = parse_history(fh)
    tool_names: list[str] = []
    tool_status = "absent"
    if args.tool_log:
        with Path(args.tool_log).open(encoding="utf-8", errors="replace") as fh:
            tool_names = parse_tool_log(fh)
        tool_status = "read" if tool_names else "empty"
    catalog: list[str] = []
    if args.catalog:
        catalog = [
            ln.strip()
            for ln in Path(args.catalog).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    out = summarize(rows, tool_names, args.boundary, parse_aliases(args.alias), catalog)
    slash_status = "empty" if records == 0 else "partial" if malformed else "complete"
    out["channels"] = {
        "slash": {"status": slash_status, "records": records, "malformed": malformed},
        "tool": {"status": tool_status, "occurrences": len(tool_names)},
    }
    out["complete"] = slash_status == "complete" and tool_status == "read"
    print(json.dumps(out, indent=2))
    return 0


def _cmd_ledger_path(_args: Args) -> int:
    print(default_ledger_path())
    return 0


def _cmd_ledger_save(args: Args) -> int:
    if not DATE_RE.match(args.resweep_on):
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
        "created": date.today().isoformat(),  # noqa: DTZ011
        "resweep_on": args.resweep_on,
        "head": head,
        "key": ledger_key(head, findings),
        "findings": findings,
    }
    _ = out.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(out), "key": ledger["key"], "head": head}))
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
    "counts": _cmd_counts,
    "ledger-path": _cmd_ledger_path,
    "ledger-save": _cmd_ledger_save,
    "ledger-verify": _cmd_ledger_verify,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    sub = parser.add_subparsers(dest="cmd", required=True)

    counts = sub.add_parser("counts", help="per-skill counts, era split, spread as JSON")
    _ = counts.add_argument("--history", required=True, help="prompt-history JSONL file")
    _ = counts.add_argument("--boundary", required=True, help="era boundary, YYYY-MM-DD")
    _ = counts.add_argument(
        "--tool-log", help="text file with one Launching skill: line per launch"
    )
    _ = counts.add_argument("--catalog", help="file of current skill names, one per line")
    _ = counts.add_argument(
        "--alias", action="append", default=[], help="old=new rename, repeatable"
    )

    _ = sub.add_parser("ledger-path", help="print the default ledger path")

    save = sub.add_parser("ledger-save", help="write the ledger with its key")
    _ = save.add_argument("--findings", required=True, help="JSON list of findings")
    _ = save.add_argument("--resweep-on", required=True, help="date to sweep again, YYYY-MM-DD")
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
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
