# commit

Create git commits following project conventions with format enforcement
and safety checks.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install commit@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add commit@skills
```

Claude Code uses a leading slash (`/commit:…`). Codex omits it (`commit:…`).

## Skills

`/commit:commit` in Claude Code, `commit:commit` in Codex: analyze changes,
draft a conventional commit message, and commit.

## How It Works

1. Analyze changes: review the diff, determine type and scope, check topic
   coherence.
2. Determine staging: respect existing staged files, and auto-stage only if
   nothing is staged. A staged secret stops the run.
3. Draft the commit message: follow `AGENTS.md`/`CLAUDE.md` and recent
   commit styles, with proportional detail and verified version-bump URLs.
4. Commit: retry on pre-commit hook failures, never bypassing the hook.
5. Confirm the result: show the created commit and the remaining working
   tree state.

## Arguments

Pass an optional hint to influence the commit description:

```text
/commit:commit fix the auth bug
```

```text
/commit:commit add retry logic to the API client
```

The hint supplements auto-detection, and the project's commit format is
always enforced.

## Commit Format Detection

Reads `AGENTS.md` and `CLAUDE.md` to discover conventions. Inspects the
last 10 commits for style matching. Falls back to Conventional Commits
(`type(scope): description`) if no convention is found.

## Safety

- No destructive commands: never runs `git push` or `git reset --hard`.
- No history rewriting: never uses `--amend`, and always creates new commits.
- Secret filtering: never stages `.env`, credentials, or key files, and names any it skips.
- No tool credit: commit messages carry no `Co-Authored-By` trailer, tool footer, or emoji.
- Explicit staging: stages specific files only, never `git add -A`, `git add .`, or `git commit -a`.

## Prerequisites

- git
