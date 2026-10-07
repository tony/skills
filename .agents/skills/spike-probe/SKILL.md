---
name: spike-probe
description: >-
  Use when spiking a feature or fix in the working tree to prove it quickly
  before committing to an implementation.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[<goal>] [--branch=<name>] [--keep-tree] [--replay]"
  source: "plugins/spike/skills/probe/SKILL.md"
---

# this skill

Rapid spike harness. Probe the goal in the working tree with the
lightest verification that proves the path, exit through the project's
fast quality gates, stash everything with a recovery ref, and hand back
a commit-by-commit plan, optionally replaying it immediately.

A probe **mutates the working tree freely** and never touches history.

The shared steps (preflight, setup, probe loop, exit gate, stash) live in
`references/spike-core.md`; read it before Phase 0. `references/spike.sh`
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

| Rationalization | Reality |
|---|---|
| "The owner said 'we'll clean it up later' so commit now, clean later" | "Later" is this command's Phase 5. A commit *is* the cleanup being deferred; stash instead. |
| "They need it before a meeting, so a commit is the fastest handoff" | A stash plus the plan is the same speed and leaves history clean. Show the demo from the working tree. |
| "It's all green, so it's safe to commit" | Green ≠ reviewed. The probe skipped naming, API, and scope decisions on purpose; the plan surfaces them first. |
| "One commit is easier to undo than a stash" | A stash with a recorded ref is exactly as recoverable and never entangles trunk or the branch. |
| "I'll commit on a scratch branch, that doesn't count" | It counts. Scratch branches leak into PRs and get merged. Stash. |

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
   - Several: `ask-user-choice` (multi-select), one option per
     candidate plus "all of them". Non-interactive: halt and name the
     candidates.
   - None: ask what to probe before touching anything. Non-interactive:
     halt and name the missing goal.
3. **Record provenance** in the Phase 1 brief.

For a set of review findings, the brief notes the boundary: a probe
explores fixes with zero commits; screening them is the `respond-check` skill and
landing them is the `respond-action` skill.

| Flag | Default | Effect |
|---|---|---|
| `--branch=<name>` | off | Probe on a new scratch branch from HEAD, then return to the original branch and delete the scratch branch at exit. Still zero commits. |
| `--keep-tree` | off | Skip the stash at exit; leave changes in the working tree. The plan is still produced; after a probe on top it is built from the tree's diff against the user-work SHA. Cannot combine with `--replay`: halt and say so. |
| `--replay` | off | After the plan is approved, apply the spike's stash and land plan items one gated commit at a time. |

## Phase 0: Situational awareness

Run the Preflight in `references/spike-core.md`, resolving the gate
buckets and CI split per `references/verification-gates.md`. Probe
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

Run Setup from `references/spike-core.md` once the brief is
approved: `save-user` for *stash first*, `hold-user` for *probe on top*,
`branch-start` with `--branch`. With `--keep-tree` after a stash-first
answer the spike stays in the tree, so their work stays stashed: report the
SHA and its restore command. Then follow its probe loop.

## Phase 3: Spike exit gate

Run the Exit gate in `references/spike-core.md`.

## Phase 4: Stash with a recovery ref

Unless `--keep-tree`, run the Stash steps in
`references/spike-core.md`: `stash` on a clean start, `stash-on-top`
after a probe on top, `delta` for the plan, then `restore` after a
stash-first run that is not replaying, and `branch-end` with `--branch`.

## Phase 5: The replay plan

Produce the commit-by-commit plan. For each planned commit:

- **Subject** in the project's commit format (from Phase 0).
- **Contents**: which files/hunks from the spike's changes it takes (the
  delta after a probe on top), and what gets rewritten rather than
  replayed.
- **Decisions to resolve**: each `SPIKE:` marker landing in this commit,
  as a question with a recommendation.
- **Gates**: the per-commit gate commands, right-sized per
  `references/verification-gates.md`.

Close the plan with the local-vs-CI table and the post-push watch
command: `gh pr checks --watch` for a PR, `gh run watch` when no PR
exists yet, or "none (no remote)".

## Phase 6: Replay (only with `--replay`, after approval)

1. From the original branch, never a scratch branch, apply the spike
   (apply, not pop). The stash stays until the replay finishes green.
   Their own edits are never part of a plan item: after a probe on top,
   pass the user-work SHA so only the spike's delta is applied.

```console
$ <scripts>/spike.sh replay-apply <spike sha> [<user-work sha>]
```

2. Land plan items in order: stage only that item's changes, run its
   gates, commit with the planned message, written per
   `references/prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailers, and no emoji. A red gate
   stops the replay; report and hand back. Prefer file-level splits;
   to split one file, write the relevant hunks to a patch file and
   `git apply --cached <patch>` (`git add -p` is interactive).
3. After the final item: run any end-of-run `build` bucket, drop the
   spike stash by SHA (it refuses the user-work stash; an `already
   gone` result means nothing to drop), and if the branch has a remote
   counterpart offer to push and watch CI:

```console
$ <scripts>/spike.sh drop <spike sha>
```

4. After a stash-first run, restore their work with
   `<scripts>/spike.sh restore <user-work sha>`. It stays uncommitted. A refused
   restore keeps the stash: report the SHA.

## Output contract

Write the report, and any replay commit message, per
`references/prose-rules.md`.

The first line of the reply is exactly the hero line: no lead-in sentence,
no first-person opener. Report results, not process: never narrate a
departure from these steps or name the brief or the skill; do the step or
halt. State what happened, not what a contender or step did not do.
Write in the passive or the plain result, never "I" or "the run"; when a
non-interactive default applies, name the default taken without describing
how the run was set up. Use no transient wording ("for now", "currently").
Warnings about the checkout (mode changes, files left in place, a tree
that needs attention) go inside `## Stash`, never before the first section.

1. Hero block (1–3 lines): `✓ spike proven` / `⚠ spike blocked` +
   goal + exit path taken.

   A run that halts before probing (no commit, repository rooted at
   home, dirty tree declined, goal missing) is the hero line, one result
   sentence, then one line with what the user must do next. Several
   blockers at once: name every one in that single result sentence, in
   the order no commits, repository at home, dirty tree, missing code or
   goal, and make the action line cover them all. No sections, no panel,
   no stash SHA, no local or temp paths, no command echo, no description
   of the environment. The result sentence names only the blockers, never
   why a file or tree is in that state.
2. `## Spike findings`: what was proven, stumbling blocks, `SPIKE:`
   markers, observed-not-addressed list. State stumbling blocks even
   when the probe succeeded: a path that fought you throughout is the
   case for the `spike-bakeoff` skill or the `spike-ratchet` skill.
3. `## Verification`: gate commands run and their results; the
   local-vs-CI split; what was deferred and why.
4. `## Stash`: message, SHA, restore command. With `--keep-tree` there
   is no spike stash: say the spike was left in the tree. A probe that
   changed nothing says "no changes" here instead of a SHA. Whenever the
   run saved the user's work (stash first or on top), add one more bullet
   in this form, with the real SHA and its restore state:
   `- user work before spike: 9d31c2a, restored (git stash apply 9d31c2a
   puts it back)`.
5. `## Replay plan`: the numbered commit sequence from Phase 5.
6. End with an `ask-user-choice` panel: replay now / keep stash and
   stop / discard spike, unless already running inside plan mode or
   `--replay` was given. In a non-interactive run (CI, subagent),
   record the panel's question and options in the report instead of
   asking, and default to keeping the stash.

A halted run replies in this shape:

```text
⚠ spike blocked: stream the NDJSON export instead of buffering it.

Nothing was probed: the repository has no commits and the export code is missing.
Make the initial commit yourself, since a spike never commits, open the project that holds the export code, then run spike-probe again.
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


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
