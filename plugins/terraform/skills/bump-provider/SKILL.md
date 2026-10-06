---
name: bump-provider
description: "Use when updating one Terraform or OpenTofu provider across modules and refreshing root lockfiles without losing platforms."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "WebSearch", "WebFetch", "AskUserQuestion"]
argument-hint: "<provider> [version] [--root-module <dir>...] [--audit-only] [--no-lock] [--no-commit]"
user-invocable: true
disable-model-invocation: true
---

# Bump a Terraform provider

Raise a provider's version across every module that declares it, in one
commit, then refresh the lock file of every affected root module.

Follow the phase structure in `../bumping-terraform/SKILL.md`, which
points to the three references this skill relies on. To move the CLI
itself, use `/terraform:bump-terraform`. To refresh locks within the
constraints already written, use `/terraform:refresh-lock`.

User arguments: $ARGUMENTS

## Procedure

### 1. Resolve which provider

The argument may be a full source address or a bare name. List the
source addresses the repository declares:

```console
git grep -hE '^[[:space:]]*source[[:space:]]*=' -- '*.tf' '*.tofu'
```

The list mixes provider and module sources. Resolve the argument against
the addresses inside `required_providers` blocks only. If more than one
declared address matches, ask which.

A name that matches nothing declared is a finding, not a typo to correct
silently: say so and stop.

### 2. Discover the layout and settle the ambiguities

Run the umbrella's discovery phase. `--root-module` limits the run to the
named directories.

### 3. Resolve the target version

If the user named a version, confirm it is published. Otherwise take the
latest stable release. Either way, record the tag and the source
repository the registry reports, and derive the changelog link from that
source.

### 4. Inventory the sites and predict the edits

Every module declaring this provider, root and child, per the pin-sites
reference. Decide per site whether it needs editing at all.

### 5. Present the plan and wait

Show the sites to be edited with the operator each keeps, the sites left
alone with the reason, the lock files to be refreshed with how many
platforms each tracks, and any drift found. With `--audit-only`, stop
here and write nothing.

### 6. Edit and commit

All constraint edits in one commit. Then, unless `--no-lock`, refresh
each affected root module's lock and commit those separately, checking
each lock's per-provider platform count against its count before. With
`--no-commit`, leave everything in the working tree and say what would
have been committed. Write commit messages and the report per
`../../references/prose-rules.md`.

### 7. Verify

Read the selected version back out of each lock file and compare it to
the target. Run the repository's own gates. Report root modules that did
not move, and why.

## Output

Open with a one-line hero (`✓ <provider> <old> -> <new> across N root
modules` or `⚠ Audit only: N sites behind`), then exactly these
sections:

1. `## Target` — the provider's resolved source address, the target
   version, its publication date, and the changelog link derived from
   the registry.
2. `## Layout` — root modules and child modules discovered, which tool
   drives the repository, and any classification the user settled.
3. `## Sites` — every declaration found, whether it was edited or
   deliberately left alone, and the operator each kept.
4. `## Locks` — per root module: the version selected before and after,
   and the platform count tracked before and after.
5. `## Verification` — the gates run and their real results, with any
   pre-existing failure named as pre-existing.
6. `## Drift` — pin sites that disagreed with each other before the
   bump, root modules that did not move and why, and modules whose
   constraints already admitted the target.

End with an `AskUserQuestion` panel offering next steps, for example:
converge the pin sites that disagree, refresh the lock files this run
left alone, restore multi-platform coverage to a lock that only ever
tracked one, or stop here. Skip the panel only in plan mode.
