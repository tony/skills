---
name: bump-terraform
description: "Use when updating the Terraform or OpenTofu CLI across module constraints, version-manager files, CI, and images."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "WebSearch", "WebFetch", "AskUserQuestion"]
argument-hint: "[version] [--root-module <dir>...] [--audit-only] [--no-lock] [--no-commit]"
user-invocable: true
disable-model-invocation: true
---

# Bump the Terraform CLI

Move `required_version` across every module that declares one, along
with the version manager files, CI workflows, and images that pin the
same CLI somewhere else.

Follow the phase structure in `../bumping-terraform/SKILL.md`, which
points to the three references this skill relies on. To move a provider,
use `/terraform:bump-provider`.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve the target version

Find the installed CLI version with `terraform -version` or
`tofu -version`, whichever exists. If the user named a version, confirm
it is published. Otherwise list the latest stable releases:

```console
curl -s https://releases.hashicorp.com/terraform/index.json | jq -r '.versions | keys_unsorted[]' | grep -vE 'alpha|beta|rc' | sort -V | tail -3
```

Resolve against OpenTofu's releases instead when `tofu` drives the
repository. Present the latest stable alongside the installed version
and confirm which to write; they often differ. If the release list is
unreachable, resolve the version before writing anything.

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

All pin sites in one commit. Then, unless `--no-lock`, refresh each
root module's lock as a separate commit, since a CLI bump can change the
lock file's own format. With `--no-commit`, leave the working tree alone
and say what would have been committed. Write commit messages and the
report per `../../references/prose-rules.md`.

Verify by initialising each root module and confirming it accepts the
new version, then run the repository's own gates.

## Output

Open with a one-line hero (`✓ terraform <old> -> <new> across N pin
sites` or `⚠ Audit only: N sites disagree`), then exactly these
sections:

1. `## Target` — the resolved version, how it was confirmed, the
   version installed locally, and the changelog link.
2. `## Layout` — root modules and child modules discovered, and which
   tool drives the repository.
3. `## Sites` — every pin found, inside the configuration and outside
   it, and whether each was edited or left alone with the reason.
4. `## Locks` — per root module: whether the lock was refreshed, and
   the platform count tracked before and after.
5. `## Verification` — the gates run and their real results, including
   whether each root module now initialises.
6. `## Drift` — every disagreement found before the bump, and every one
   still outstanding after it.

End with an `AskUserQuestion` panel offering next steps, for example:
converge the root modules still on an older pin, add the version to a
version manager file the repository lacks, align the CI workflow, or
stop here. Skip the panel only in plan mode.
