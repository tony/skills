---
name: probe
description: "Use when spiking a feature or fix in the working tree to prove it quickly before committing to an implementation."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[<goal>] [--branch=<name>] [--keep-tree] [--replay]"
disable-model-invocation: true
---


# `/spike:probe`

Rapid spike harness. Probe the goal in the working tree with the
lightest verification that proves the path, exit through the project's
fast quality gates, stash everything with a recovery ref, and hand back
a commit-by-commit plan, optionally replaying it immediately.

A probe **mutates the working tree freely** and never touches history.

The shared steps (preflight, setup, probe loop, exit gate, stash) live in
`../../references/spike-core.md`; read it before Phase 0. `../../scripts/spike.sh`
holds the git plumbing. In every command, `<scripts>` stands for the
absolute path of `../../scripts` resolved from this skill's directory (the
shell runs in the project, not here); write that path literally.

## Core thesis

A spike answers "does this path work?" It is **evidence, not a
deliverable**: its value survives as a stash you can reapply and the
decisions the plan records. Committing spike code turns unreviewed
exploration into history.

Verify with the cheapest signal while probing, run the fast gates once
at exit, and defer what CI covers to CI. The plan is the product: a
numbered commit sequence mapping stash contents to commits.

## The Iron Rule

```
A SPIKE PRODUCES ZERO COMMITS
```

Not on trunk, the feature branch, or a scratch branch, and not "just to
checkpoint". Exit paths: stash (default), `--keep-tree` (leave changes
unstaged), or `--replay` (commits only *after* the plan is approved, one
plan item at a time, each behind a green gate).

Rationalizations and their answers: `../../references/spike-core.md` (Zero commits).

**Red flags (STOP, you are about to violate the Iron Rule):**
typing `git commit` in any form; "checkpoint commit"; "WIP commit";
"temporary commit"; "I'll squash it later"; creating a branch to
commit to it. All of these mean: stash and write the plan.

## `$ARGUMENTS` contract

Non-flag text is the probe goal. Resolve the goal by this ladder:

1. **Typed goal wins.** Non-flag `$ARGUMENTS` text is the goal,
   verbatim; conversation context may enrich it but never overrides it.
2. **Empty → mine the conversation** (review findings just presented, a
   failing test, a pasted stack trace, an agreed suggestion).
   - One strong candidate: adopt it; the Phase 1 brief is the
     confirmation gate.
   - Several: `AskUserQuestion` (multi-select), one option per
     candidate plus "all of them". Non-interactive: halt and name the
     candidates.
   - None: ask what to probe before touching anything. Non-interactive:
     halt and name the missing goal.
3. **Record provenance** in the Phase 1 brief.

For a set of review findings, the brief notes the boundary: a probe
explores fixes with zero commits; screening them is `/respond:check` and
landing them is `/respond:action`.

| Flag | Default | Effect |
|---|---|---|
| `--branch=<name>` | off | Probe on a new scratch branch from HEAD, then return to the original branch and delete the scratch branch at exit. Still zero commits. |
| `--keep-tree` | off | Skip the stash at exit; leave changes in the working tree. The plan is still produced; after a probe on top it is built from the tree's diff against the user-work SHA. Cannot combine with `--replay`: halt and say so. |
| `--replay` | off | After the plan is approved, apply the spike's stash and land plan items one gated commit at a time. |

## Phase 0: Situational awareness

Run the Preflight in `../../references/spike-core.md`, resolving the gate
buckets and CI split per `../../references/verification-gates.md`. Probe
accepts all three dirty-tree answers (stash first, probe on top, abort) and
`--branch`.

## Phase 1: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

Present a short spike brief:

1. The goal, restated in one line, with its provenance (typed, or
   inferred from what).
2. What "proven" means: the demo command or smoke check that ends
   the probe.
3. Files expected to change; scratch branch name if `--branch`.
4. Discovered gate commands (per bucket: command or `unset`) and the
   local-vs-CI split.
5. The exit path: stash / `--keep-tree` / `--replay`.

Wait for approval, then exit plan mode. If plan mode is unavailable,
present the same brief inline and proceed on confirmation. In a
non-interactive run, record the brief in the report and proceed. A
rejected brief ends the run with nothing saved, switched, or edited, so
there is nothing to undo.

## Phase 2: The probe

Run Setup from `../../references/spike-core.md` once the brief is
approved: `save-user` for *stash first*, `hold-user` for *probe on top*,
`branch-start` with `--branch`. With `--keep-tree` after a stash-first
answer the spike stays in the tree, so their work stays stashed: report the
SHA and its restore command. Then follow its probe loop.

## Phase 3: Spike exit gate

Run the Exit gate in `../../references/spike-core.md`.

## Phase 4: Stash with a recovery ref

Unless `--keep-tree`, run the Stash steps in
`../../references/spike-core.md`: `stash` on a clean start, `stash-on-top`
after a probe on top, `delta` for the plan, then `restore` after a
stash-first run that is not replaying, and `branch-end` with `--branch`.
Run `git rev-parse --verify <sha>^{commit}` on each printed SHA, as its own
Bash call, before writing the report.

## Phase 5: The replay plan

Produce the plan per `../../references/replay.md` (The replay plan).

## Phase 6: Replay (only with `--replay`, after approval)

Land it per `../../references/replay.md` (Replay).

## Output contract

Write the report, and any replay commit message, per
`../../references/prose-rules.md`.

The first line of the reply is exactly the hero line: no lead-in sentence,
no progress note sent while sub-agents ran, no first-person opener, no
"I recommend". Print every SHA abbreviated to 7 characters. After the last section
only the panel or the default line follows: no table, no closing question
in prose. Report results, not process: never narrate a
departure from these steps or name the brief or the skill; do the step or
halt. State what happened, never what a contender or step did not do: no
"not hidden", "no user work was saved", "nothing was X" restatements.
Write in the passive or the plain result, never "I" or "the run". Do not
describe how the run was set up (answers unavailable, permissions,
sandbox); a non-interactive default is one line: "Default: keep the
stashes." Do not print HEAD or the main checkout's SHA; SHAs belong to
stashes. Use no transient wording ("for now", "currently"). Write only the
sections below: a stray finding goes in the findings or open section, and
process (an amended commit, a retry) is left out.
Warnings about the checkout (mode changes, files left in place, a tree
that needs attention) go inside `## Stash`, never before the first section.

1. Hero block (1–3 lines): `✓ spike proven` / `⚠ spike blocked` +
   goal + exit path taken.

   A run that halts before probing is the hero line and the blocker
   sentence per `../../references/spike-core.md` (Halted run).
2. `## Spike findings`: what was proven, stumbling blocks, `SPIKE:`
   markers, observed-not-addressed list. State stumbling blocks even
   when the probe succeeded: a path that fought you throughout is the
   case for `/spike:bakeoff` or `/spike:ratchet`.
3. `## Verification`: gate commands run and their results; the
   local-vs-CI split; what was deferred and why.
4. `## Stash`: message, SHA (one `git rev-parse --verify <sha>^{commit}`
   printed back), restore command. With `--keep-tree` there
   is no spike stash: say the spike was left in the tree. A probe that
   changed nothing says "no changes" here instead of a SHA. Whenever the
   run saved the user's work (stash first or on top), add one more bullet
   in this form, with the real SHA and its restore state:
   `- user work before spike: 9d31c2a, restored (git stash apply 9d31c2a
   puts it back)`.
5. `## Replay plan`: the numbered commit sequence from Phase 5.
6. End with an `AskUserQuestion` panel: replay now / keep stash and
   stop / discard spike, unless already running inside plan mode or
   `--replay` was given. In a non-interactive run (CI, subagent),
   state the default taken ("Default: keep the stash.") instead of asking.

A halted run replies in this shape:

```text
⚠ spike blocked: stream the NDJSON export instead of buffering it.

Blocked: the repository has no commits and the export code is missing.
Make the initial commit yourself, since a spike never commits, open the project that holds the export code, then run /spike:probe again.
```

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Proven:** ...`), the numbered plan
aside:

```text
✓ spike proven: stream the NDJSON export instead of buffering it. Exit path: stash.

## Spike findings
- Proven: a 2 GB export runs in constant memory.
- Stumbling block: the serializer assumes a full list, so it needed a generator wrapper.
- SPIKE: batch size hardcoded to 500 in export.py.
- Observed, not addressed: the CSV exporter buffers the same way.

## Verification
- Ran format, lint, typecheck, and the export tests; all pass.
- Deferred to CI: integration suite and build.

## Stash
- spike: stream export (all gates pass; batch size undecided)
- 4be09c7, restore with git stash apply 4be09c7

## Replay plan
1. export(refactor[serializer]) Accept an iterator
2. export(feat[stream]) Stream NDJSON in batches
```
