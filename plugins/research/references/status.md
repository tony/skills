# Status

```console
$ python3 <topic.py> status
```

Add `--namespace <ns>` to narrow it and `--root` for a non-default root. Only runs with an `index.md` count as topics, so other dated folders under the root stay out of it. The result holds `recent`, the `<namespace>/<topic>` worked on last, and `topics`, already sorted by `urgency` and then by last update. Per topic it reports the latest run, every run date, sources by state (`layout.md` lists the states), open questions, assessment gaps, unweighed conflicts, moving pins, released reports whose sources moved, whether a report exists, and the ranked `next_action`.

A missing or unreadable root is an error (exit 2), not an empty list: report it as blocked and name `--root` and `RESEARCH_ROOT`. A topic whose ledger is damaged appears with an `error` instead of counts, and the exit is 1; report it per `layout.md` and rank it first.

## Next actions

`next_action` is the script's ranking, most urgent first. Print it as given and add the step it implies:

- `continue`, for a released report whose sources moved (`releases_affected`): continue the topic and re-verify. A corrected report goes to the same readers only when the user names `release`.
- `verify`, for a failed check (vanished, moved, changed, misquoted, unreachable, or unverifiable): verify, then fix the claims the failed sources support.
- `continue`, for conflicts not yet weighed (`conflicts_open`): weigh each per `analysis.md`.
- `continue`, for stale, unverified, or unchecked sources: a new run re-verifies them. Intact sources need a live `verify` before a client sees the report, and `release` refuses an offline check unless `--allow-offline` is passed.
- `continue --fill`, for open questions or criteria gaps.
- `add`, for moving pins: re-add the source with the exact version its page states.
- `report`, when no report exists.
- `none`, when nothing is left.

Read-only: status never writes.

## Output

Open with a one-line hero, `✓ <n> topics under the research root`, then one section:

1. `## Topics`: one line per topic in the script's order: `<namespace>/<topic>`, latest run, sources by state, open questions, `next_action`. With no topics, one bullet: "None; start one with foray".

A missing or unreadable root is a halted run: `⚠ Blocked: the research root is missing or unreadable`, then one line saying to pass `--root` or set `RESEARCH_ROOT`.

Write the reply per `reply-contract.md`.

```text
✓ 2 topics under the research root

## Topics

- research/sqlite-wal, latest 2026-07-14: 6 sources (5 intact, 1 moved), 2 open questions; next: verify.
- research/uv-monorepo, latest 2026-07-12: 4 sources intact, 1 unknown rating; next: continue --fill.
```

Panel options: continue a topic, verify a topic, stop.
