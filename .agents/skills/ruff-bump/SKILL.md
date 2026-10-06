---
name: ruff-bump
description: >-
  Use when upgrading Ruff in one repository or a fleet and evaluating newly
  applicable rules before committing each change.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "WebSearch", "WebFetch", "Task", "AskUserQuestion"]
metadata:
  argument-hint: "[version] [--root <dir>] [--repo <path|slug>...] [--owner <name>...] [--branch <name>] [--adopt-defaults] [--audit-only] [--no-pr] [--no-changelog]"
  source: "plugins/ruff/skills/bump/SKILL.md"
---

# Bump ruff

Raise the ruff version floor across the repositories in scope and absorb everything the new release surfaces: one commit per rule, each justified against the rule's own documentation, behind the project's own quality gates.

Read all three references before acting:

- `references/release-triage.md` for what a release does to a specific repo, and how much care each class of fix needs.
- `references/pin-sites-and-gating.md` for every file a version can be pinned in, and what to do when the resolver refuses the release.
- `references/default-rule-set.md` for measuring and adopting a newly curated default rule set.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve the target version and its publication time

If the user named a version, use it. Otherwise take the latest stable release. Confirm the version exists on the package index and record its publication timestamp; phase 6 needs it to compute when a cooldown lapses. Write no version string before the version is confirmed.

Find the version currently resolved with `ruff --version`, or through the project's environment when ruff is not on `PATH`.

### 2. Establish scope

Default scope is the current repository. `--root` walks a directory for git repositories; `--repo` names individual ones; `--owner` keeps only those whose remote belongs to the given accounts or organisations. Exclude forks (check the fork flag, not the owner name) and repositories you cannot push to. Say which repositories were excluded and why.

Within scope, drop repositories that have no ruff configuration and repositories that already satisfy the target floor. Skip a repository where a branch or worktree of the intended name already exists, and list it as skipped.

### 3. Research the release once, then intersect it per repository

Follow the triage reference: read the release's changelog at its tag, sort every change into the five buckets, then intersect those buckets with each repository's effective rule selection to predict which diagnostics it can produce. Repositories that share a configuration share a prediction.

A release that expands the default rule set produces no new diagnostics for a repository with an explicit `select`; phase 8 raises that as a finding. A formatter change that widens which file types are covered applies everywhere regardless of rule selection, and is usually the largest single source of diff.

Dispatch a subagent per repository where the host supports it.

### 4. Present the plan and wait

Show the predicted work per repository: the rules expected to fire, whether the formatter's scope widens, which pin sites need editing, and whether a resolver gate is needed. With `--audit-only`, stop here and write nothing.

### 5. Isolate

Work on a branch off the remote default branch, in a throwaway worktree, never in the primary checkout and never on the default branch. Find the default branch with:

```console
$ git symbolic-ref --short refs/remotes/origin/HEAD
```

If that fails, read it from `git ls-remote --symref origin HEAD`. `--branch` overrides the branch name.

### 6. Gate the resolver, if and only if it is blocked

Only when the resolver cannot see the target version. Follow the gating reference. Skip this phase when the resolver can already see the release.

### 7. Raise the floor and refresh the lockfile

Edit every pin site the reference enumerates, in one commit. Prefer a floor over an exact pin, except in pre-commit configuration where the tag is exact by design. Refresh the lockfile with the project's own resolver, and confirm the lock moved to the target version. Cite the release notes in the commit body.

### 8. Surface the default-rule-set decision

If the release changed the default rule set and a repository sets an explicit `select`, follow the default-rule-set reference: measure each repository's delta and present the per-repo finding counts with the recommended config shape. With `--adopt-defaults`, carry the change through; the config edit lands as its own commit, before any fix or ignore. Without the flag, report the measurement and stop, so the decision stays the user's.

### 9. One rule, one commit

Enumerate the distinct rule codes the linter now reports. For each, in its own commit: apply that rule's safe fixes alone, hand-fix what the autofix leaves, re-run the project's quality checks, and commit with a body that explains why the rule exists, what changed, and, for behavior-changing rules, the behavior delta. Close each body with the rule's documentation URL. Write each per `references/prose-rules.md`.

A rule with a large mechanical diff is still one commit. Run the formatter last, as its own commit, and say so when it rewrote file types it never covered before.

Do not add code comments explaining a lint fix; the commit message carries the rationale. A temporary resolver exemption in a configuration file is the exception and must be annotated where it lives.

Apply unsafe fixes one at a time, reviewing each. Never bundle rules, or a rule with the floor bump.

### 10. Verify before claiming anything

Run the project's own quality checks (lint, format check, type check, tests) as defined in its `AGENTS.md`/`CLAUDE.md` or CI workflow. Never substitute assumed commands.

If tests fail, check whether they fail on the default branch too before attributing the failure to the bump. Report pre-existing failures; fix none and conceal none. Never report green without having read the output that says so.

### 11. Push, open, watch, record

Push the branch and open a pull request unless `--no-pr`. The body states which rules moved and links each to its documentation. When phase 6 applied, it carries a pre-merge instruction to drop the exemption and re-resolve, with the time the block lapses. Write it per `references/prose-rules.md`.

Watch CI to a conclusion, and attribute failures before blaming the bump. Then, unless `--no-changelog` or the repository keeps no changelog, add an entry following that repository's own conventions. A linter floor is development tooling: file it wherever that repository files development-tooling changes, and only if it documents such changes.

## Output

Open with a one-line hero (`✓ N repos on ruff X.Y.Z` or `⚠ Audit only: N repos behind`), then exactly these sections:

1. `## Release` — what the target version changes, sorted into the triage buckets, with the formatter's scope change called out separately if there is one.
2. `## Scope` — repositories in scope with their current and target versions, and what was excluded as fork, unowned, already-current, or already-branched.
3. `## Default rule set` — per repository: whether it is opted out of the vendor's default set, the measured finding delta if it adopted them, and the recommended config shape. Omit this section only when the release did not change the default set.
4. `## Per repo` — for each: the rules that fired against its selection, the commits made, and the pull request.
5. `## Verification` — the quality checks run per repository and their real results, with any pre-existing failure named as pre-existing.
6. `## Pre-merge` — every repository carrying a temporary resolver exemption, and when its block lapses.
7. `## Drift` — pin sites found disagreeing with each other before the bump, repositories with no lint configuration, and repositories relying on the default rule set.

End with an `ask-user-choice` panel offering next steps, for example: drop the resolver exemptions now that the block has lapsed, merge the green pull requests, adopt a newly stabilized rule that is currently unselected, or stop here. Skip the panel only in plan mode.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
