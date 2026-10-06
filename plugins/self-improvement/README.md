# self-improvement

Mine local agent prompt history for how the skill catalog is really used, then
land the changes that usage evidence supports.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install self-improvement@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add self-improvement@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/self-improvement:sweep [<plugin\|plugin:skill>...]` | `self-improvement:sweep [<plugin\|plugin:skill>...]` | Rank the catalog twice (all-time and current-era), report what gets retyped around it, and save a findings ledger. Edits no skill |
| `/self-improvement:apply [<id>...]` | `self-improvement:apply [<id>...]` | Land the ledger's findings, one gated commit per finding |

`sweep` reports and `apply` acts. Only `apply` edits skills, so only it is
invoked by name.

`/self-improvement:apply` takes `--ledger <path>` (the ledger the sweep
printed; default is the per-worktree one) and `--dry-run` (show the edits and
their gates, write nothing).

## What it looks for

The signal is the text around an invocation, or the absence of one.

A paste is a preamble retyped after the skill name: reference directories, a
tool preference, a quality bar. A continuation asks for a step the skill
stopped short of. An override re-scopes what the skill runs on. Each points at
a different remedy: a default, a terminal step, an argument.

A procedure restated near-verbatim with no skill named is the case for a skill
that does not exist yet. That is the only finding allowed to propose one.

A finding needs at least 5 occurrences across at least 2 projects, in the era
of the catalog you are about to change. It is reported as a ratio against that
skill's invocation count in the same window; the same evidence argues for
opposite remedies at 54% and at 20%.

## Prerequisites

- python3 (standard library only), for `scripts/sweep.py`
- git, for dating rules, mapping renames, and dating each skill's first commit
- the host's session-search tool, or `rg`, to collect skill-tool launches
- optional: `uv`, to run `agentgrep` across other hosts' stores

## Counting and the ledger

`scripts/sweep.py counts` turns a prompt-history file into per-skill counts,
the era split, and project spread. `ledger-save` writes the findings ledger
under the git directory, outside the working tree, and `ledger-verify`
recomputes its key before `apply` edits anything. The key is the sha256 of the
repository `HEAD` and the sorted finding ids and verdicts.

`references/detecting-invocations.md` covers collecting the inputs and the
traps that produce confident wrong answers: invocations are recorded in two
separate places and either alone misreports usage, renames split a skill's
history, a supersession splits it the other way, and a truncated query is
indistinguishable from a genuine absence.

`references/worked-example-spike.md` shows what a finding and its edit look
like.
