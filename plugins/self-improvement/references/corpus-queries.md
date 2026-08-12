# Reading the Corpus

How `/self-improvement:sweep` gets usage facts out of local agent
history with `agentgrep`, and the traps that produce confident wrong
answers. Every number below was measured, not estimated; re-measure
rather than trusting these figures, which are here to show the shape
of the problem.

## Two channels, and neither one is the census

A skill gets invoked two different ways, recorded in two different
places, and a census built on one of them is wrong.

**Typed slash commands** live in the host's prompt history —
`~/.claude/history.jsonl`, one JSON object per line with a `.display`
field. Cheap: no search, just `jq` and `rg`.

```console
jq -r 'select(.display != null) | .display' ~/.claude/history.jsonl | rg -o '^/[a-z0-9-]+:[a-z0-9-]+' | sed 's|^/||' | sort | uniq -c | sort -rn
```

**Skill-tool invocations** emit a `Launching skill: <plugin>:<skill>`
line into the conversation transcript. These are *not* in prompt
history, so a default-depth search finds nothing — `--exhaustive` is
mandatory.

```console
uvx agentgrep --color never search --exhaustive '"Launching skill:"' --limit 2000 --no-progress --json
```

The two disagree violently. In one measured run the slash channel held
2,416 invocations and the tool channel 230, and `merge-pr:this` scored
44 in the first and 0 in the second. **A skill is only "unused" when
it is absent from both.** Reporting from the tool channel alone
recommends deleting heavily used skills.

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
predecessor's history either way. Sum across every name a skill has
had before applying any threshold.

## Spread, not just repetition

The evidence bar is repetition **and** spread: a pattern confined to
one project is that project's quirk. Both search channels encode the
originating project in the result path, so spread is countable.

```console
uvx agentgrep --color never search --exhaustive '<pattern>' --limit 500 --no-progress --json | jq -r '[.. | objects | select(has("path")) | .path] | .[]' | rg -o '/projects/[^/]+' | sort -u | wc -l
```

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

`status.state` must read `complete`. `stats.matched` is the exact
count, which is what a threshold should be applied to.

## Query syntax that bites

- Global flags go **before** the subcommand. `agentgrep search --color
  never` is an error; `agentgrep --color never search` is not.
- `depth:exhaustive` as an inline query term is equivalent to
  `--exhaustive`, but it is a request-wide directive: combining it with
  `OR` or negation is a hard error. Use the flag when the query needs
  boolean operators.
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
