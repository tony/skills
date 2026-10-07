---
name: terraform-bump-terraform
description: >-
  Use when updating the Terraform or OpenTofu CLI across module constraints,
  version-manager files, CI, and images.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[version] [--root-module <dir>...] [--audit-only] [--no-lock] [--no-commit]"
  source: "plugins/terraform/skills/bump-terraform/SKILL.md"
---

# Bump the Terraform CLI

Move `required_version` across every module that declares one, along
with the version manager files, CI workflows, and images that pin the
same CLI somewhere else.

Follow the phase structure and conventions in
the `terraform-bumping-terraform` skill (recorded tree state, commit
message rules, non-interactive defaults, stopped and audit-only runs), which names the references this
skill uses. To move a provider, use the `terraform-bump-provider` skill.

User arguments: $ARGUMENTS

`references/lockctl.py` resolves from this skill's directory: print its absolute path once and write that path literally in each command, since shell variables do not persist between Bash calls.

## Procedure

### 1. Resolve the target version

Find the installed CLI version with `terraform -version` or
`tofu -version`, whichever exists. If the user named a version, confirm
it with the by-key command in `references/pin-sites.md`. Otherwise list the latest stable releases:

```console
$ curl -fsS https://releases.hashicorp.com/terraform/index.json \
    | jq -r '.versions | keys_unsorted[]' \
    | python3 references/lockctl.py stable 3
```

The fence shows the `../../scripts/` form; write the absolute path.

When `tofu` drives the repository, list OpenTofu's releases with the
command in `references/pin-sites.md`. Present the latest stable
alongside the installed version and confirm which to write; they often
differ. If the release list is unreachable and the user named no
version, stop and ask which version to write. When the target crosses a
major version, add the CLI's upgrade guide to the report.

### 2. Discover the layout

Run the umbrella's discovery phase. `--root-module` limits the run to the
named directories.

### 3. Inventory every pin site

Both kinds, per the pin-sites reference: `required_version` in every
module, and the pins outside the configuration (`.terraform-version`,
`.tool-versions`, `mise.toml`, workflow files, image tags, devcontainer
configuration, Makefile variables).

### 4. Report the drift before overwriting it

Root modules that disagree about the CLI, a version manager file that
contradicts the configuration, CI installing a third version: surface
all of it as a finding first. An exact `required_version` is a hard gate
(see the pin-sites reference), so root modules that disagree cannot all
be run from one machine.

When they disagree, ask: converge every root module on the target, or
move only the selected ones and report the rest as outstanding drift.

### 5. Distinguish root modules from reusable ones

Root modules keep their existing shape: an exact pin stays exact, a
pessimistic constraint stays pessimistic. Reusable modules keep floors,
per the pin-sites reference; say why in the commit body when you move
one.

### 6. Present the plan and wait

Show every site to be edited with the form it keeps, every site left
alone with the reason, the drift found, and whether lock files will be
refreshed. With `--audit-only`, stop here and write nothing.

### 7. Edit, commit, verify

All pin sites in one commit. Then, unless `--no-lock`, re-run `init` in
each root module that has a committed, unmodified lock, as a separate
commit if the lock changes (a CLI bump can change the lock file's own
format). Use plain `init` per the lock reference, never `-upgrade`: a CLI
bump moves no provider, so any version change in `lockctl.py state`
means restore the lock from git and report it. A lock whose platform
count dropped is restored the same way and never committed without the
user's explicit yes (headless: restore it, leave it out, and stop). A root module with no
committed lock is skipped and reported: `init` there would create a lock
and pick providers. Run it only after the user approves that outcome.
With `--no-commit`, leave the working tree alone and say what would have
been committed. Write commit messages and the
report per `references/prose-rules.md`.

Verify by initialising each guarded root module and confirming it
accepts the new version, but only when the installed CLI satisfies the
new `required_version` and `--no-lock` is absent (`init` writes the
lock). Otherwise report init as unverifiable (skipped lock-less modules
included), name the installed version, and edit nothing to work around
it. Then run the repository's own gates.

## Output

Open with a one-line hero (`✓ terraform <old> -> <new> across N pin
sites` or `Audit only: N sites disagree`), then these sections in
order:

1. `## Target`: the resolved version, how it was confirmed (registry
   or "confirmed by you"), the version installed locally, and the
   changelog link (or that none was confirmed).
2. `## Layout`: root modules and child modules discovered, and which
   tool drives the repository.
3. `## Sites`: a list of every pin found, inside the configuration and outside
   it, and whether each was edited or left alone with the reason.
4. `## Locks`: per root module: whether the lock was re-initialised or
   skipped (and why), and the platform count tracked before and after.
5. `## Verification`: the gates run and their real results, including
   whether each root module now initialises.
6. `## Drift`: every disagreement found before the bump, and every one
   still outstanding after it. Omit it when nothing disagreed.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ terraform 1.14.5 -> 1.15.8 across 4 pin sites

## Target

- 1.15.8 confirmed on releases.hashicorp.com; 1.15.8 installed locally; changelog linked at v1.15.8.

## Sites

- envs/prod/versions.tf, .tool-versions, and the Dockerfile image tag edited.
- .github/workflows/plan.yml pinned 1.14.0, a third version, and was edited.

## Locks

- envs/prod: re-initialised, versions unchanged, 3 platforms before and after.
- envs/staging: no committed lock, skipped.

## Verification

- envs/prod initialises under 1.15.8; fmt -check passes.
```

A run that cannot proceed ends with the stopped line from
the `terraform-bumping-terraform` skill, not this shape.

End with an `ask-user-choice` panel offering next steps, for example:
converge the root modules still on an older pin, add the version to a
version manager file the repository lacks, align the CI workflow, or
stop here. Skip the panel only in plan mode. Without a question tool, list the
options and take the default: stop here.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
