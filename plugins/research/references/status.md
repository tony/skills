# Status

```console
$ python3 <topic.py> status
```

Add `--namespace <ns>` to narrow it and `--root` for a non-default root. For each topic it reports the latest run, every run date, sources by state, open questions, assessment gaps, unweighed conflicts, released reports whose sources moved, and whether a report exists. Only runs with an `index.md` count as topics, so other dated folders under the root stay out of it.

Present one line per topic, most urgent first, each with its next action:

- released reports whose sources moved (`releases_affected`): `continue`, re-verify, release a corrected report to the same readers per `release.md`, and revisit each listed decision.
- failed checks (vanished, moved, changed, misquoted): `verify`, then fix the claims they support.
- conflicts not yet weighed (`conflicts_open`): `continue`, and weigh each per `analysis.md`.
- stale, unverified, or unchecked sources: a new run with `continue`, which re-verifies them; intact sources need a live `verify` before a client sees the report, and `release` refuses an offline check unless `--allow-offline` is passed.
- open questions or criteria gaps: `continue --fill`.
- moving pins: re-add the source with the exact version its page states.
- no report: `report`.

Read-only: status never writes.

## Output

Open with a one-line hero (`✓ <n> topics under <root>` or `⚠ No topics under <root>`), then:

1. `## Topics`: one line per topic, most urgent first: latest run, sources by state, open questions, next action.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ 2 topics under the Documents root

## Topics

- research/sqlite-wal, latest 2026-07-14: 6 sources (5 intact, 1 moved), 2 open questions; next: verify.
- research/uv-monorepo, latest 2026-07-12: 4 sources intact, 1 unknown rating; next: continue --fill.
```

The panel offers continue a topic, verify a topic, and stop; no bullet repeats a next action as a panel option. Panel options: continue a topic, verify a topic, stop.
