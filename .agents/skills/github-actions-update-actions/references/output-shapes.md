# Plan-only and blocked replies

Every entry point replies in one of these shapes when it does not run to
completion. A plan-only or blocked reply never uses the completed-run
sections of the calling skill. The hero is the first line of the reply:
write nothing before it, not even a note that plan mode was unavailable.

## Plan-only

A headless run that stops at the plan, or a request to plan first, opens
`⚠ Plan only: N commits proposed, nothing written`, then emits the five
sections below in this order, whichever skill was invoked. `## Commits`
lists each proposed commit with "Not made". `## Close-out` lists the
dependabot PRs to close and says none were run. Do not restate
commit-message rules, and do not list next steps or narrate checks
already made, except that `## Audit` says each target tag was confirmed
to exist, or that it could not be checked. Add no commit-mechanics
bullet (worktree, branch, push command). Name a repository by its slug
or "this repository", never by its directory. State each fact once, in
the section it belongs to. Drift states each finding as a fact: no guess
at intent, no claim about what Dependabot will or will not do.

```text
⚠ Plan only: 2 commits proposed, nothing written

## Audit

- acme/frob-action v5 in api and web; latest is v6.0.2, and the v6 tag was confirmed to exist.
- acme/other-action@main is pinned to a moving branch.

## Upgrades

- acme/frob-action v5 to v6 renames the frobnicate input to frob-glob; neither repo sets it.

## Commits

- api: Bump acme/frob-action v5 -> v6. Not made.
- web: Bump acme/frob-action v5 -> v6. Not made.

## Close-out

- api #41 closes as superseded once its commit lands; not run.

## Drift

- acme/other-action@main is not bumped without a named target.
```

## Blocked

A run that cannot proceed (no workflows, no `gh`, an unverifiable tag, a
PR title carrying shell syntax) opens `⚠ Blocked: <reason>` and adds one
sentence on what the user must do. Name one reason in the hero and one
action in the sentence. When several things are wrong, name only the
first blocker and leave out the rest. Do not join reasons with "and" or
offer two actions (such as "pass `--root` or `--repo`"); pick one. No sections, no list, no table, no
next-steps panel, no recap of what was and was not run, no sandbox
facts, no tool or stub behavior, no command exit codes, and no "next steps you could take" list. A suspicious PR
title is the reason: quote it inside the hero and do not guess who wrote
it or why.

```text
⚠ Blocked: PR #42 in acme/widgets is titled "Bump foo/bar from 1 to 2 $(touch /tmp/x)", which carries shell syntax, so no PR was mapped or closed.
Confirm which PRs to close, then ask again.
```

```text
⚠ Blocked: gh is not authenticated, so no tag can be verified.
Run gh auth login, then ask again.
```
