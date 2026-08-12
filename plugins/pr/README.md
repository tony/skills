# pr

Manage gold-standard PR descriptions. Detects AI slop and verbose commits,
resolving them via fixup commits and autosquash.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install pr@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add pr@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/pr` | `pr` | Generate PR description from branch diff |
| `/pr:refresh` | `pr:refresh` | Update PR description to current branch net change, preserving structure |
| `/pr:recut` | `pr:recut` | Rewrite PR description from scratch, keeping relevant context |
| `/pr:merge-commit` | `pr:merge-commit` | Generate merge commit message from branch diff |
| `/pr:review` | `pr:review` | Review PR description against gold-standard patterns |
| `/pr:deslop` | `pr:deslop` | Audit commits for AI slop and verbosity; resolve via fixups/autosquash |

## How It Works

- **`/pr`**: Gathers diff/log context, reads conventions (`AGENTS.md`/`CLAUDE.md`,
  templates), applies gold-standard patterns, and optionally creates PR via `gh`.
- **`/pr:refresh`**: Stacks-aware diff against base, backs up to `.git/pr-backups/`,
  updates content while preserving hand-written text/structure, and applies via `gh`.
- **`/pr:recut`**: Backs up PR, mines old description for manual context, resolves
  templates, drafts fresh description, and applies via `gh`.
- **`/pr:merge-commit`**: Gathers diff/log, reads conventions, drafts proportional
  message (title-only for small, structured for large), and presents for copying.
- **`/pr:review`**: Fetches PR and diff, evaluates against structure/patterns,
  and reports strengths and specific markdown improvements.
- **`/pr:deslop`**: Detects trunk, discovers quality gates, checks commits for slop
  (regex + semantic), writes patches to `.git/deslop/`, and optionally applies
  via rebase/autosquash.

## Arguments

Generate PR description (optional hint):

```
/pr
/pr fixes the race condition in new_session
```

Refresh/recut existing PR (defaults to current branch's PR):

```
/pr:refresh
/pr:refresh #42
/pr:refresh the retry logic was dropped
/pr:recut
/pr:recut #42 use .github/PULL_REQUEST_TEMPLATE/feature.md
```

Generate merge commit message (optional hint):

```
/pr:merge-commit
/pr:merge-commit version bump
/pr:merge-commit breaking change in the session API
```

Review PR:

```
/pr:review
/pr:review #42
/pr:review https://github.com/owner/repo/pull/42
```

Audit branch for slop:

```
/pr:deslop
/pr:deslop --apply-patches
/pr:deslop --apply-rebase --run-tests
/pr:deslop --message-only --budget=strict
/pr:deslop --force-rewrite-pushed --apply-rebase
```

Defaults to **audit-only** (writes patches to `.git/deslop/`). Use `--apply-patches`
for fixups or `--apply-rebase` for autosquash. See `plugins/pr/skills/deslop/SKILL.md`
for flags.

## Gold-Standard Patterns

Generated descriptions use patterns from high-quality open-source PRs:
- **`## Summary`**: Bold impact labels
- **`## Changes by area`**: Sub-headings for multi-module changes
- **`## Design decisions`**: Trade-off rationale
- **`## Verification`**: Copyable `rg`/`grep` commands
- **`## Test plan`**: `- [x]` checklists
- **Tables**: For renames, APIs, matrices
- **Before/After**: Code blocks for behavior changes
- **Negative assertions**: Proving unwanted patterns are removed

## PR Templates

`/pr` and `/pr:recut` resolve templates in this order: user hint > repo template >
gold-standard structure. `/pr:review` accepts user hints. `/pr:refresh` preserves
existing structure without applying templates.

## Safety

- Never force-pushes or runs destructive git commands.
- Never pushes to main/master.
- Always presents before modifying.
- Backs up existing descriptions before editing.

## Prerequisites

- **git**: For diff/log.
- **gh**: For PR creation/fetching.
