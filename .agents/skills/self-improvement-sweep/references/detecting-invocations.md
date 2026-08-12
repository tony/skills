# Detecting Skill Usage From Local Agent History

Every prompt you have typed and every transcript your agents wrote sits
in local stores on your disk — Claude Code, Codex, Cursor, Gemini and
the rest. That pile is the corpus, and `agentgrep` searches it. This
file is how to turn it into a per-skill invocation count, and the ways
that count comes back confidently wrong.

These are heuristics distilled from sweeps already run, not a worked
pass. `worked-example-spike.md` is that — one sweep followed from the
prompts it mined to the edits they became. The queries here are the
reusable part; copy them. The figures beside them record one machine on
one day and are kept only to show how large a trap was, never as a
threshold or an expected value. A number whose run you cannot inspect
is cheaper to re-measure than to trust.

## Invocations land in two places, and neither is the whole count

A skill gets invoked two different ways and each way is recorded
somewhere else. Call each one a channel. A count built on a single
channel is wrong.

**Typed slash commands** live in the host's prompt history —
`~/.claude/history.jsonl`, one JSON object per line carrying
`.display`, `.project`, and `.timestamp`. Cheap: no search, just `jq`
and `rg`.

Extract one dated row per record and keep it:

```console
jq -r 'select(.display != null) | [(.timestamp / 1000 | todate | .[:10]), .display] | @tsv' ~/.claude/history.jsonl | rg '^\S+\t/[a-z0-9-]+:[a-z0-9-]+' | sed -E 's|^(\S+)\t/([a-z0-9-]+:[a-z0-9-]+).*|\1\t\2|' > slash-channel.tsv
```

Two things in that pipeline are load-bearing. Carrying `.timestamp`
through is what makes an era split possible at all — rank straight to
`uniq -c` and the dates are gone, with no later phase able to recover
them. And anchoring the match to the start of the *record* rather than
to the start of any line is what stops a pasted prompt that merely
mentions the `action-worktree` skill from scoring as an invocation of it; on one
corpus, matching per line inflated the total by 43.

Rank it all-time:

```console
cut -f2 slash-channel.tsv | sort | uniq -c | sort -rn
```

Then re-slice the same file for the current era, using the boundary
Phase 0 derived from the catalog's birth dates:

```console
awk -F'\t' '$1 >= "<boundary>"' slash-channel.tsv | cut -f2 | sort | uniq -c | sort -rn
```

**Skill-tool invocations** emit a `Launching skill: <plugin>:<skill>`
line into the conversation transcript. These are *not* in prompt
history, so a default-depth search finds nothing — `--exhaustive` is
mandatory.

```console
uvx agentgrep --color never search --exhaustive '"Launching skill:"' --limit 2000 --no-progress --json
```

The two disagree, and not by a fixed amount. The ratio between them
belongs to each skill rather than to the corpus: a skill invoked almost
only by name outscores its tool-channel count by two or three orders of
magnitude, and one the model reaches for on its own inverts that
completely. An aggregate ratio therefore describes no skill in
particular, and a reader carrying one across will discard whichever
channel it made look small.

**A skill is only "unused" when it is absent from both.** Reporting
from the tool channel alone recommends deleting heavily used skills;
reporting from the slash channel alone erases the ones the model
invokes without ever being asked by name.

Do not try to predict which channel a skill lands in from its
frontmatter. `disable-model-invocation: true` does not confine a skill
to the slash channel — measured counterexamples exist in both
directions. Union the channels; do not model them.

## Renames split the history

A renamed skill keeps its old invocations under the old name forever.
Counting only the current name undercounts, sometimes by most of the
total: one measured rename left 150 invocations under the old name and
34 under the new one, an 82% undercount.

Recover the old names from the repository rather than guessing.

```console
git log --diff-filter=R --name-status --format='%h' -- 'plugins/*/skills/*'
```

Also read commit subjects for renames that moved a file the rename
detector scored below its threshold, and for skills replaced by a
different set rather than renamed — the successor carries none of the
predecessor's history either way. Sum across every name a single skill
has had before applying any threshold, and across nothing else — a
replacement is not a rename.

## Supersessions split it the other way

A rename and a supersession look identical in the counts and demand
opposite handling. A rename you detect and **sum** across. A
supersession — a skill replaced by a different one, or by a set of
them — leaves no git trace linking predecessor to successor, and
summing them is precisely wrong: the predecessor's invocations all
belong to the era before the successor shipped.

The tell is cheap once you look for it. A superseded skill has a full
all-time record and an empty recent half. Confirm it against the
successor, which carries the mirror image — empty until that date and
holding the traffic after it. A predecessor that went quiet with no
sibling picking up its work is abandoned rather than superseded, and
that is a different finding with a different remedy.

Recover the boundary from birth dates, since the rename detector scores
a supersession at nothing:

```console
git log --follow --format='%ad' --date=short -- <path to SKILL.md> | tail -1
```

Then window each finding against the birth date of the skill that
covers it. A procedure typed by hand over and over is a discoverability
gap only if the typing continued after the skill existed; measured
against the wrong date it reads as a gap either way.

## Spread, not just repetition

The evidence bar is repetition, spread, **and** currency. Spread is the
leg this section serves: a pattern confined to one project is that
project's quirk.

Project attribution sits in a different field per record type, and
reading only one of them silently reports zero spread. In `agentgrep`'s
`--json` output, prompt-history records carry it in `.metadata.project`
— their `path` is the single history file they all share, so deriving a
project from the path discards that whole channel. Transcript records
are the reverse: their metadata comes back empty and the project is the
`/projects/<slug>` path segment. Union both.

```console
uvx agentgrep --color never search --exhaustive '<pattern>' --limit 500 --no-progress --json | jq -r '[.. | objects | select(has("path")) | .metadata.project // (.path | capture("/projects/(?<p>[^/]+)").p) // empty] | .[]' | sort -u | wc -l
```

Those field names describe agentgrep's normalization, not the files
underneath it. The slash-channel query above reads
`~/.claude/history.jsonl` directly, and there the project is a
top-level `project` holding an absolute path — that record has no
`metadata` object at all. Carrying `.metadata.project` across from one
query to the other returns nothing for every record, which is
indistinguishable from a pattern that genuinely has no spread.

Some hosts' prompt histories, Codex and Grok among them, carry neither
field, so their spread is not countable from a result alone — say so
rather than scoring it zero.

## Cost, and how to not pay it repeatedly

An exhaustive search reads the whole corpus — one measured run covered
916 sources and 402,283 records in about 95 seconds. That is the unit
cost of *one* query. Budget accordingly:

- Run **one** broad exhaustive query and group its results locally,
  rather than one query per skill. A single `"Launching skill:"` sweep
  ranks every skill at once.
- Reach for the slash channel first. It is instant and usually larger.
- Save raw JSON to a scratch file and re-slice it with `jq` instead of
  re-running the search.

Confirm the sweep actually completed before drawing conclusions —
a bounded or partial run looks identical to a genuine absence of
matches.

```console
jq -c '.summary.status, .summary.stats, .summary.coverage' <saved.json>
```

`status.state` must read `complete`. Do not then threshold on
`stats.matched`: it counts results after deduplication and after
`--limit`, so it quietly equals the limit whenever the limit binds and
`state` still reads `complete`. `coverage.matches_seen` counts every
match before either, and is the number a threshold belongs on. In one
measured run the two read 302 and 439 for the same query, and 439 was
the literal occurrence count.

## Query syntax that bites

- Global flags go **before** the subcommand. `agentgrep search --color
  never` is an error; `agentgrep --color never search` is not.
- `depth:exhaustive` as an inline query term is equivalent to
  `--exhaustive`, but the field is a request-wide directive and cannot
  itself be negated or joined by `OR`. Boolean operators elsewhere in
  the query are fine: `depth:exhaustive (a OR b)` runs, while
  `depth:exhaustive a OR b` is a hard error because the bare `OR` takes
  the directive as an operand. Parenthesize, or use the flag.
- Bare terms are AND-combined substrings. `OR`, `NOT`, `( )`, and
  `"exact phrases"` compose. Fields: `agent:`, `model:`, `role:`,
  `timestamp:`, `path:`, `scope:`, `cwd:`, `project:`, `branch:`.
- Default `--scope` is `prompts`. Anything written by the assistant or
  by a tool needs `--exhaustive` to be reachable at all.

## Hosts do not type alike

The slash-command extraction above is a Claude Code shape. Other hosts
record the same intent differently — one measured Codex history held a
single `/plugin:skill` invocation across the whole file, because skills
there get named bare or with a sigil instead. Extract per host, and
when a host's channel comes back near-empty, treat that as "the
extraction does not fit this host" until proven otherwise, never as
"this host does not use skills".

## Redact before anything ships

Corpus results carry the user's absolute paths — project slugs are
derived from them — and prompts quoted as evidence routinely contain
local paths, hostnames, and client or employer names. The repository
forbids all of it in shipped artifacts.

Quote evidence in the report and the proposal, and strip it from
anything that lands: a `SKILL.md`, a commit message, a pull request
body, an issue. Name the pattern and its spread ("recurs across four
language ports") instead of pasting the paths that proved it.
