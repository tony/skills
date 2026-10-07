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

Claude Code uses a leading slash (`/pr:…`). Codex omits it (`pr:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/pr:pr` | `pr:pr` | Generate PR description from branch diff |
| `/pr:refresh` | `pr:refresh` | Update PR description to current branch net change, preserving structure |
| `/pr:rewrite` | `pr:rewrite` | Rewrite PR description from scratch, keeping relevant context |
| `/pr:merge-commit` | `pr:merge-commit` | Generate merge commit message from branch diff |
| `/pr:review-pr` | `pr:review-pr` | Review a PR description for structure, proportionality, and brittle details |

## How It Works

- `/pr:pr`: Gathers diff/log context against the PR's base or the parent branch of a stacked branch, reads conventions (`AGENTS.md`/`CLAUDE.md`,
  templates), applies the section patterns in `skills/pr/SKILL.md`, and optionally creates the PR via `gh`.
- `/pr:refresh`: Diffs against the PR's own base (a stacked PR diffs against its parent), backs up to `pr-backups/` in the git directory with a `cmp`-checked copy (in a temporary directory when the git directory is not writable), updates content while preserving hand-written text and structure, and applies via `gh` once the PR body is confirmed unchanged since the backup.
- `/pr:rewrite`: Backs up PR, mines old description for manual context, resolves
  templates, drafts fresh description, and applies via `gh`.
- `/pr:merge-commit`: Gathers diff/log, reads conventions, drafts proportional
  message (title-only for small, structured for large), and presents for copying.
- `/pr:review-pr`: Fetches PR and diff, evaluates against structure/patterns,
  and reports strengths and specific markdown improvements.

## Arguments

Generate PR description (optional hint):

```text
/pr:pr
/pr:pr fixes the race condition in new_session
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

## PR Templates

`/pr:pr` and `/pr:rewrite` resolve templates in this order: user hint > repo template >
the `/pr:pr` section patterns. `/pr:review-pr` accepts user hints. `/pr:refresh` preserves
existing structure without applying templates.

## Safety

- Never force-pushes or runs destructive git commands.
- Never pushes to main/master. `/pr:pr` runs `git push -u <remote> <branch>` (the base's remote) only as part of creating a PR you approved.
- `/pr:refresh` and `/pr:rewrite` edit a PR only after you approve the proposal; `/pr:pr` pushes the branch and creates a PR only after you confirm.
- Backs up existing descriptions, verifies the copy, and refuses to edit a PR whose body or title changed since the backup.
- Stops without changing anything when `gh` is unauthenticated, the PR is missing, or the PR's head branch is not checked out.

## Prerequisites

- git: For diff/log.
- python3 (3.9 or newer): For the backup script `/pr:refresh` and `/pr:rewrite` run.
- gh: For PR creation/fetching; run `gh auth login` once.
