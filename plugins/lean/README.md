# lean

Writing discipline and cleanup tools for tight, slop-free prose and code.
Keeps slop out of drafts and tidies working trees without commits.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install lean@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add lean@skills
```

Claude Code uses a leading slash (`/lean:…`). Codex omits it (`lean:…`).

## Components

### `lean-writing`

Automatic guidance during writing. Encourages leading with results, stating truth
over journey, and preserving references. Never edits files.

### `/lean:tighten`

Removes slop in-place for files or pasted drafts. Prints diffs but never commits
or pushes.

### `/lean:trim-comments`

Judges code comments and docstrings against three gates — would losing it hurt a
maintainer in three years, would an elite library write it this tersely, will it
stay true without hand-syncing — and deletes or rewrites the failures in place.
Defaults to the files the branch changed; pasted code is trimmed in the reply
with nothing edited. Lists a verdict for every comment, keeps included, and
confirms before editing. Prints a diff, never commits.

## Prerequisites

- None. Reads `AGENTS.md` / `CLAUDE.md` at runtime to match repo voice.
