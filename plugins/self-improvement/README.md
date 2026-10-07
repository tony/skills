# self-improvement

Mine local agent prompt history for how the skill catalog is really used, then
land the changes that usage evidence supports.

The counter reads Claude Code's prompt history (`~/.claude/history.jsonl`)
and its transcripts. Other hosts keep no per-prompt file in a shape the
script can parse, so they are covered only by `--history` pointed at a file
in the same JSONL shape, or by the optional `agentgrep` route. Skills are
found under `plugins/*/skills/` by default; `--catalog-glob` handles
`skills/` and `.claude/skills/` layouts.

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

Claude Code uses a leading slash (`/self-improvement:…`). Codex omits it (`self-improvement:…`).

## Skills

Rank the catalog twice (all-time and current-era), report what gets retyped
around it, and save a findings ledger. Edits no skill:

```text
/self-improvement:sweep [<plugin|plugin:skill>...]
```

Land the ledger's findings, one gated commit per finding:

```text
/self-improvement:apply [<id>...]
```

`sweep` reports and `apply` acts. Only `apply` edits skills, so only it is
invoked by name.

`/self-improvement:apply` takes `--ledger <path>` (the ledger the sweep
printed; default is the per-worktree one) and `--dry-run` (show the edits and
their gates, write nothing).

## What it looks for

The signal is the text around an invocation, or the absence of one: a paste,
a continuation, an override, or a procedure restated with no skill named.
`skills/sweep/SKILL.md` defines each and the evidence bar a finding must
clear.

## Prerequisites

- python 3.9 or newer (standard library only), for `scripts/sweep.py`
- git, for dating rules, mapping renames, and dating each skill's first commit
- the host's session-search tool, or `rg`, to collect skill-tool launches
- optional: `uv`, to run a pinned `agentgrep` across other hosts' stores, after you confirm the command

## Counting and the ledger

`scripts/sweep.py catalog` dates the skills from git history. `tree-check`
reports uncommitted changes that `apply` must not mix with its edits: tracked
files, and untracked files under the catalog directory.

`counts` turns a prompt-history file into per-skill counts, the era split
(when given `--boundary`), project spread, and, per `--window`, the
numerator and windowed denominator of a finding's ratio. `ledger-save` writes the
findings ledger under the git directory, outside the working tree, and
`ledger-verify` recomputes its key before `apply` edits anything. `autosquash` folds
`fixup!` commits into their targets for the verification pass.

`references/detecting-invocations.md` covers collecting the counter's inputs
and the traps that make a count confidently wrong.

`references/worked-example-spike.md` shows what a finding and its edit look
like.
