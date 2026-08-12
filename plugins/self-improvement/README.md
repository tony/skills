# self-improvement

Mine local agent prompt history for how the skill catalog is really used, then
land the changes that usage evidence supports.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install self-improvement@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add self-improvement@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/self-improvement:sweep [<skill>...]` | `self-improvement:sweep [<skill>...]` | Rank the catalog twice — all-time and current-era — and report what gets retyped around it. Changes nothing |
| `/self-improvement:apply [<id>...]` | `self-improvement:apply [<id>...]` | Land the sweep's accepted findings, one gated commit per finding |

`sweep` reports and `apply` acts, the same split as `/respond:check` and
`/respond:action`. Only `apply` edits files, so only it is invoked by name.

`/self-improvement:apply` flags: `--dry-run` (show the edits and their gates,
write nothing).

## What it looks for

The signal is the text around an invocation, or the absence of one.

A **paste** is a preamble retyped after the skill name — reference
directories, a tool preference, a quality bar. A **continuation** asks for a
step the skill stopped short of. An **override** re-scopes what the skill runs
on. Each points at a different remedy: a default, a terminal step, an argument.

A procedure restated near-verbatim with **no** skill named is the case for a
skill that does not exist yet. That is the only finding allowed to propose one.

A finding needs repetition, spread, and currency: several occurrences,
across more than one project, in the era of the catalog you are about
to change. It is reported as a ratio against that skill's invocation
count — the same evidence argues for opposite remedies at 54% and at 20%.

## Prerequisites

- **agentgrep** — read-only search across local agent stores, run as
  `uvx agentgrep`
- **jq** — slicing saved search results
- **git** — dating when a rule entered a skill, mapping renames, and
  dating when each skill first became reachable

## Reading the corpus

`references/corpus-queries.md` documents the measurement method and the traps
that produce confident wrong answers: invocations are recorded in two separate
places and either alone misreports usage, renames split a skill's history,
a supersession splits it the other way, a truncated query is
indistinguishable from a genuine absence, and one exhaustive query
reads the entire corpus.
