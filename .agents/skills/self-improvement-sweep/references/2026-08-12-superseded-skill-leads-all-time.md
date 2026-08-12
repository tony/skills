
# 2026-08-12 — A retired skill led the all-time ranking

The case that put currency in the evidence bar. The catalog's
third-most-invoked skill had not been invoked once in the current era,
and nothing in an all-time ranking said so.

## Input

Build the dated slash channel:

```console
jq -r 'select(.display != null) | select(.display | test("^/[a-z0-9-]+:[a-z0-9-]+")) | [(.timestamp / 1000 | todate | .[:10]), (.display | capture("^/(?<s>[a-z0-9-]+:[a-z0-9-]+)").s)] | @tsv' ~/.claude/history.jsonl > "$SCRATCH/slash-channel.tsv"
```

Rank it all-time:

```console
cut -f2 "$SCRATCH/slash-channel.tsv" | sort | uniq -c | sort -rn | head -4
```

```
    439 code-review:code-review
    265 riper:research
    222 pr:merge-commit
    193 riper:execute
```

Re-slice the same file for the current era:

```console
awk -F'\t' '$1 >= "2026-07-24"' "$SCRATCH/slash-channel.tsv" | cut -f2 | sort | uniq -c | sort -rn | head -4
```

```
     47 code-review:code-review
     46 merge-pr:this
     36 spike:bakeoff
     28 spike:probe
```

## Reasoning

`pr:merge-commit` holds 222 invocations all-time — third in the whole
catalog — and does not appear in the current era at all. `merge-pr:this`
holds 46 in the current era and is absent from the all-time top four.

They are the same behavior. `merge-pr:this` replaced `pr:merge-commit`,
and a supersession leaves no git trace linking the two, so no rename map
recovers the relationship.

An all-time ranking presents `pr:merge-commit` as a top-three skill
worth investing in. Every pattern typed around it is a historical
record of a workflow that already got its remedy. A sweep that ranked
only all-time would spend its best findings improving a skill nobody
invokes, and would rank its replacement ninth or lower.

The mirror image is what distinguishes this from abandonment: the
predecessor goes to zero on a date, and a sibling picks the traffic up
from that same date. A predecessor that goes quiet with nothing
inheriting its work is abandoned, which is a live finding with a
different remedy.

## Output

Rank the catalog twice, all-time and current-era, and report both.

Before running the verdicts on any pattern, check whether the skill it
concerns is still where the behavior lives. Name the successor and
confirm it carries the mirror image before calling anything superseded.

The boundary here is 2026-07-24, the most recent day on which a batch
of skills was born large enough to mark a catalog rebuild rather than
a handful of arrivals.
