#!/usr/bin/env python3
"""Collect a pull request's review feedback as normalized JSON.

Reads reviews, issue comments, inline review comments, review threads, and
failing checks, then prints one object: ``reviews``, ``comments``, ``inline``,
``threads``, and ``failing_checks``. Every entry carries the author's ``login``
and whether the account is a ``bot`` (REST ``user.type`` of ``Bot``, or a login
ending in ``[bot]``). Resolved and outdated threads are left out unless
``--include-resolved`` is given. A thread whose comments were cut at the
query's page size has ``truncated`` set; its remaining comments are in
``inline``.

For GraphQL, ``gh api --help`` says ``--paginate`` "requires that the original
query accepts an ``$endCursor: String`` variable and that it fetches the
``pageInfo{ hasNextPage, endCursor }`` set of fields from a collection"; the
thread query does both for ``reviewThreads``.

Exit codes: 0 collected, 4 ``gh`` failed (stderr says why; nothing is printed,
so a failed read never passes for empty feedback).
"""

import argparse
import asyncio
import json
import re
import sys
from typing import Any

import ghcli

GhError = ghcli.GhError
gh = ghcli.gh

_THREADS_QUERY = (
    "query($owner: String!, $repo: String!, $number: Int!, $endCursor: String) {"
    " repository(owner: $owner, name: $repo) { pullRequest(number: $number) {"
    " reviewThreads(first: 100, after: $endCursor) { pageInfo { hasNextPage endCursor }"
    " nodes { isResolved isOutdated path comments(first: 20) { pageInfo { hasNextPage }"
    " nodes { databaseId author { login __typename } body createdAt } } } } } } }"
)
_THREAD_NODES = ".data.repository.pullRequest.reviewThreads.nodes[]"


def _lines(raw: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _is_bot(login: str, kind: str) -> bool:
    """Return whether an account is automated.

    >>> _is_bot("x[bot]", "User"), _is_bot("app", "Bot"), _is_bot("ann", "User")
    (True, True, False)
    """
    return kind == "Bot" or login.endswith("[bot]")


def _rest(path: str, fields: str) -> list[dict[str, object]]:
    jq = f'.[] | {{{fields}, login: (.user.login // ""), type: (.user.type // "")}}'
    rows = _lines(gh("api", path, "--paginate", "--jq", jq))
    for row in rows:
        row["bot"] = _is_bot(str(row["login"]), str(row["type"]))
        del row["type"]
    return rows


def normalize_thread(node: dict[str, Any]) -> dict[str, Any]:
    """Reduce a ``reviewThreads`` node to its resolution state and comments."""
    block: dict[str, Any] = node["comments"]
    comments: list[dict[str, Any]] = []
    for item in block["nodes"]:
        author: dict[str, Any] = item.get("author") or {}
        login = str(author.get("login", ""))
        comments.append(
            {
                "id": item["databaseId"],
                "login": login,
                "bot": _is_bot(login, "Bot" if author.get("__typename") == "Bot" else ""),
                "body": item["body"],
                "at": item["createdAt"],
            }
        )
    return {
        "resolved": node["isResolved"],
        "outdated": node["isOutdated"],
        "path": node["path"],
        "truncated": block["pageInfo"]["hasNextPage"],
        "comments": comments,
    }


def collect(pr: str, *, include_resolved: bool) -> dict[str, object]:
    """Return the normalized feedback for ``pr``."""
    return asyncio.run(_collect(pr, include_resolved=include_resolved))


async def _collect(pr: str, *, include_resolved: bool) -> dict[str, object]:
    number = pr if pr.isdigit() else _number(pr)
    pull = f"repos/{{owner}}/{{repo}}/pulls/{number}"
    repo = gh("repo", "view", "--json", "owner,name", "--jq", '.owner.login + " " + .name').split()

    def read_threads() -> list[dict[str, object]]:
        return _lines(
            gh(
                "api", "graphql", "--paginate",
                "-F", f"owner={repo[0]}", "-F", f"repo={repo[1]}", "-F", f"number={number}",
                "-f", f"query={_THREADS_QUERY}", "--jq", _THREAD_NODES,
            )
        )  # fmt: skip

    async with ghcli.task_group() as group:
        threads = group.create_task(asyncio.to_thread(read_threads))
        checks = group.create_task(
            asyncio.to_thread(ghcli.pr_checks, number, "name,bucket,link", gh)
        )
        reviews = group.create_task(
            asyncio.to_thread(_rest, f"{pull}/reviews", "id, state, body, commit: .commit_id")
        )
        comments = group.create_task(
            asyncio.to_thread(
                _rest,
                f"repos/{{owner}}/{{repo}}/issues/{number}/comments",
                "id, body, at: .created_at",
            )
        )
        inline = group.create_task(
            asyncio.to_thread(
                _rest,
                f"{pull}/comments",
                "id, body, path, commit: .commit_id, at: .created_at, reply_to: .in_reply_to_id",
            )
        )
    kept = [
        normalize_thread(t)
        for t in threads.result()
        if include_resolved or not (t["isResolved"] or t["isOutdated"])
    ]
    failing = [
        {**c, "run": (re.search(r"/runs/(\d+)", str(c.get("link", ""))) or [None, ""])[1]}
        for c in checks.result()
        if c.get("bucket") in {"fail", "cancel"}
    ]
    return {
        "reviews": reviews.result(),
        "comments": comments.result(),
        "inline": inline.result(),
        "threads": kept,
        "failing_checks": failing,
    }


def _number(ref: str) -> str:
    found = re.search(r"/pull/(\d+)", ref)
    if found:
        return str(found.group(1))
    return gh("pr", "view", "--json", "number", "--jq", ".number").strip()


def main(argv: list[str] | None = None) -> int:
    """Print the feedback for ``--pr``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", required=True, help="number, URL, or current")
    parser.add_argument("--include-resolved", action="store_true")
    args = parser.parse_args(argv)
    try:
        out = collect(args.pr, include_resolved=args.include_resolved)
    except GhError as exc:
        sys.stderr.write(f"{exc}\n")
        return 4
    sys.stdout.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
