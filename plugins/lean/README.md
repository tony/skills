# lean

Writing discipline and cleanup tools for tight, slop-free prose and code.
Keeps slop out of drafts and tidies working trees without commits.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install lean --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install lean@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add lean@skills
```

Claude Code uses a leading slash (`/lean:…`). Codex omits it (`lean:…`).

## Components

### `lean-writing`

Automatic guidance during writing. Encourages leading with results, stating truth
over journey, and preserving references. Never edits files.

### `/lean:tighten`

Removes slop in place from files after you confirm; pasted drafts are printed
tightened and edit nothing. Prints diffs but never commits or pushes.

### `/lean:trim-comments`

Judges code comments and docstrings against the three gates in the comment
policy and deletes or rewrites the failures in place. Defaults to comments on
lines the branch added or changed; pasted code is trimmed in the reply with
nothing edited. Lists a verdict for every comment, keeps included, and
confirms before editing. Prints a diff, never commits.

## Prerequisites

- `python3` (3.9 or newer) runs `scripts/scope.py` for both editing skills and `scripts/tally.py` for `trim-comments`.
- Reads `AGENTS.md` / `CLAUDE.md` at runtime to match repo voice.
