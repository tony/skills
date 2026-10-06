---
name: terraform-bumping-terraform
description: >-
  Use when Terraform or OpenTofu provider constraints, CLI pins, or
  lockfiles are stale across repository root modules.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "WebSearch", "WebFetch", "AskUserQuestion"]
metadata:
  source: "plugins/terraform/skills/bumping-terraform/SKILL.md"
---

# Bumping Terraform

Find the root modules, move every declaration of a version together,
refresh each root module's lock file without narrowing it, and verify
the selected version changed.

The references own the rules; read each before the phase that cites it:

- `references/layout-discovery.md` for root and child module
  classification and what to ask.
- `references/pin-sites.md` for every pin site, operator
  preservation, and registry lookups.
- `references/lock-and-init.md` for `init`, platform narrowing, and
  verification.

## Core principle

Constraints from every module in a configuration must all be satisfied
at once, so the unit of work is the configuration, not the file. Every
declaration moves in one commit, or none does.

## Scope

The current repository. Discover its root modules rather than assuming
one, and confirm the set with the user when there is more than one.

Never widen scope as a side effect: a bump is not the moment to
normalise operators repository-wide, adopt platforms the lock never
tracked, or reformat modules the change did not touch.

## Phase 1 - Discover the layout

Follow the layout-discovery reference. Record, per directory: kind, lock
file presence, how many platforms that lock tracks per provider, and the
providers and `required_version` it declares. That inventory is the unit
of work for everything after.

Ask the reference's ambiguity questions all at once, after the inventory
exists.

## Phase 2 - Resolve the target and confirm it exists

Ask the registry, not memory. Confirm the version is published and
record its tag and source repository, which is where the changelog link
comes from. Use the registry the detected tool resolves against. Write
no version string before this phase confirms the version exists.

## Phase 3 - Inventory the pin sites and predict the change

Find every declaration of the thing being moved across the whole
configuration, per the pin-sites reference, including CLI pin sites
outside `.tf`. Work out which sites need editing: a constraint that
already admits the target needs none.

Report drift found before the bump as its own finding: root modules
disagreeing about the CLI version, a `.tool-versions` that contradicts
`required_version`, pin sites that disagree with each other. The bump
overwrites that evidence.

## Orchestration Plan

Before any file is written, enter plan mode (`EnterPlanMode` in Claude
Code, `/plan` or `Shift+Tab` in Cursor, Codex, and Gemini) and present a
plan covering:

- The root modules in scope, and any directory whose classification the
  user settled.
- The target version, and the evidence it exists.
- Every pin site to be edited, the operator each one keeps, and the
  sites left alone with the reason.
- Which lock files will be refreshed, and how many platforms each
  tracks.
- The commits this produces and whether they will be pushed.
- Drift found that this run will not fix.

Wait for approval. Exit plan mode before Phase 4.

If plan mode is unavailable, finish discovery, resolution, and inventory,
and confirm scope with the user before writing anything.

## Phase 4 - Edit the constraints

All sites in one commit. Preserve each site's operator, and write to the
file the tool loads where `.tofu` shadows `.tf`.

The commit body says what moved and why, and cites the release notes at
the tag the registry reported. Take the subject format from the project's
own commit conventions in AGENTS.md or CLAUDE.md. Write it per
`references/prose-rules.md`.

## Phase 5 - Refresh the locks

Per root module, per the lock reference. Compare each lock's
per-provider platform count against its count before the run; a drop is
a stop signal.

Lock files land as their own commit, separate from the constraints.

## Phase 6 - Verify

Read the selected version back out of each lock file, per root module.
Name the root modules that did not move and why.

Run the detected tool's `fmt -check -recursive` and its `validate` per
initialised root module (`tofu` where OpenTofu drives the repository),
then the repository's own gates. If something fails, establish whether it
failed before the bump; report pre-existing failures, and fix none as a
side effect.

Never report a gate as passing without having read the output that says
so.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
