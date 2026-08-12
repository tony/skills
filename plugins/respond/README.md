# respond

Respond to review feedback — from a colleague, from Bugbot or
CodeRabbit or Copilot, from a review command run earlier in the session
— by screening every claim before any code moves, fixing what survives
as atomic gated commits, and looping the whole cycle against CI and the
review agents until the pull request goes quiet.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install respond@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add respond@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/respond:check [findings]` | `respond:check [findings]` | Screen every claim against six gates and emit a ledger of fix / defer / decline verdicts with evidence and drafted replies. Changes nothing |
| `/respond:action [findings]` | `respond:action [findings]` | Land the accepted findings, one gated commit each, running the screening first when no ledger covers the current head |
| `/respond:goal` | `respond:goal` | Run the loop to a stated finish — screen, fix, push, watch CI, wait for the review agents, repeat until nothing new is actionable |

Flags: `--pr=<num>` (collect from a pull request), `--base=<ref>`
(override the provenance baseline), `--include-resolved` (screen
settled threads too), `--no-fixup` (forward commits only),
`--on-fail=skip|stop|ask` (per-finding gate failure),
`--reply` (post the drafted replies), `--max-rounds=<n>` and
`--wait=<minutes>` (loop bounds), `--no-push`.

## What gets screened

Six gates, cheapest first, stopping at the first that settles the
finding:

1. **Locate** — tie the claim to a file and symbol, or report it
   unlocatable rather than guessing.
2. **Truth** — is it true of the code as written? Read the code; a
   reviewer's confidence is not evidence, and three bots agreeing is
   one opinion repeated.
3. **Provenance** — did this branch cause it, against the merge-base
   with trunk? Pre-existing findings defer by default.
4. **Alignment** — does it hold against decisions the project already
   made, in AGENTS.md, in the branch's stated purpose, in the design
   the surrounding code encodes? A misaligned verdict must cite a
   written decision, never a preference invented while screening.
5. **Odds** — what trigger does the scenario need, and what damage does
   it do? Severe damage clears at any trigger; a remote trigger with
   non-severe damage is declined as improbable, and the reply states
   the trigger so a reviewer who knows a caller that produces it can
   say so.
6. **Cost** — what does the fix add beyond the fix? Costed against the
   smallest change that works, not the one the reviewer proposed.

## What a fix is allowed to add

Every accepted finding is asked why now and why this, and each fix is
measured by what the next reader inherits:

- **Tests** — added when the branch could plausibly break this again
  *and* no existing test would catch it. Extend a test before adding
  one.
- **Comments** — kept only if a reader three years from now, with no
  memory of the review, would be worse off without the line. Never
  change narration, never review breadcrumbs, and never a ticket,
  issue, or pull-request number in code.
- **Complexity** — no guard for a state the caller excludes, no
  defensive wrapper with no reachable failure mode, no abstraction with
  one caller, no configuration knob nobody asked for.

Every commit report names what was added, and an empty list is the good
outcome.

## The loop

`/respond:goal` states its exit condition before the first round and
measures every round against it: no new fixes, CI green on the current
head, and every review agent on the roster having weighed in on that
head — or the round cap, whichever comes first.

The roster is discovered from what has actually commented on the
repository's pull requests, then from configuration and required
checks. Waiting for agents is bounded, because they have no completion
signal; an agent that never arrives is reported, not waited on.

The loop halts rather than working around a failed gate, a rejected
push, a needed rebase, or a verdict that needs the author's intent. It
never merges, never force-pushes, never resolves a thread, and never
approves on a reviewer's behalf.

## Verification discovery

The skills read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
which quality checks the project requires, and read the CI definitions
to learn what a push verifies for free (see
`references/verification-gates.md`). No test runner, linter, or build
tool is hardcoded, and no more verification is run than each fix needs.

## Prerequisites

- **git** — provenance uses merge-base, diff, log -L, and blame
- **gh** (optional) — enables pull-request feedback, CI watching, and
  review-agent detection; without it, screening works from pasted text
  and the session's own review output
