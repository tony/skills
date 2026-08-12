# double-check

Forces verification requests to return re-derived answers instead of diffs
against prior turns. Includes an alignment tool for repairing chats.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install double-check@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add double-check@skills
```

*Note: The skills below use Claude Code's leading slash. Codex uses the
same names without it.*

## Components

- **`double-check` (skill):** Triggers when asked to double-check,
  cross-check, or verify. The agent re-derives answers directly from
  source artifacts, avoiding revision logs or inherited numbering.
- **`/double-check:align` (skill):** Recovers conversations where
  diff-shaped answers already landed. Restates the best analysis rebuilt
  from source without referencing earlier responses. Can re-anchor on a
  narrower question.

## The contract

Both components enforce `references/verification-contract.md`:

- The deliverable is a re-derived answer, not a delta.
- The baseline is the source material, not the transcript.
- Confidence belongs to the claim, never the revision.
- **Exception:** Explicit corrections are stated once if you acted on a
  prior claim.

## Relationship to `lean`

While `lean` keeps drafts free of journey-narration in artifacts,
`double-check` applies this discipline to conversation turns. Explicit
comparison requests are out of scope.

## Prerequisites

- None
