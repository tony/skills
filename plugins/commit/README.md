# commit

Create git commits following project conventions with format enforcement
and safety checks.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install commit@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add commit@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/commit` | `commit` | Analyze changes, draft a conventional commit message, and commit |

## How It Works

1. **Analyze changes** — Review diff, determine type/scope, check topic
   coherence.
2. **Determine staging** — Respect existing staged files. Auto-stage
   only if nothing is staged. Excludes secrets.
3. **Draft commit message** — Follow `AGENTS.md`/`CLAUDE.md` and recent
   commit styles. Apply guidelines: proportional detail, version bump
   URLs, before/after patterns.
4. **Commit** — Execute the commit. Handle and retry on pre-commit hook
   failures.
5. **Confirm result** — Show the created commit and remaining working
   tree state.

## Arguments

Pass an optional hint to influence the commit description:

```
/commit fix the auth bug
/commit add retry logic to the API client
```

The hint supplements auto-detection — the project's commit format is
always enforced.

## Commit Format Detection

Reads `AGENTS.md` and `CLAUDE.md` to discover conventions. Inspects the
last 10 commits for style matching. Falls back to Conventional Commits
(`type(scope): description`) if no convention is found.

## Safety

- **No destructive commands** — Never runs `git push` or `git reset
  --hard`.
- **No history rewriting** — Never uses `--amend`; always creates new
  commits.
- **Secret filtering** — Never stages `.env`, credentials, or key files.
- **Explicit staging** — Stages specific files only; never uses
  `git add -A` or `git add .`.
- **Heredoc formatting** — Used for multi-line commit messages.

## Prerequisites

- **git**
