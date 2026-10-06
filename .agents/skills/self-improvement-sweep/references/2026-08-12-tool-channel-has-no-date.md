
# 2026-08-12 — The tool channel cannot be dated

Measured while adding a current-era ranking to this skill.
The ranking needs a date on every invocation. One of the two channels
does not have one.

## Input

The exhaustive tool-channel sweep, the same query the census runs:

```console
uvx agentgrep --color never search --exhaustive '"Launching skill:"' --limit 3000 --no-progress --json > tool-channel.json
```

How many of its results carry a usable timestamp:

```console
jq -r '[.results[] | select(.timestamp != null)] | length, (.results | length)' tool-channel.json
```

```
2
262
```

The prompt channel, for contrast:

```console
uvx agentgrep --color never search 'spike' --limit 5 --no-progress --json | jq -r '.results[] | "\(.store)\tts=\(.timestamp)"'
```

```
claude.history	ts=2026-07-30T23:07:21.288000Z
claude.history	ts=2026-07-12T19:51:38.313000Z
claude.history	ts=2026-07-05T19:40:44.276000Z
claude.history	ts=2025-12-18T16:48:42.688000Z
claude.history	ts=2026-08-12T20:36:53.278000Z
```

Then the obvious rescue — let the query filter by date instead:

```console
uvx agentgrep --color never search --exhaustive '"Launching skill:" timestamp:>=2026-07-24' --limit 50 --no-progress --json | jq -c '.summary.status, .summary.coverage.matches_seen'
```

```
{"state":"complete","reason":null,"conditions":[]}
2
```

## Reasoning

Two of 262 transcript results carry a date. Prompt-history results
(`store: claude.history`) carry one every time; transcript results
(`store: claude.projects`) essentially never do.

The `timestamp:` filter does not rescue it. It returns the same two
records — the only two it can evaluate — and drops the other 260
without comment. `state` still reads `complete`, because the search
did complete; it simply had nothing to test 260 records against.

That is the worst available failure shape. A filtered query returning
2 of 262 looks exactly like a genuine finding that the era contains
almost no tool-channel activity, and the completeness field agrees
with it.

## Output

The era split is a slash-channel measurement. The union of both
channels can only be ranked all-time.

A report carrying a current-era ranking has to say which channel
produced it, because a skill the model reaches for on its own lives
mostly in the channel that cannot be dated and will look thinner in
that ranking than it is.

Do not use `timestamp:` on a tool-channel query. It answers a
different question than the one it appears to answer.
