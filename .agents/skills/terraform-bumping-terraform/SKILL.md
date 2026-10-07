---
name: terraform-bumping-terraform
description: >-
  Use when Terraform or OpenTofu providers, CLI pins, or lockfiles are
  outdated or behind; bump or upgrade them across root modules.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
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

## Conversational requests

The three slash-command skills are gated, so the model cannot invoke them.
Match the request to one, read its file, and follow its Procedure and
Output, taking its arguments from the request's wording:

- A provider to move: the `terraform-bump-provider` skill.
- The CLI version to move: the `terraform-bump-terraform` skill.
- Locks to refresh inside existing constraints:
  the `terraform-refresh-lock` skill.

A request that names none ("everything here is behind") is a provider
bump with no provider named unless the user says the CLI: list the
declared providers and ask which (headless default: stop). One run does
one of them; offer the others as next steps.

## Conventions for every run

- Name the current branch in the plan. Before the run's first edit, run
  `git status --porcelain` and print the result: that list is the
  changes the run did not make. Never rely on it from memory in later
  commands. Commit only this run's paths with `git commit -- <paths>`,
  after `git add <path>` for any new file such as a lock file (`git
  commit -- <untracked path>` fails). Stop when a path to commit is
  already in the recorded list.
- `references/lockctl.py` resolves from this skill's directory. Print
  its absolute path once and write that path literally in each command,
  since shell variables do not persist between Bash calls. The
  references show the same `../../scripts/` form.
- Commit messages carry no `Co-Authored-By`, no "Generated with" or other
  tool trailers, and no emoji.
- Where there is no interactive question tool (Codex, headless runs),
  state each question in the reply with the narrower answer as the
  default (fewest modules, `--no-commit`), without remarking that no
  question tool exists. A headless run presents the
  plan and stops, unless the request itself authorises the edit ("go
  ahead and bump it"); that covers the edit only, never a commit or
  push.
- Reply in the shape each skill's Output declares, as plain text outside
  any code fence, with plain bullets and no bold (never
  `- **Label:** ...`), and no section that would hold nothing. Name paths
  relative to the repository, never local absolute or temporary paths,
  and name tools by name (`terraform`), never by install path. Name no
  helper script in a reply; say what it found.
- Name no version the registry has not confirmed, and make no claim about
  what a newer release changes (such as a major jump) before one is
  confirmed.
- A run that cannot proceed (nothing declared, no version named and the
  release list unreachable, a dirty tree it cannot work around) ends
  with `⚠ Stopped: <one result sentence>`, then the step the user must
  take. No sections and no recap. Findings that change that step follow
  as plain bullets, with no lead-in sentence, and describe only what the
  run found, never steps it would take after the edit. A run stopped
  before its first edit says nothing was edited.
- `--audit-only` writes nothing and is a result, not a stop. Its hero is
  `Audit only: <result>` with no `⚠`, the skill's own sections follow
  (omit the empty ones), and no sentence restates that nothing was
  written. An audit with nothing to audit (no Terraform files) is a
  stopped run.
- When a confirmed target crosses a major version, link the project's
  upgrade guide in the report, or say none was found.

## Core principle

Constraints from every module in a configuration must all be satisfied at
once, so the unit of work is the configuration, not the file. Every
declaration moves in one commit, or none does.

## Scope

The current repository. Discover its root modules and confirm the set with
the user when there is more than one. Never widen scope as a side effect:
no repository-wide operator normalising, no platforms the lock never
tracked, no reformatting of modules the change did not touch.

## Phase 1 - Discover the layout

Follow the layout-discovery reference. Record, per directory: kind, lock
file presence, how many platforms that lock tracks per provider, and the
providers and `required_version` it declares. That inventory is the unit
of work for everything after.

Find root modules from the `.tf` files, not only from tracked lock files,
and map each child module to the root modules that call it, both per the
reference. Ask the reference's ambiguity questions together, after the
inventory exists.

## Phase 2 - Resolve the target and confirm it exists

Ask the registry the detected tool resolves against, not memory. Confirm
the version is published and record its tag and source repository, which
is where the changelog link comes from. Write no version string before
this phase confirms it. If it cannot be confirmed, stop and ask the user
which version to use, and say plainly when a version was stated but not
confirmed. When the user says they confirmed it, write it, record
"confirmed by you" in the report, and link no changelog unless a fetch
succeeded.

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

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present a plan covering:

- The root modules in scope, and any directory whose classification the
  user settled.
- The target version, and the evidence it exists.
- Every pin site to be edited, the operator each one keeps, and the
  sites left alone with the reason.
- Which lock files will be refreshed, and how many platforms each
  tracks.
- The commits this produces and whether they will be pushed.
- Drift found that this run will not fix.

Wait for approval, then exit plan mode before Phase 4. Without plan mode,
finish discovery, resolution, and inventory, and confirm scope with the
user before writing anything. Headless, the plan is the reply.

## Phase 4 - Edit the constraints

All sites in one commit. Preserve each site's operator, and write to the
file the tool loads where `.tofu` shadows `.tf`.

The commit body says what moved and why, and cites the release notes at
the tag the registry reported, but only a page the run fetched; with none,
the body names no link. Take the subject format from the project's
own commit conventions in AGENTS.md or CLAUDE.md. Write it per
`references/prose-rules.md`.

## Phase 5 - Refresh the locks

Per root module, per the lock reference, without `-upgrade` when one
provider or the CLI moves. Apply the reference's guard first: a root
module with no committed lock, or an edited one, is skipped and reported,
never initialised on its own. Compare each provider's platform count
against its count before the run; a drop is a stop signal. A failed
`init` restores the lock from git. A lock that lost platforms is never
committed without the user's explicit yes to that file; headless, restore
it from git, leave it out of the commit, and stop.

Lock files land as their own commit, separate from the constraints.

## Phase 6 - Verify

Read the selected version back out of each lock file, per root module.
Name the root modules that did not move and why.

Run the detected tool's `fmt -check -recursive` and its `validate` per
initialised root module (`tofu` where OpenTofu drives the repository),
then the repository's own gates. If something fails, establish whether it
failed before the bump; report pre-existing failures, and fix none as a
side effect.

Never report a gate as passing without reading the output that says so.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
