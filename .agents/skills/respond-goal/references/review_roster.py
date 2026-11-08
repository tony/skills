#!/usr/bin/env python3
"""List the accounts that reviewed recent pull requests, by account type.

Reads reviews, issue comments, and inline review comments of the most recent
pull requests through the REST API, whose ``user.type`` field is ``Bot`` for an
app account and ``User`` for a person. Prints a JSON array of
``{"login", "type", "bot", "surfaces", "prs"}``, bots first. ``bot`` is true
for type ``Bot`` or a login ending in ``[bot]``.

Exit codes: 0 listed (possibly empty), 4 ``gh`` failed (stderr says why).
"""

import argparse
import asyncio
import json
import sys
from functools import partial

import ghcli
from ghcli import GhError, gh

_SURFACES = {
    "reviews": "pulls/{n}/reviews",
    "comments": "issues/{n}/comments",
    "inline": "pulls/{n}/comments",
}
_USER = ".[] | select(.user != null) | [.user.login, .user.type] | @tsv"


def summarize(seen: list[tuple[str, str, str, str]]) -> list[dict[str, object]]:
    """Fold ``(pr, surface, login, type)`` sightings into one row per account.

    >>> rows = summarize([("1", "reviews", "ann", "User"), ("2", "inline", "x[bot]", "Bot")])
    >>> [(r["login"], r["bot"]) for r in rows]
    [('x[bot]', True), ('ann', False)]
    """
    kinds: dict[str, str] = {}
    surfaces: dict[str, set[str]] = {}
    prs: dict[str, set[str]] = {}
    for pr, surface, login, kind in seen:
        kinds.setdefault(login, kind)
        surfaces.setdefault(login, set()).add(surface)
        prs.setdefault(login, set()).add(pr)
    rows: list[dict[str, object]] = [
        {
            "login": login,
            "type": kind,
            "bot": kind == "Bot" or login.endswith("[bot]"),
            "surfaces": sorted(surfaces[login]),
            "prs": len(prs[login]),
        }
        for login, kind in kinds.items()
    ]
    return sorted(rows, key=lambda r: (not r["bot"], str(r["login"])))


def collect(limit: int) -> list[dict[str, object]]:
    """Return the account summary for the last ``limit`` pull requests."""
    listing = gh(
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        str(limit),
        "--json",
        "number",
        "--jq",
        ".[].number",
    )
    reads = [
        (number, surface, path) for number in listing.split() for surface, path in _SURFACES.items()
    ]
    raws = asyncio.run(
        ghcli.gather(
            [
                partial(
                    gh,
                    "api",
                    f"repos/{{owner}}/{{repo}}/{path.format(n=number)}",
                    "--paginate",
                    "--jq",
                    _USER,
                )
                for number, _, path in reads
            ],
            limit=4,
        )
    )
    seen: list[tuple[str, str, str, str]] = []
    for (number, surface, _), raw in zip(reads, raws, strict=True):
        for line in raw.splitlines():
            login, _, kind = line.partition("\t")
            if login:
                seen.append((number, surface, login, kind))
    return summarize(seen)


def main(argv: list[str] | None = None) -> int:
    """Print the roster candidates."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="recent pull requests to read")
    args = parser.parse_args(argv)
    try:
        sys.stdout.write(json.dumps(collect(args.limit)) + "\n")
    except GhError as exc:
        sys.stderr.write(f"{exc}\n")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
