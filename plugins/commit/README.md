# commit

Create git commits following project conventions with format enforcement
and safety checks.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install commit --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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

1. Gather state: read the branch, status, diffs, untracked files, and recent
   commits. Stop on a non-repository, a detached HEAD, an unfinished merge or rebase, nothing to commit, or
   a branch-convention violation.
2. Analyze changes: review the diff, determine type and scope, check topic
   coherence.
3. Determine staging: respect existing staged files, and auto-stage only if
   nothing is staged. A staged secret, by name or by key content in the diff, stops the run.
4. Draft the commit message: follow `AGENTS.md`/`CLAUDE.md` and recent
   commit styles, with proportional detail and verified version-bump URLs.
5. Commit: retry on pre-commit hook failures, never bypassing the hook.
6. Confirm the result: read back the stored message, committed paths,
   whether any remote-tracking ref holds the commit, and the remaining
   working tree state.

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
recent commits for style matching. Falls back to Conventional Commits
(`type(scope): description`) if no convention is found.

## Safety

- No destructive commands: never runs `git push` or `git reset --hard`.
- No history rewriting: never uses `--amend`, and always creates new commits.
- Secret filtering: never stages `.env`, credentials, or key files, and names any it skips.
- No tool credit: commit messages carry no `Co-Authored-By` trailer, tool footer, or emoji.
- Explicit staging: stages specific files only, never `git add -A`, `git add .`, or `git commit -a`.

## Prerequisites

- git
