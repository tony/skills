#!/usr/bin/env python3
"""Offline plan arithmetic for package-updater: cooldown lapse dates and commit tracks.

``plan_rules.py lapse --published TIME (--window N --unit UNIT | --cutoff TIME) [--now TIME]``
prints when a release becomes visible under a rolling window (``published + window``, visible
from that instant on) or a fixed cutoff (visible only when published at or before it; waiting
never lifts it). ``UNIT`` is minutes, hours, days or weeks. A bare date (``2026-01-05``) is
read as the end of that UTC day, 23:59, which errs toward waiting.

``plan_rules.py track [--pin FILE...]`` reads one ``--lock-diff`` or ``--manifest-diff`` result
from stdin and assigns each moved package its commit track: ``named`` for a new major (for 0.x
a new minor), ``bulk`` for an in-range move, ``by-hand`` for a range or file the diff could
not classify. ``--pin`` classifies pin files by name. Whether an in-range package earns its own
commit, and which packages form a release train, stay a judgment.

Exit status: 0, 1 when ``track`` stdin is not a diff result, 2 on bad usage. A file-level error
in the diff is data: it goes to ``by_hand`` and the exit is 0.
"""

# ruff: noqa: PLR2004
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import cast

UNITS = {"minutes": "minutes", "hours": "hours", "days": "days", "weeks": "weeks"}
PIN_TRACKS = {
    ".tool-versions": "toolchain",
    ".nvmrc": "toolchain",
    ".node-version": "toolchain",
    ".python-version": "toolchain",
    ".ruby-version": "toolchain",
    ".java-version": "toolchain",
    ".terraform-version": "toolchain",
    "mise.toml": "toolchain",
    ".mise.toml": "toolchain",
    "rust-toolchain.toml": "toolchain",
    "rust-toolchain": "toolchain",
    "package.json": "mixed: packageManager and engines are package-manager, ranges are not",
    "go.mod": "mixed: go and toolchain lines are toolchain, require lines are dependencies",
}


def parse_time(text: str) -> datetime:
    """Parse an ISO time, or a bare date as 23:59 UTC of that day.

    >>> parse_time("2026-01-05").isoformat()
    '2026-01-05T23:59:00+00:00'
    >>> parse_time("2026-01-05T08:30:00Z").isoformat()
    '2026-01-05T08:30:00+00:00'
    """
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.fromisoformat(text).replace(hour=23, minute=59, tzinfo=UTC)
    when = datetime.fromisoformat(text)
    if when.tzinfo is None:
        message = f"time has no zone: {text}"
        raise ValueError(message)
    return when.astimezone(UTC)


def lapse(
    published: datetime,
    now: datetime,
    *,
    window: timedelta | None = None,
    cutoff: datetime | None = None,
) -> dict[str, object]:
    """Return when ``published`` becomes visible, and whether it is visible at ``now``."""
    if cutoff is not None:
        visible = published <= cutoff
        return {"kind": "cutoff", "visible_at": None, "visible": visible, "waiting_helps": False}
    if window is None or window <= timedelta(0):
        message = "a positive window or a cutoff is required"
        raise ValueError(message)
    at = published + window
    return {
        "kind": "rolling",
        "visible_at": at.isoformat(),
        "visible_day": at.date().isoformat(),
        "visible": now >= at,
        "waiting_helps": True,
    }


def tracks(diff: dict[str, object]) -> dict[str, object]:
    """Assign a track to each package in a ``--lock-diff`` or ``--manifest-diff`` result."""
    entries: list[dict[str, object]] = []
    by_hand: list[dict[str, object]] = []
    for file, result in diff.items():
        if file == "path" or not isinstance(result, dict):
            continue
        found = cast("dict[str, object]", result)
        if "error" in found or "new" in found:
            by_hand.append({"file": file, "reason": found.get("error", "new file, no baseline")})
            continue
        for bucket, track in (("majors", "named"), ("in_range", "bulk")):
            rows = cast("list[dict[str, object]]", found.get(bucket, []))
            entries.extend({"file": file, "track": track, **e} for e in rows)
        unclassified = cast("list[dict[str, object]]", found.get("unclassified", []))
        by_hand.extend({"file": file, **e} for e in unclassified)
    return {"entries": entries, "by_hand": by_hand}


def main(argv: list[str]) -> int:
    """Run a subcommand; exit 2 on bad usage and 1 when the input carries an error."""
    if argv[:1] == ["lapse"]:
        opts = dict(zip(argv[1::2], argv[2::2], strict=False))
        try:
            published = parse_time(opts["--published"])
            now = parse_time(opts["--now"]) if "--now" in opts else datetime.now(UTC)
            if "--cutoff" in opts:
                result = lapse(published, now, cutoff=parse_time(opts["--cutoff"]))
            else:
                unit = UNITS[opts["--unit"]]
                result = lapse(published, now, window=timedelta(**{unit: int(opts["--window"])}))
        except (KeyError, ValueError) as error:
            sys.stderr.write(f"plan_rules.py: lapse needs valid arguments ({error})\n")
            return 2
        sys.stdout.write(json.dumps(result) + "\n")
        return 0
    if argv[:1] == ["track"]:
        if argv[1:2] == ["--pin"] and len(argv) > 2:
            out = {f: PIN_TRACKS.get(f.rsplit("/", 1)[-1], "unknown") for f in argv[2:]}
            sys.stdout.write(json.dumps(out) + "\n")
            return 0
        if len(argv) == 1:
            try:
                loaded = json.load(sys.stdin)
                if not isinstance(loaded, dict):
                    raise ValueError  # noqa: TRY004, TRY301
                result = tracks(cast("dict[str, object]", loaded))
            except ValueError:
                sys.stderr.write("plan_rules.py: stdin is not a repo_facts diff result\n")
                return 1
            sys.stdout.write(json.dumps(result) + "\n")
            return 0
    sys.stderr.write("usage: plan_rules.py lapse ... | track [--pin FILE...]\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
