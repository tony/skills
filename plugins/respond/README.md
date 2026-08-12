# respond

Screen review feedback from humans or bots before changing code. Verifies
claims against facts and project decisions. Valid findings become gated,
atomic commits; invalid ones get evidence-backed replies.

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
| `/respond:check [findings]` | `respond:check [findings]` | Screen every claim against six gates and emit a ledger of verdicts with evidence and drafted replies. Changes nothing |
| `/respond:action [findings]` | `respond:action [findings]` | Land accepted findings as gated commits, running the screening first when needed |
| `/respond:goal` | `respond:goal` | Run the loop to a stated finish — screen, fix, push, watch CI, repeat until nothing is actionable |

Flags: `--pr=<num>` (collect from a pull request), `--base=<ref>`
(override provenance baseline), `--include-resolved` (screen settled
threads), `--no-fixup` (forward commits only), `--on-fail=skip|stop|ask`
(per-finding gate failure), `--reply` (post drafted replies),
`--max-rounds=<n>`, `--wait=<minutes>`, `--no-push`.

## What gets screened

Six gates, cheapest first, stopping at the first that settles the finding:

1. **Locate** — tie the claim to a file and symbol, or report it unlocatable.
2. **Truth** — is it true of the code as written? Confidence is not evidence.
3. **Provenance** — did this branch cause it? Pre-existing findings defer
   by default.
4. **Alignment** — does it hold against decisions in AGENTS.md, the branch's
   purpose, or the surrounding code's design? Misaligned verdicts must cite a
   written decision.
5. **Odds** — what trigger does the scenario need, and what damage does it do?
   A remote trigger with non-severe damage is declined as improbable.
6. **Cost** — what does the fix add beyond the fix? Costed against the
   smallest change that works.

## What a fix is allowed to add

Every accepted finding is asked why now and why this:

- **Tests** — added when the branch could plausibly break this again
  *and* no existing test would catch it. Extend before adding.
- **Comments** — kept only if a reader three years from now would be
  worse off without the line. No breadcrumbs, no ticket numbers.
- **Complexity** — no guard for a state the caller excludes, no
  defensive wrapper with no reachable failure mode.

Every commit report names what was added; an empty list is the good outcome.

## The loop

`/respond:goal` states its exit condition before the first round and
measures against it: no new fixes, CI green, and every review agent
having weighed in — or the round cap, whichever comes first.

The roster is discovered from pull requests, configuration, and required
checks. Waiting for agents is bounded; missing agents are reported.

The loop halts rather than working around a failed gate, a rejected push,
a needed rebase, or a verdict needing the author's intent. It never merges
or force-pushes.

## Verification discovery

The skills read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
required quality checks, and read the CI definitions to learn what a push
verifies (see `references/verification-gates.md`). No tool is hardcoded,
and no more verification is run than each fix needs.

## Prerequisites

- **git** — provenance uses merge-base, diff, log -L, and blame
- **gh** (optional) — enables pull-request feedback, CI watching, and
  review-agent detection

