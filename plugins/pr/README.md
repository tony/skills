# pr

Draft, refresh, rewrite, and review PR descriptions, and draft merge commit
messages, from the branch diff. For slop cleanup of a branch's commits, see
the `slop` plugin.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install pr@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add pr@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/pr` | `pr` | Generate PR description from branch diff |
| `/pr:refresh` | `pr:refresh` | Update PR description to current branch net change, preserving structure |
| `/pr:rewrite` | `pr:rewrite` | Rewrite PR description from scratch, keeping relevant context |
| `/pr:merge-commit` | `pr:merge-commit` | Generate merge commit message from branch diff |
| `/pr:review-pr` | `pr:review-pr` | Review a PR description for structure, proportionality, and brittle details |

## How It Works

- **`/pr`**: Gathers diff/log context, reads conventions (`AGENTS.md`/`CLAUDE.md`,
  templates), applies the section patterns below, and optionally creates the PR via `gh`.
- **`/pr:refresh`**: Stack-aware diff against base, backs up to `pr-backups/` in the git directory,
  updates content while preserving hand-written text/structure, and applies via `gh`.
- **`/pr:rewrite`**: Backs up PR, mines old description for manual context, resolves
  templates, drafts fresh description, and applies via `gh`.
- **`/pr:merge-commit`**: Gathers diff/log, reads conventions, drafts proportional
  message (title-only for small, structured for large), and presents for copying.
- **`/pr:review-pr`**: Fetches PR and diff, evaluates against structure/patterns,
  and reports strengths and specific markdown improvements.

## Arguments

Generate PR description (optional hint):

```text
/pr
/pr fixes the race condition in new_session
```

Refresh/rewrite existing PR (defaults to current branch's PR):

```text
/pr:refresh
/pr:refresh #42
/pr:refresh the retry logic was dropped
/pr:rewrite
/pr:rewrite #42 use .github/PULL_REQUEST_TEMPLATE/feature.md
```

Generate merge commit message (optional hint):

```text
/pr:merge-commit
/pr:merge-commit version bump
/pr:merge-commit breaking change in the session API
```

Review PR:

```text
/pr:review-pr
/pr:review-pr #42
/pr:review-pr https://github.com/owner/repo/pull/42
```

## Section patterns

Generated descriptions use these patterns:
- **`## Summary`**: Bold impact labels
- **`## Changes by area`**: Sub-headings for multi-module changes
- **`## Design decisions`**: Trade-off rationale
- **`## Verification`**: Copyable `rg`/`grep` commands
- **`## Test plan`**: `- [x]` checklists
- **Tables**: For renames, APIs, matrices
- **Before/After**: Code blocks for behavior changes
- **Negative assertions**: Proving unwanted patterns are removed

## PR Templates

`/pr` and `/pr:rewrite` resolve templates in this order: user hint > repo template >
the `/pr` section patterns. `/pr:review-pr` accepts user hints. `/pr:refresh` preserves
existing structure without applying templates.

## Safety

- Never force-pushes or runs destructive git commands.
- Never pushes to main/master.
- `/pr:refresh` and `/pr:rewrite` edit a PR only after you approve the proposal; `/pr` creates one only on request.
- Backs up existing descriptions before editing.
- Stops without changing anything when `gh` is unauthenticated, the PR is missing, or the PR's head branch is not checked out.

## Prerequisites

- **git**: For diff/log.
- **gh**: For PR creation/fetching; run `gh auth login` once.
