# double-check

Forces verification requests to return re-derived answers instead of diffs
against prior turns. Includes `align`, which repairs chats that already
hold a revision log.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install double-check --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install double-check@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add double-check@skills
```

Claude Code uses a leading slash (`/double-check:…`). Codex omits it (`double-check:…`).

## Components

- `double-check` skill: triggers when asked to double-check,
  "are you sure", "I don't trust that", to verify your earlier answer,
  or to run an analysis again. The agent re-derives answers directly from
  source artifacts, avoiding revision logs or inherited numbering.
- `/double-check:align` skill: recovers conversations where
  diff-shaped answers already landed. Restates the best analysis rebuilt
  from source without referencing earlier responses. Can re-anchor on a
  narrower question.

## The contract

Both components enforce `references/verification-contract.md`:

- The deliverable is a re-derived answer, not a delta.
- The baseline is the source material, not the transcript.
- Confidence belongs to the claim, never the revision.
- Exception: explicit corrections are stated once if you acted on a
  prior claim.

Beyond pasting the contract into your own rules file, the plugin adds
trigger routing on those request phrases and `align`, which repairs a chat
after a revision-log answer has already landed.

## Measured effect

Measured 2026-10-07 with `claude plugin eval`, 3 runs per arm, with the
plugin against the bare model (graders marked `arm: both` score both arms):

- `01-double-check-retry-cap`: 3/3 runs pass with the plugin, 0/3 without.
  Without it every run failed the standalone-answer judge.
- `04-double-check-adopted-claim`: 3/3 with, 0/3 without. Without it, 2 of 3
  runs failed to tell the user the filed ticket's figure was wrong, and all 3
  failed the judge that the correction stays to one brief sentence.
- Verdict phrases (`overstated`, `still holds`, `as I said earlier`) did not
  appear in any run of either arm on this fixture, so the effect measured here
  is standalone shape and the one-sentence correction, not a drop in those
  phrases.

## Prerequisites

- None
