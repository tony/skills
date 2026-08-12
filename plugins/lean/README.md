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

## Related Plugins

- **`lean`**: For real-time writing guidance or quick, commit-free tidying of working trees.
- **`/slop:scan`**: For repo-wide, commit-based reviews on clean trees.
- **`/pr:deslop`**: For fixing commits about to ship (via autosquash).

## Prerequisites

- None. Reads `AGENTS.md` / `CLAUDE.md` at runtime to match repo voice.
