# respond

Screen review feedback from humans or bots before changing code. Verifies
claims against facts and project decisions. Valid findings become gated,
atomic commits; invalid ones get evidence-backed replies.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install respond@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add respond@skills
```

## Skills

Screen every claim against six gates and emit a ledger of verdicts with
evidence and drafted replies. Changes nothing. In Claude Code:

```text
/respond:check [findings]
```

In Codex:

```text
respond:check [findings]
```

Land accepted findings as gated commits, running the screening first when
needed. In Claude Code:

```text
/respond:action [findings]
```

In Codex:

```text
respond:action [findings]
```

Run the loop to a stated finish: screen, fix, push, watch CI, repeat until
nothing is actionable. In Claude Code:

```text
/respond:goal
```

In Codex:

```text
respond:goal
```

Flags: `--pr=<num>` (collect from a pull request), `--base=<ref>`
(override provenance baseline), `--include-resolved` (screen settled
threads), `--no-fixup` (forward commits only), `--on-fail=skip|stop|ask`
(per-finding gate failure), `--reply` (post drafted replies),
`--max-rounds=<n>`, `--wait=<minutes>`, `--ci-wait=<minutes>`, `--no-push`.

## What gets screened

Six gates, cheapest first, stopping at the first that settles the finding:
locate, truth, provenance, alignment, odds, cost. A misaligned verdict must
cite a written decision, and a remote trigger with non-severe damage is
declined as improbable. The gates are defined in
`references/screening-rubric.md`.

## What a fix is allowed to add

A test only when the branch could plausibly break this again and no
existing test would catch it. A comment only if a reader three years from
now would be worse off without it. No guard for a state the caller
excludes. Every commit report names what was added; an empty list is the
good outcome.

## The loop

`/respond:goal` states its exit condition before the first round: no new
fixes, CI green, and every review agent having weighed in, or the round
cap. Waits for CI and for agents are capped, and missing agents are
reported. It halts rather than working around a failed gate, a rejected
push, a needed rebase, or a verdict needing the author's intent, and it
never merges or force-pushes.

## Verification discovery

The skills read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
required quality checks, and read the CI definitions to learn what a push
verifies (see `references/verification-gates.md`). No tool is hardcoded,
and no more verification is run than each fix needs.

## Prerequisites

- **git** — provenance uses merge-base, diff, log -L, and blame
- **gh** (optional) — enables pull-request feedback, CI watching, and
  review-agent detection

