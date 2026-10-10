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

The skill reads the repository state, drafts a message in the project's
format, commits what is staged (or stages the non-sensitive changes when
nothing is), and reads the stored commit back. The steps live in
`skills/commit/SKILL.md`.

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
- Secret filtering: `scripts/sensitive.py` refuses sensitive file names (`.env`, key, state, and credential files) and private-key or token content in changed lines, and the skill names any path it skips.
- No tool credit: commit messages carry no `Co-Authored-By` trailer, tool footer, or emoji.
- Explicit staging: stages specific files only, never `git add -A`, `git add .`, or `git commit -a`.

## Prerequisites

- git
