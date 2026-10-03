# Status

`<topic.py>` is the script path from the skill that sent you here.

```console
$ python3 <topic.py> status
```

Add `--namespace <ns>` to narrow it and `--root` for a non-default root. For each topic it reports the latest run, every run date, sources by state, open questions, cards still without notes, assessment criteria with no source or an unknown rating, and whether a report exists. Only runs with an `index.md` count as topics, so other dated folders under the root stay out of it.

Present one line per topic, most urgent first, each with its next action:

- failed checks (vanished, moved, changed, misquoted): `verify`, then fix the claims they support.
- stale, unverified, or unchecked sources: a new run with `continue`, which re-verifies them; intact sources need a live `verify` before a client sees the report.
- open questions or criteria gaps: `continue --fill`.
- moving pins: re-add the source with the exact version its page states.
- no report: `report`.

Read-only: status never writes.

## Output

Open with a one-line hero (`✓ <n> topics under <root>` or `⚠ No topics under <root>`), then:

1. `## Topics`: one line per topic, most urgent first: latest run, sources by state, open questions, next action.

End with an `AskUserQuestion` panel (for example: continue a topic, verify a topic, stop). Skip it in plan mode; without an interactive host, print the options as a numbered list.
