---
name: bumping-terraform
description: "Use when Terraform or OpenTofu providers, CLI pins, or lockfiles are outdated or behind; bump or upgrade them across root modules."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
---

# Bumping Terraform

Find the root modules, move every declaration of a version together,
refresh each root module's lock file without narrowing it, and verify
the selected version changed. This skill classifies the request and hands
it to one of three skills; the conventions below apply to whichever runs.

## Conversational requests

The three slash-command skills are gated, so the model cannot invoke them.
Match the request to one, then read its file and follow it from its
Procedure through its Output, taking its arguments from the request's
wording:

- A provider to move: `../bump-provider/SKILL.md`.
- The CLI version to move: `../bump-terraform/SKILL.md`.
- Locks to refresh inside existing constraints:
  `../refresh-lock/SKILL.md`.

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
- Script paths: `../../scripts/lockctl.py` resolves from a skill's
  directory (a reference writes `../scripts/`). Print the absolute path
  once and write it literally in each command, since shell variables do
  not persist between Bash calls.
- Commit bodies say what moved and why, and cite release notes at the
  tag the registry reported only when the run fetched that page; with
  none, the body names no link. Take the subject format from the
  project's AGENTS.md or CLAUDE.md. Write them per
  `../../references/prose-rules.md`.
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
- Where no question tool exists, close with `Next steps:` and a plain
  bulleted list of the options, in that form every time, then stop. A
  stopped run is the exception: it has no panel and no `Next steps:`
  list.
- A reply's `## Layout` names what the user can act on: the roots and
  children found and any settled classification. Name the driving tool
  only when both `terraform` and `tofu` are present. Leave out the branch
  and any tool that is not installed.
- Name no version the registry has not confirmed, and make no claim about
  what a newer release changes (such as a major jump) before one is
  confirmed. A version the user named that the registry cannot confirm
  (unreachable, or absent from the release list) is a stopped run unless
  the user said they confirmed it; the next step offers that confirmation
  or access to the registry.
- Output rules for every reply: state results, not the rules behind them.
  Do not mention commit-message rules, trailers, or this skill's
  conventions. Do not recap a default taken ("I've taken the default"); a
  next-step option "stop here" is fine. Do not remark on the missing question tool. Do not
  write "X, not Y" contrasts or filler such as "nothing needed
  classifying by you". A bullet states a finding, not scope the plan
  already gave. The hero is the line the skill's shape gives with
  nothing appended; a failing gate goes in `## Verification`, stated as
  observed. Every reply, not only a stopped one, omits what the
  repository lacks ("no other file pins the CLI", "no child modules
  found", "tflint isn't installed", "the repository defines no other
  gates") and never states what the run will do on its own later ("I'll
  run the audit again"). With `--no-commit`, do not say nothing was
  committed.
- A run that cannot proceed (nothing declared, no version named and the
  release list unreachable, a dirty tree it cannot work around, a lock
  that failed after the edits, a gate the edits plausibly broke) ends
  with `⚠ Stopped: <one result sentence>`, then the step the user must
  take. The result sentence says what state the repository is in: `so
  nothing was edited` before the first edit, or `so nothing was
  committed` after it. A run stopped after its edits leaves them in the
  working tree, and the step offers reverting them (`git restore --
  <paths>`) first.

  The reply has no sections, no recap, and no numbered next-step list.
  The step is one or two sentences and ends with its request. Bullets are
  optional, at most three, with no lead-in sentence, and follow these
  rules:

  - A bullet is a finding about the repository as it stands that the
    step depends on, such as the pins that disagree when the step asks
    which to move. With no such finding, write no bullets.
  - The declared pins are the usual finding. Lock files, backends, which
    root calls which module, and the installed `terraform` version stay
    out, as does whether a pin or an installed version would satisfy the
    target. The one exception is the roots outside `--root-module` that
    call a child module the run would edit: the result sentence names
    them.
  - Leave out anything about what the run would do after the edit
    (`init` could not run, no lock to refresh, both keep `~>`), the
    branch, history, untracked files, the driving tool, or a question.
  - A stop after the edits may state the new constraint and the lock's
    selected version in one bullet, as the repository stands now ("the
    lock selects 3.7.0 with 1 h1 checksum, 2 before"), never as what the run
    did.
  - A bullet never asks the user for anything.
  - Never state what the run will do on its own later ("I'll show the
    plan", "and I'll rerun it", "after that I'll ...", a "then" clause, or a
    "so I can ..." clause after the user's step);
    telling the user what to do next is the step itself.
  - List nothing the repository lacks ("neither directory has a backend
    block or a lock file", "no CI or task file runs providers lock").
  - Name no sandbox or network block; say the registry or mirror was
    unreachable.

  Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

  ```text
  ⚠ Stopped: I could not confirm hashicorp/aws 6.57.0 because registry.terraform.io was unreachable, so nothing was edited.

  Tell me you confirmed 6.57.0 yourself, or allow registry.terraform.io.

  - envs/prod and modules/network both declare hashicorp/aws, at ~> 6.56.0 and ~> 6.55.0, so the pins disagree.
  ```

- `--audit-only` writes nothing and is a result, not a stop. Its hero is
  `Audit only: <result>` with no `⚠`, the skill's own sections follow
  (omit the empty ones), and no sentence restates that nothing was
  written. In an audit `## Held back` lists only what a constraint or
  guard is already blocking, never constraints that merely permit a
  newer release. An audit with nothing to audit (no Terraform files) is a
  stopped run.
- A target the user confirmed is reported as "confirmed by you", with no
  reason attached. `## Drift` states only what `## Sites` and `## Locks`
  do not already say.
- When a confirmed target crosses a major version, link the project's
  upgrade guide in the report, or say none was found.

## Core principle

Constraints from every module in a configuration must all be satisfied at
once, so the unit of work is the configuration, not the file. Every
declaration moves in one commit, or none does.

## Scope

The current repository. Discover its root modules and confirm the set with
the user when there is more than one. When `--root-module` limits the run, list every root outside it that
calls a child module the run would edit (or declares the target pin). Such a root would be left
inconsistent, its lock failing `init`, so stop and name them, or widen the scope on the user's yes
(headless: stop). Never widen scope as a side effect:
no repository-wide operator normalising, no invented platform names,
no reformatting of modules the change did not touch.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

Present a plan covering:

- The root modules in scope, and any directory whose classification the
  user settled.
- The target version, and the evidence it exists.
- Every pin site to be edited, the operator each one keeps, and the
  sites left alone with the reason.
- Which lock files will be refreshed, each provider's `h1:` count, and
  any platform names declared by the repository or confirmed by the user.
- The commit this produces (constraints and locks together) and whether
  it will be pushed.
- Drift found that this run will not fix.

Wait for approval, then exit plan mode before the first edit. Without plan
mode, finish discovery, resolution, and inventory, and confirm scope with
the user before writing anything. Headless, the plan is the reply.

