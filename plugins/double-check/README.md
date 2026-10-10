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

## Prerequisites

- None
