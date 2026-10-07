---
name: terraform-bump-provider
description: >-
  Use when updating one Terraform or OpenTofu provider across modules and
  refreshing root lockfiles without losing platforms.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "<provider> [version] [--root-module <dir>...] [--audit-only] [--no-lock] [--no-commit]"
  source: "plugins/terraform/skills/bump-provider/SKILL.md"
---

# Bump a Terraform provider

Raise a provider's version across every module that declares it, in one
commit, then refresh the lock file of every affected root module.

Follow the conventions in the `terraform-bumping-terraform` skill (recorded tree
state, script paths, commit message rules, non-interactive defaults,
the plan, stopped and audit-only runs). This skill uses
`references/layout-discovery.md`,
`references/pin-sites.md`, and
`references/lock-and-init.md`. To move the CLI, use
the `terraform-bump-terraform` skill. To refresh locks within existing constraints,
use the `terraform-refresh-lock` skill.

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
    -- '*.tf' '*.tofu' '*.tf.json'
```

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

Follow `references/layout-discovery.md`. Record, per directory:
kind, lock file presence, how many platforms that lock tracks per
provider, and the providers and `required_version` it declares. Find root
modules from the `.tf` files, not only from tracked lock files, map each
child module to the roots that call it, and ask the reference's
ambiguity questions together once the inventory exists. `--root-module`
limits the run to the named directories.

### 3. Resolve the target version

If the user named a version, confirm it with the exact-entry command in
`references/pin-sites.md`. Otherwise take the
latest stable release. Either way, query the registry's metadata for
that exact version and record its tag, publication date, and source
repository, never the latest-only endpoint, and build the changelog link from that
source at the tag in the form the reference gives, fetching it before
linking. If the registry reports no source, say no changelog
link was confirmed. When the target crosses a major version, add the
provider's upgrade guide.

### 4. Inventory the sites and predict the edits

Every module declaring this provider, root and child, per the pin-sites
reference. The affected root modules are the roots that declare it plus
the roots that call a declaring child module, mapped per the
layout-discovery reference. Decide per site whether it needs editing at all.

### 5. Present the plan and wait

Per the umbrella's Orchestration Plan, show the sites to be edited with the operator each keeps, the sites left
alone with the reason, the lock files to be refreshed with how many
platforms each tracks, and any drift found. With `--audit-only`, stop
here and write nothing.

### 6. Edit and commit

All constraint edits in one commit. Then, unless `--no-lock`, refresh
each affected root module's lock and commit those separately. Move only
the bumped provider: use the lock reference's "Moving one provider"
steps, never `init -upgrade`. When the user named a version that the
constraint allows to be exceeded, follow its "Landing a version the user
named" steps so the lock holds exactly that version. A root module with no committed lock is
skipped and reported, since `init` would create one; run it there only
after the user approves. A failed `init` restores the lock from git. Compare each lock with `lockctl.py diff`, passing the bumped provider
to `--allow` (the lock reference has the command), and restore a dropped
platform count for the bumped provider with `providers lock` naming it. Never commit a lock that
lost platforms without the user's explicit yes to that file; headless,
restore it from git, leave it out of the commit, and stop. With
`--no-commit`, leave everything in the working tree and say what would
have been committed. Write commit messages and the report per
`references/prose-rules.md`.

### 7. Verify

Read the selected version back out of each lock file and compare it to
the target; a different version is an overshoot to report, not a pass.
`lockctl.py diff` exiting non-zero names any other provider that changed
or any count that dropped; report it. Run the repository's own gates.
Report root modules that did not move, and why.

## Output

Open with a one-line hero (`✓ <provider> <old> -> <new> across N root
modules` or `Audit only: N sites behind`), then these sections in
order:

1. `## Target`: the provider's resolved source address, the target
   version, its publication date, the changelog link taken from the
   registry's source (or that none was confirmed), and the upgrade
   guide on a major jump.
2. `## Layout`: root modules and child modules discovered, which tool
   drives the repository, and any classification the user settled.
3. `## Sites`: a list of every declaration found, whether it was edited or
   deliberately left alone, and the operator each kept.
4. `## Locks`: per root module: the version selected before and after,
   and the platform count tracked before and after.
5. `## Verification`: the gates run and their real results, with any
   pre-existing failure named as pre-existing.
6. `## Drift`: pin sites that disagreed with each other before the
   bump, root modules that did not move and why, and modules whose
   constraints already admitted the target. Omit it when none apply.

Name each commit by subject in the section it carries (constraints under
`## Sites`, locks under `## Locks`), never by SHA, and do not report the
temporary exact pin used to land a named version.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ hashicorp/aws 6.56.1 -> 6.57.0 across 2 root modules

## Target

- registry.terraform.io/hashicorp/aws 6.57.0, published 2026-09-30; changelog taken from the registry's source at v6.57.0.

## Layout

- Root modules: envs/prod, envs/staging. Child module: modules/network. Driven by terraform.

## Sites

- envs/prod/versions.tf and modules/network/versions.tf edited, keeping ~>.
- envs/staging/versions.tf already admits 6.57.0, left alone.

## Locks

- envs/prod: 6.56.1 to 6.57.0, 3 platforms before and after.
- envs/staging: 6.56.1 to 6.57.0, 1 platform before and after.

## Verification

- fmt -check and validate pass in both root modules.
```

A run that cannot proceed ends with the stopped line from
the `terraform-bumping-terraform` skill, not this shape.

End with an `ask-user-choice` panel offering next steps, for example:
converge the pin sites that disagree, refresh the lock files this run
left alone, restore multi-platform coverage to a lock that only ever
tracked one, or stop here. Skip the panel only in plan mode. Without a question tool, list the
options and take the default: stop here.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
