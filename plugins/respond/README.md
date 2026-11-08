# respond

Screen review feedback from humans or bots before changing code. Verifies
claims against facts and project decisions. Valid findings become gated,
atomic commits; invalid ones get evidence-backed replies.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install respond --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

Claude Code uses a leading slash (`/respond:…`). Codex omits it (`respond:…`).

## Skills

Screen every claim against six gates and emit a ledger of verdicts with
evidence and drafted replies. Edits no tracked file. In Claude Code:

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

Every skill takes a pull request number or URL to collect feedback from.
Each skill's flags are listed under `$ARGUMENTS contract` in its
`skills/<name>/SKILL.md`; the limits all three share (no force-push, no
resolved threads, no merge) are in `references/report-contract.md`.

## What a fix is allowed to add

A test only when the branch could plausibly break this again and no
existing test would catch it. A comment only if a reader three years from
now would be worse off without it. No guard for a state the caller
excludes. Every commit report names what was added; an empty list is the
good outcome.

## Verification discovery

The skills read AGENTS.md / CLAUDE.md / CONTRIBUTING.md to discover
required quality checks, and read the CI definitions to learn what a push
verifies (see `references/verification-gates.md`). No tool is hardcoded,
and no more verification is run than each fix needs.

## Prerequisites

- **git**: provenance uses merge-base, diff, log -L, and blame
- **gh** (optional): enables pull-request feedback, CI watching, and
  review-agent detection
- **python3** (3.14 or newer): runs the scripts for the ledger digest, base resolution, stash, revert, push, and in `goal` the CI and review-agent waits
