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

Follow the conventions in the `terraform-bumping-terraform` skill (recorded tree
state, script paths, commit message rules, non-interactive defaults,
the plan, stopped and audit-only runs). This skill uses
`references/layout-discovery.md`,
`references/pin-sites.md`, and
`references/lock-and-init.md`. To move a provider, use
the `terraform-bump-provider` skill.

User arguments: $ARGUMENTS

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

Write the script's absolute path there, per the umbrella's script-path rule.

When `tofu` drives the repository, list OpenTofu's releases with the
command in `references/pin-sites.md`. Present the latest stable
alongside the installed version and confirm which to write; they often
differ. If the release list is unreachable and the user named no
version, stop and ask which version to write. When the target crosses a
major version, add the CLI's upgrade guide to the report.

### 2. Discover the layout

Follow `references/layout-discovery.md` and record its inventory.
`--root-module` limits the run to the named directories.

### 3. Inventory every pin site

Both kinds, per the pin-sites reference: `required_version` in every
module (the reference's `git grep` lists them across `.tf`, `.tofu`, and `.tf.json`), and the pins outside the configuration (`.terraform-version`,
`.tool-versions`, `mise.toml`, `.mise/config.toml`, workflow files, image tags, devcontainer
configuration, Makefile variables, `atlantis.yaml`, `.pre-commit-config.yaml`).
With `--root-module`, apply the umbrella's scope rule to roots outside it
that call a child module whose `required_version` you would edit.

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

Per the umbrella's Orchestration Plan, show every site to be edited with the form it keeps, every site left
alone with the reason, the drift found, and whether lock files will be
refreshed. Warn when the installed CLI cannot satisfy the new
`required_version`: `init` will not run and the roots will be unverifiable. With `--audit-only`, stop here and write nothing.

### 7. Edit and re-initialise

Edit all pin sites, committing nothing yet. Unless `--no-lock`, check
that the installed CLI satisfies the new `required_version`; if it does
not, skip `init`, report it unverifiable, and name the installed version.

Otherwise re-run `init` in each root module that has a committed,
unmodified lock:

- Use plain `init` per the lock reference, never `-upgrade`: a CLI bump
  moves no provider, so `lockctl.py diff` with no `--allow` must exit 0.
- A non-zero exit (a version change or a platform count drop) means
  restore the lock from git and report it.
- A CLI bump can change the lock file's own format; that change is part
  of the commit.
- A root module with no committed lock is skipped and reported: `init`
  there would create a lock and pick providers. Run it only after the
  user approves that outcome.

A failed `init`, or a lock restored for a version change or dropped
count, stops the run with nothing committed. Leave the pin edits in the
working tree and end with the stopped line (the umbrella has its mid-run
form). A dropped count is committed only with the user's explicit yes.

### 8. Verify, then commit

Verify on the working tree before any commit. Confirm each guarded root
module initialised under the new version in the step above. Where `init`
did not run (`--no-lock`, a CLI that does not satisfy the pin, or no
committed lock), report it unverifiable and edit nothing to work around
it. Then run the repository's own gates (`validate`, `tflint`, policy
checks).

A gate that fails on a file this run edited, or that the bump plausibly
caused, is a mid-run stop: leave the edits, commit nothing, and end with
the stopped line. A failure in code the run did not touch is
pre-existing; report it as such and carry on.

With `--no-commit`, leave the edits in the working tree. Otherwise make
one commit holding the pin edits and any changed lock. Write commit
messages and the report per `references/prose-rules.md`.

## Output

Open with a one-line hero (`✓ terraform <old> -> <new> across N pin
sites` or `Audit only: N sites disagree`; `<old>` is the version the pins
agreed on, or `mixed` when they disagreed), then these sections in
order:

1. `## Target`: the resolved version, how it was confirmed (registry
   or "confirmed by you" with no reason), the version installed locally, and the
   changelog link (or that none was confirmed).
2. `## Layout`: root modules and child modules discovered (the umbrella
   says when to name the tool).
3. `## Sites`: a list of every pin found, inside the configuration and outside
   it, and whether each was edited or left alone with the reason.
4. `## Locks`: per root module: whether the lock was re-initialised or
   skipped (and why), and the platform count tracked before and after.
5. `## Verification`: the gates run and their real results, including
   whether each root module now initialises.
6. `## Drift`: every disagreement found before the bump, and every one
   still outstanding after it. Omit it when nothing disagreed.

Name the commit by subject in `## Sites`, never by SHA.
State a root module that could not be initialised in `## Locks` only;
`## Verification` does not repeat it. `## Drift` states nothing
`## Sites` already says.

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
stop here. Skip the panel only in plan mode. Without a question tool, print the
umbrella's `Next steps:` list and stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
