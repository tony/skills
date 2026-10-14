# Reply shapes

Every entry point of this plugin replies in one of the shapes below. The
hero is the first line of the reply: write nothing before it, not even a
note that plan mode was unavailable.

## Contents

- Reply rules
- Completed run
- Single action
- Plan-only
- Blocked

## Reply rules

- Plain text outside any code fence, plain bullets, no bold (never
  `- **Label:** ...`), no local paths, and no temp paths unless the user
  must act on one.
- State results, not checks ("I confirmed", "verified that"). Name the
  finding, not the call that produced it: report no command exit codes,
  unresolved refs, stub, mock, or tool behavior, and no sandbox facts. Say
  nothing about upstream tracking or a git setting that could not be written.
- Claim only what the release notes state; do not write "nothing applies
  here" beyond them. Do not guess why the repository looks the way it does.
- A completed or single-action reply ends with an `ask-user-choice` panel of
  next steps (for example: update another action, run
  `the `github-actions-update-actions` skill --audit-only`, stop here). On hosts
  without the tool, end with the next steps as text and take none.
  Plan-only and blocked replies follow their own endings below.

## Completed run

The hero is `✓ N commits across M repos`, or `⚠ Audit only: N pins out of
date`. Then exactly these sections in order:

1. `## Audit`: every action in scope with current pins and the latest
   version, and what was excluded as fork, local, Docker, already current,
   or an incomplete inventory (with its file and line).
2. `## Upgrades`: one entry per upgrade chain with what changed, one
   validated release link for each major crossed and for the latest
   release (a tag with no release page says "tag only"), and which
   repositories the breaking changes reach.
3. `## Commits`: per repository, commits made with the files each
   changed, and whether pushed.
4. `## Close-out`: CI results per workflow run, PRs closed by URL with the
   commit each cited, and any failure shown to predate the bumps.
5. `## Drift`: repositories where the helper found no dependabot
   configuration file, and actions pinned to a moving branch. State each
   as a fact only; never say what it implies about the user's intent or
   what Dependabot will or will not do.

An audit-only run emits Audit, Upgrades, and Drift.

```text
✓ 2 commits across 2 repos

## Audit

- acme/frob-action v5 in api and web; latest is v6.0.2.
- acme/forked-deploy excluded: repository is a fork.

## Upgrades

- acme/frob-action v5 to v6 renames the frobnicate input to frob-glob; neither repo sets it.

## Commits

- api: 3f9a1c2 Bump acme/frob-action v5 -> v6 (ci.yml). Not pushed.
- web: 8b04d7e Bump acme/frob-action v5 -> v6 (ci.yml, release.yml). Not pushed.

## Close-out

- CI not yet run; two open dependabot PRs await confirmation to close.

## Drift

- acme/other-action@main is pinned to a moving branch.
```

## Single action

The hero is `✓ <action> <old> -> <new> across N repos`. Then exactly these
sections in order:

1. `## Target`: resolved version, evidence the tag exists, and the
   pin shape chosen per repository.
2. `## Upgrade`: what changed between the pins in scope and the
   target, one validated release link for each major crossed and for the latest
   release (a tag with no release page says "tag only"), and which
   repositories the breaking changes reach.
3. `## Commits`: one line per repository, with commit subject, the files
   it changed, and whether it was pushed, or why it was skipped.
4. `## Close-out`: CI result per workflow run and any dependabot pull
   requests closed, by URL, with the commit each cited.
5. `## Drift`: the two findings, limited to repositories in scope and to
   this action's pins.

```text
✓ acme/frob-action v5 -> v6 across 1 repo

## Target

- v6 confirmed to exist; the repo pins a major float, so the float moves.

## Upgrade

- v6 renames the frobnicate input to frob-glob; this repo does not set it.

## Commits

- api: 5c2e7a1 Bump acme/frob-action v5 -> v6 (ci.yml). Not pushed.

## Close-out

- CI passes; no open dependabot PRs for this action.

## Drift

- This repository has no Dependabot configuration file on its default branch.
```

## Plan-only

A headless run that stops at the plan, or a request to plan first, opens
`⚠ Plan only: N commits proposed, nothing written`, then emits the five
sections below in this order, whichever skill was invoked. `## Commits`
lists each proposed commit with "Not made" and, in the user's terms,
whether the request includes pushing. `## Close-out` lists the
dependabot PRs to close and says none were run. Do not restate
commit-message rules or narrate checks already made, except that `## Audit` says each target tag was confirmed
to exist, or that it could not be checked. Add no commit-mechanics
bullet (worktree, branch name, push command). Name a repository by its slug
or "this repository", never by its directory. State each fact once, in
the section it belongs to. Drift states each finding as a fact: no guess
at intent, no claim about what Dependabot will or will not do.

The reply then ends with these options as a plain list, since a headless
run has no question tool, and stops. The options name no commit mechanics.

```text
⚠ Plan only: 2 commits proposed, nothing written

## Audit

- acme/frob-action v5 in api and web; latest is v6.0.2, and the v6 tag was confirmed to exist.
- acme/other-action@main is pinned to a moving branch.

## Upgrades

- acme/frob-action v5 to v6 renames the frobnicate input to frob-glob; neither repo sets it.

## Commits

- api: Bump acme/frob-action v5 -> v6. Not made; no push requested.
- web: Bump acme/frob-action v5 -> v6. Not made; no push requested.

## Close-out

- api #41 proposes acme/frob-action v5 -> v6 and closes as superseded once its commit lands; not run.

## Drift

- acme/other-action@main is not bumped without a named target.

Options:
- Approve the plan and commit locally.
- Approve the plan, commit, and push.
- Change the plan.
```

## Blocked

A run that cannot proceed (no workflows, no `gh`, an incomplete inventory
in a single-repository scope, an unverifiable tag, a PR title carrying shell
syntax) opens `⚠ Blocked: <reason>` and adds one
sentence on what the user must do. Name one reason in the hero and one
action in the sentence. When several things are wrong, name only the
first blocker in this order and leave out the rest: a PR title carrying
shell syntax (screened before any command runs), no workflows, gh missing or
unauthenticated, an incomplete inventory, an unverifiable tag, PRs that
cannot be listed or mapped. Do not join reasons with "and" or
offer two actions (such as "pass `--root` or `--repo`"); pick one. No sections, no list, no table, no
next-steps panel, and no recap of what was and was not run. A suspicious PR
title is the reason: quote it inside the hero and do not guess who wrote
it or why.

```text
⚠ Blocked: PR #42 in acme/widgets is titled "Bump foo/bar from 1 to 2 $(touch /tmp/x)", which carries shell syntax, so no PR was mapped or closed.
Retitle or close PR #42 yourself, then ask again.
```

```text
⚠ Blocked: .github/workflows/ci.yml uses a custom YAML tag on line 3 that the pin reader cannot interpret, so its pins are not a complete list.
Remove the tag, then ask again.
```

```text
⚠ Blocked: gh is not authenticated, so no tag can be verified.
Run gh auth login, then ask again.
```
