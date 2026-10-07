#!/usr/bin/env python3
"""Bounded waits for a pull request's CI checks and review agents.

``ci`` polls ``gh pr checks`` until at least one check exists on the head and
none is pending. ``agents`` polls reviews and comments until every named login
has weighed in on a head SHA; a trailing ``[bot]`` is ignored on both sides.
Reviews and issue comments are read; inline review comments are not. Each
prints one JSON line.

Exit codes: 0 done, 1 a check failed, 2 timed out, 3 no check appeared within
the grace period, 4 ``gh`` failed (its stderr is printed).
"""

# ruff: noqa: S603
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

_FAIL = {"fail", "cancel"}


def classify_ci(checks: list[dict[str, str]]) -> str:
    """Return ``none``, ``failed``, ``pending``, or ``green`` for a check list.

    >>> classify_ci([])
    'none'
    >>> classify_ci([{"bucket": "pass"}, {"bucket": "pending"}])
    'pending'
    >>> classify_ci([{"bucket": "fail"}, {"bucket": "pending"}])
    'failed'
    >>> classify_ci([{"bucket": "pass"}, {"bucket": "skipping"}])
    'green'
    """
    if not checks:
        return "none"
    buckets = {c.get("bucket", "") for c in checks}
    if buckets & _FAIL:
        return "failed"
    if "pending" in buckets:
        return "pending"
    return "green"


def _bare(login: str) -> str:
    return login.removesuffix("[bot]")


class GhError(Exception):
    """``gh`` could not run or exited nonzero without usable output."""


def missing_agents(
    roster: list[str],
    reviews: list[dict[str, str]],
    comments: list[dict[str, str]],
    sha: str,
    since: str,
) -> list[str]:
    """Return roster logins with no review on ``sha`` and no comment since.

    Timestamps are ISO 8601 UTC, so string comparison orders them.

    >>> r = [{"login": "a", "commit": "abc"}, {"login": "b", "commit": "old"}]
    >>> c = [{"login": "c", "at": "2026-01-02T00:00:00Z"}]
    >>> missing_agents(["a", "b", "c", "d"], r, c, "abc", "2026-01-01T00:00:00Z")
    ['b', 'd']
    >>> missing_agents(["bot"], [{"login": "bot[bot]", "commit": "abc"}], [], "abc", "")
    []
    >>> missing_agents(["a"], [{"login": None, "commit": "abc"}], [], "abc", "")
    ['a']
    """
    seen = {_bare(r["login"]) for r in reviews if r.get("login") and r.get("commit") == sha}
    seen |= {_bare(c["login"]) for c in comments if c.get("login") and c.get("at", "") >= since}
    return [login for login in roster if _bare(login) not in seen]


def _gh(*args: str, checks: bool = False) -> str:
    """Return ``gh`` stdout; raise ``GhError`` on failure.

    ``gh pr checks`` exits nonzero for failing or pending checks while still
    printing them, and for a head with no checks; ``checks=True`` accepts both.
    """
    try:
        done = subprocess.run(
            ["gh", *args],  # noqa: S607
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        msg = f"gh: {exc}"
        raise GhError(msg) from exc
    if done.returncode == 0:
        return done.stdout
    if checks and done.stdout.strip():
        return done.stdout
    if checks and "no checks reported" in done.stderr:
        return ""
    msg = done.stderr.strip() or f"gh exited {done.returncode}"
    raise GhError(msg)


def _lines(raw: str) -> list[dict[str, str]]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _wait_ci(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout * 60
    grace = time.monotonic() + args.grace * 60
    state = "none"
    while True:
        raw = _gh("pr", "checks", args.pr, "--json", "name,bucket,state", checks=True)
        state = classify_ci(json.loads(raw) if raw.strip() else [])
        if state in {"green", "failed"}:
            break
        if state == "none" and time.monotonic() >= grace:
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(args.interval)
    timed_out = state == "pending" or (state == "none" and time.monotonic() >= deadline)
    print(json.dumps({"status": "timeout" if timed_out else state}))
    if state == "failed":
        return 1
    if timed_out:
        return 2
    return 3 if state == "none" else 0


def _wait_agents(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout * 60
    base = f"repos/{{owner}}/{{repo}}/pulls/{args.pr}/reviews"
    reviews_jq = "-q"
    while True:
        reviews = _lines(
            _gh(
                "api", base, "--paginate", reviews_jq,
                ".[] | {login: .user.login, commit: .commit_id}",
            )
        )  # fmt: skip
        comments = _lines(
            _gh(
                "api", f"repos/{{owner}}/{{repo}}/issues/{args.pr}/comments",
                "--paginate", reviews_jq,
                ".[] | {login: .user.login, at: .created_at}",
            )
        )  # fmt: skip
        missing = missing_agents(args.agents, reviews, comments, args.sha, args.since)
        if not missing or time.monotonic() >= deadline:
            break
        time.sleep(args.interval)
    print(json.dumps({"missing": missing}))
    return 2 if missing else 0


def main(argv: list[str] | None = None) -> int:
    """Run the ``ci`` or ``agents`` wait."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ci = sub.add_parser("ci")
    ci.add_argument("pr")
    ci.add_argument("--timeout", type=float, default=30, help="minutes")
    ci.add_argument("--grace", type=float, default=2, help="minutes to wait for a first check")
    ci.add_argument("--interval", type=float, default=30, help="seconds")
    ag = sub.add_parser("agents")
    ag.add_argument("pr")
    ag.add_argument("--sha", required=True)
    ag.add_argument("--since", required=True, help="ISO 8601 UTC push time")
    ag.add_argument("--agents", nargs="+", required=True)
    ag.add_argument("--timeout", type=float, default=10, help="minutes")
    ag.add_argument("--interval", type=float, default=30, help="seconds")
    args = parser.parse_args(argv)
    try:
        return _wait_ci(args) if args.cmd == "ci" else _wait_agents(args)
    except GhError as exc:
        sys.stderr.write(f"{exc}\n")
        return 4


if __name__ == "__main__":
    sys.exit(main())
