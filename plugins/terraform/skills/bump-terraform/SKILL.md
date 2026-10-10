---
name: bump-terraform
description: "Use when updating the Terraform or OpenTofu CLI across module constraints, version-manager files, CI, and images."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
argument-hint: "[version] [--root-module <dir>...] [--audit-only] [--no-lock] [--no-commit]"
disable-model-invocation: true
---

# Bump the Terraform CLI

Move `required_version` across every module that declares one, along
with the version manager files, CI workflows, and images that pin the
same CLI somewhere else.

Follow the conventions in `../bumping-terraform/SKILL.md` (recorded tree
state, script paths, commit message rules, non-interactive defaults,
the plan, stopped and audit-only runs). This skill uses
`../../references/layout-discovery.md`,
`../../references/pin-sites.md`, and
`../../references/lock-and-init.md`. To move a provider, use
`/terraform:bump-provider`.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve the target version

Find the installed CLI version with `terraform -version` or
`tofu -version`, whichever exists. If the user named a version, confirm
it with the by-key command in `../../references/pin-sites.md`. Otherwise list the latest stable releases:

```console
$ curl -fsS https://releases.hashicorp.com/terraform/index.json \
    | jq -r '.versions | keys_unsorted[]' \
    | python3 ../../scripts/lockctl.py stable 3
```

Write the script's absolute path there, per the umbrella's script-path rule.

When `tofu` drives the repository, list OpenTofu's releases with the
command in `../../references/pin-sites.md`. Present the latest stable
alongside the installed version and confirm which to write; they often
differ. If the release list is unreachable and the user named no
version, stop and ask which version to write. When the target crosses a
major version, add the CLI's upgrade guide to the report.

### 2. Discover the layout

Follow `../../references/layout-discovery.md` and record its inventory.
`--root-module` limits the run to the named directories.

### 3. Inventory every pin site

Both kinds, per the pin-sites reference: `required_version` in every
module (the reference searches `.tf`, `.tofu`, `.tf.json`, and `.tofu.json`
before applying the selected tool's file precedence), and the pins outside the configuration (`.terraform-version`,
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
  moves no provider. Compare with `lockctl.py diff` without `--allow`.
  An unqualified pass requires exit 0.
- A non-zero exit (any provider-block change, including checksums) means
  restore the lock from git and report it.
- A CLI bump can change the lock file's header outside provider blocks;
  provider blocks must remain byte-identical unless the user explicitly
  approves checksum loss under the lock reference's exception.
- A root module with no committed lock is skipped and reported: `init`
  there would create a lock and pick providers. Run it only after the
  user approves that outcome.

A failed `init`, or a lock restored for a provider-block change, stops
the run with nothing committed. Leave the pin edits in the
working tree and end with the stopped line (the umbrella has its mid-run
form). The checksum-loss exception never permits a provider version or
constraint to change, and its report must state the approved reduction.

### 8. Verify, then commit

Verify on the working tree before any commit. Confirm each guarded root
module initialised under the new version in the step above. Where `init`
did not run (`--no-lock`, a CLI that does not satisfy the pin, or no
committed lock), report it unverifiable and edit nothing to work around
it. Then run the repository's own gates (`validate`, `tflint`, policy
checks).

Apply [Verification gates](../../references/lock-and-init.md#verification-gates)
to classify failures before publication. When it requires a stop, leave the
edits, commit nothing, and end with the stopped line.

With `--no-commit`, leave the edits in the working tree. Otherwise make
one commit holding the pin edits and any changed lock. Write commit
messages and the report per `../../references/prose-rules.md`.

## Output

Open with a one-line hero (`✓ terraform <old> -> <new> across N pin
sites` or `Audit only: N sites disagree`; `<old>` is the version only when
every pin is exact and equal; otherwise `mixed`, never a range or a
`1.9.x` shorthand). A floor or pessimistic constraint makes `<old>`
`mixed` even when a version-manager file names an exact version. Then these sections in
order:

1. `## Target`: the resolved version, how it was confirmed (registry
   or `<version>, confirmed by you`), and the version installed locally.
   Add a changelog link only after fetching it.
2. `## Layout`: the discovered root modules and child modules (the umbrella
   says when to name the tool).
3. `## Sites`: every existing pin, inside the configuration and outside
   it, and whether each was edited or left alone with the reason. A file
   with no CLI pin is not a pin site; actionable missing pins go in `## Drift`.
4. `## Locks`: per root module: whether the lock was re-initialised or
   skipped (and why), and the `h1:` checksum counts before and after.
   Report platform coverage unverified unless a successful command
   checked the required platform names; counts alone do not prove it.
5. `## Verification`: the gates run and their real results.
6. `## Drift`: actionable missing pins or disagreements not already
   reported in `## Sites`. Omit it when none remain. This section owns a
   CI workflow's missing pin; do not repeat it in `## Sites`. An
   installed-CLI mismatch belongs in `## Locks`, and a pre-existing gate failure
   belongs in `## Verification`.

Name the commit by subject in `## Sites`, never by SHA.
State a root module that could not be initialised in `## Locks` only;
`## Verification` does not repeat it.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ terraform mixed -> 1.14.0 across 2 pin sites

## Target

- 1.14.0, confirmed by you; 1.16.5 installed locally.

## Layout

- Root module: infra/prod.

## Sites

- infra/prod/versions.tf: required_version ~> 1.9.0 to ~> 1.14.0.
- .tool-versions: terraform 1.9.5 to 1.14.0.
- Commit: "Bump Terraform CLI to 1.14.0".

## Locks

- infra/prod: initialization skipped because installed Terraform 1.16.5 does not satisfy ~> 1.14.0; initialization and validation unverified. The lock retains random 3.6.0 with 2 h1 records before and after; platform coverage unverified.

## Verification

- fmt -check passes.
```

A run that cannot proceed ends with the stopped line from
`../bumping-terraform/SKILL.md`, not this shape, and has no
panel and no `Next steps:` list.

End with an `AskUserQuestion` panel offering next steps, for example:
converge the root modules still on an older pin, add the version to a
version manager file the repository lacks, align the CI workflow, or
stop here. Skip the panel only in plan mode. Without a question tool, print the
umbrella's `Next steps:` list and stop.
