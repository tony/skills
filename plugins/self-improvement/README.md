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

`scripts/sweep.py catalog` lists skills with birth dates, the rename map, and
the era boundary. `tree-check` reports uncommitted changes that `apply` must
not mix with its edits; it covers tracked files and untracked files under
`plugins/`.

`counts` turns a prompt-history file into per-skill counts, the era split
(when given `--boundary`), and project spread. `ledger-save` writes the
findings ledger under the git directory, outside the working tree, and
`ledger-verify` recomputes its key before `apply` edits anything. The key is
the sha256 of the repository `HEAD` and each finding's id, verdict, skill,
and expected change, the fields `apply` acts on. `autosquash` folds
`fixup!` commits into their targets for the verification pass.

`references/detecting-invocations.md` covers collecting the counter's inputs
and the traps that make a count confidently wrong.

`references/worked-example-spike.md` shows what a finding and its edit look
like.

## Observed yield

One read-only run of `counts` on 2026-10-07 against this catalog (109
skills) and one machine's Claude Code history, with the scratch files in a
temporary directory:

- Scanned 23,465 prompt-history records (2025-09-27 to 2026-10-07) and 379
  skill-tool launch lines from 6,471 transcripts modified in the last 90
  days. Both channels read complete.
- The era boundary was 2026-10-05, the day all 109 skills were born. Three
  slash invocations fell after it and no skill reached the 10 needed for a
  ratio.
- Findings meeting the bar (5 occurrences, 2 projects, 90 days, current
  era): 0.

A freshly rebuilt catalog yields nothing until its new skills accumulate
invocations; the bar withholds a finding rather than lower itself.
