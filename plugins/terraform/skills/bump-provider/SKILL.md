---
name: bump-provider
description: "Use when updating one Terraform or OpenTofu provider across modules and refreshing root lockfiles without losing platforms."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
argument-hint: "<provider> [version] [--root-module <dir>...] [--audit-only] [--no-lock] [--no-commit]"
disable-model-invocation: true
---

# Bump a Terraform provider

Raise a provider's version across every module that declares it and
refresh the lock file of every affected root module, all in one commit.

Follow the conventions in `../bumping-terraform/SKILL.md` (recorded tree
state, script paths, commit message rules, non-interactive defaults,
the plan, stopped and audit-only runs). This skill uses
`../../references/layout-discovery.md`,
`../../references/pin-sites.md`, and
`../../references/lock-and-init.md`. To move the CLI, use
`/terraform:bump-terraform`. To refresh locks within existing constraints,
use `/terraform:refresh-lock`.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve which provider

The argument may be a full source address or a bare name. List the
source addresses the repository declares:

```console
$ git grep \
    -n -E \
    -e '^[[:space:]]*source[[:space:]]*=' \
    -e '"source"[[:space:]]*:' \
    -- '*.tf' '*.tofu' '*.tf.json' '*.tofu.json'
```

Apply the selected tool's file precedence from the layout reference.
The list mixes provider and module sources, and each hit names its file
and line. Keep only hits inside a `required_providers` block: read the
file around the line to tell. As a first cut, a provider address has two
segments (`hashicorp/aws`) or three with a hostname first
(`registry.example.com/acme/thing`); a registry module also has three
(`terraform-aws-modules/vpc/aws`), and a local path or `git::` URL is
always a module. Resolve the argument against the provider addresses. If
more than one matches, ask which.

With no provider argument, list the declared provider addresses and ask
which to move; headless, stop. A name that matches nothing declared is a
finding, not a typo to correct silently: end the run with the stopped
line.

### 2. Discover the layout and settle the ambiguities

Follow `../../references/layout-discovery.md` and record its inventory.
`--root-module` limits the run to the named directories.

### 3. Resolve the target version

- A named version: confirm it with the exact-entry command in
  `../../references/pin-sites.md`. Otherwise take the latest stable
  release.
- Query the registry's metadata for that exact version and record its
  tag, publication date, and source repository; never use the
  latest-only endpoint.
- Build the changelog link from that source at the tag, in the form the
  reference gives, and fetch it before linking. Include only metadata
  and links supported by fetched sources.
- When the target crosses a major version, add the provider's upgrade
  guide.

### 4. Inventory the sites and predict the edits

Every module declaring this provider, root and child, per the pin-sites
reference. The affected root modules are the roots that declare it plus
the roots that call a declaring child module, mapped per the
layout-discovery reference. Decide per site whether it needs editing at all.
With `--root-module`, apply the umbrella's scope rule to roots outside it
that call an edited child module.

### 5. Present the plan and wait

Per the umbrella's Orchestration Plan, show the sites to be edited with the operator each keeps, the sites left
alone with the reason, the lock files to be refreshed with each provider's
`h1:` count and declared platform names, and any drift found. With `--audit-only`, stop
here and write nothing.

### 6. Edit the constraints

Edit every constraint in the plan and commit nothing yet: constraints
and locks land together or not at all. Write commit messages per
`../../references/prose-rules.md`.

### 7. Refresh the locks

Unless `--no-lock`, refresh each affected root module's lock.

- Move only the bumped provider: use the lock reference's "Moving one
  provider" steps, never `init -upgrade`.
- When the user named a version that the constraint allows to be
  exceeded, follow its "Landing a version the user named" steps so the
  lock holds exactly that version.
- A root module with no committed lock is skipped and reported, since
  `init` would create one; run it there only after the user approves.
- A failed `init` restores the lock from git.
- Check the declared platforms with `providers lock`, naming the bumped
  provider, per the lock reference. Compare each lock with `lockctl.py diff`,
  passing the bumped provider to `--allow`, and recover a dropped `h1:`
  count using the required platform names.
- A lock with fewer `h1:` records is committed only with the user's explicit
  yes to that file. Equal counts alone do not prove platform coverage.

Any lock that fails, or keeps fewer `h1:` records without that yes
(headless: always), stops the run with nothing committed. Restore that
lock from git, leave every constraint edit in the working tree, and end
with the stopped line (the umbrella has its mid-run form).

### 8. Verify, then commit

Verify on the working tree before any commit. Read the selected version
back out of each lock file and compare it to the target; a different
version is an overshoot to report, not a pass. `lockctl.py diff` exiting
non-zero names any other provider that changed or any count that dropped;
report it. Run the repository's own gates (`validate`, `tflint`, policy
checks).

Apply [Verification gates](../../references/lock-and-init.md#verification-gates)
to classify failures before publication. When it requires a stop, leave the
edits, commit nothing, and end with the stopped line.

With `--no-commit`, leave everything in the working tree. Otherwise make
one commit holding the constraint edits and the refreshed locks. Report
root modules that did not move, and why.

## Output

Open with a one-line hero (`✓ <provider> <old> -> <new> across N root
modules` or `Audit only: N sites behind`), then these sections in
order:

1. `## Target`: the provider's resolved source address, the target
   version, and how it was confirmed. Add the publication date and
   changelog link only when fetched sources confirm them, and the upgrade
   guide on a major jump. A user-confirmed version is reported as
   `<version>, confirmed by you`.
2. `## Layout`: root modules and child modules discovered, and any
   classification the user settled (the umbrella says when to name the tool).
3. `## Sites`: a list of every declaration found, whether it was edited or
   deliberately left alone, and the operator each kept.
4. `## Locks`: per root module: the version selected before and after,
   the `h1:` checksum counts before and after, and the platform names
   whose package checks passed and where the required names came from,
   or coverage unverified.
5. `## Verification`: the gates run and their real results, with any
   pre-existing failure named as pre-existing.
6. `## Drift`: pin sites that disagreed with each other before the
   bump, unless the from and to pairs in `## Sites` already show it, root modules that did not move and why, and modules whose
   constraints already admitted the target. A bullet that repeats a
   `## Sites` or `## Locks` line is deleted; with none left, omit the
   section.

Name the commit by subject in `## Sites`, stating that it holds the
constraints and refreshed locks together. Never print its SHA or the
temporary exact pin used to land a named version.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ hashicorp/aws 6.56.1 -> 6.57.0 across 2 root modules

## Target

- registry.terraform.io/hashicorp/aws 6.57.0, confirmed by you.

## Layout

- Root modules: envs/prod, envs/staging. Child module: modules/network. Driven by terraform.

## Sites

- envs/prod/versions.tf and modules/network/versions.tf edited, keeping ~>.
- envs/staging/versions.tf already admits 6.57.0, left alone.

## Locks

- envs/prod: 6.56.1 to 6.57.0, 3 h1 records before and after; package checks passed for CI-required linux_amd64, linux_arm64 and darwin_arm64.
- envs/staging: 6.56.1 to 6.57.0, 1 h1 record before and after; platform coverage unverified.

## Verification

- fmt -check and validate pass in both root modules.
```

A run that cannot proceed ends with the stopped line from
`../bumping-terraform/SKILL.md`, not this shape, and has no
panel and no `Next steps:` list.

End with an `AskUserQuestion` panel offering next steps, for example:
converge the pin sites that disagree, refresh the lock files this run
left alone, check required platforms whose coverage is unverified, or
stop here. Skip the panel only in plan mode. Without a question tool, print the
umbrella's `Next steps:` list and stop.
