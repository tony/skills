---
name: spike-probe
description: >-
  Use when spiking a feature or fix in the working tree to prove it quickly
  before committing to an implementation.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
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
     candidate plus "all of them".
   - None: ask what to probe before touching anything.
3. **Record provenance** in the Phase 1 brief.

For a set of review findings, the brief notes the boundary: a probe
explores fixes with zero commits; screening them is the `respond-check` skill and
landing them is the `respond-action` skill.

| Flag | Default | Effect |
|---|---|---|
| `--branch=<name>` | off | Probe on a new scratch branch from HEAD. Still zero commits. |
| `--keep-tree` | off | Skip the stash at exit; leave changes in the working tree. The plan is still produced. |
| `--replay` | off | After the plan is approved, apply the stash and land plan items one gated commit at a time. |

## Phase 0: Situational awareness

Before writing any code:

1. Confirm a git repository with at least one commit:

```console
$ git rev-parse --verify HEAD
```

   A failure means no repository or no commits. Halt before touching
   anything: say what is missing and that the user must make the
   initial commit (a spike never commits).
2. Read `AGENTS.md` / `CLAUDE.md` / `.github/CONTRIBUTING.md` for
   quality checks, commit format, and test conventions.
3. Resolve the five gate buckets (`format`, `lint`, `typecheck`,
   `test`, `build`) and the CI-coverage split per
   `references/verification-gates.md`.
4. Run `git status --porcelain`. A dirty tree halts here: ask whether to
   stash their work first, probe on top of it, or abort. Non-interactive
   default: abort.
   - **Stash first:** save their work with the stash sequence in
     Phase 4 under the message `user work before spike`, record its
     SHA, and tell the user it.
   - **Probe on top:** save their work the same way, but keep it in
     the tree and run `git reset -q` afterwards (the sequence stages
     everything). Record that SHA as the baseline. Phase 4 then
     restores the user's work and reports the spike's own delta.
5. Locate the code the goal touches (existing modules, tests,
   fixtures), enough to work in the project's idiom.

## Phase 1: Orchestration plan

Enter plan mode if the host supports it (Claude Code: `EnterPlanMode`;
Cursor / Codex / Gemini: `/plan` or `Shift+Tab`) and present a short
spike brief:

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
non-interactive run, record the brief in the report and proceed.

## Phase 2: The probe

Code the shortest path to "proven". During this phase:

- Verify with the **cheapest signal that moves you forward**: the one
  test file or smoke command that exercises the new code, not the full
  suite or the build.
- Mark shortcuts as you take them with a `SPIKE:` comment (hardcoded
  values, skipped edge cases, undecided semantics). They become plan
  items, not debt to fix during the probe.
- Stay inside the goal. Adjacent problems go in the plan's "observed,
  not addressed" list.
- Record **stumbling blocks**: places the approach itself fought back
  (an API that will not compose, a constraint that surfaced too late).
  Unlike a `SPIKE:` marker (a shortcut you chose) or an adjacent
  problem, a stumbling block is evidence the *approach* may be wrong:
  the reason to reach for the `spike-bakeoff` skill.

## Phase 3: Spike exit gate

Once proven, run the fast local buckets exactly as discovered:
`format`, `lint`, `typecheck`, and the scoped `test` command. Run
`build` only if the change plausibly affects build output; otherwise
note it as CI-deferred.

Gate failures here are **information, not work**: fix formatting, and
record the rest as plan items.

Run gates as discovered, including mutating ones (`--fix` linters,
formatters). If a gate changes any file, re-run the Phase 2 proving
check once: the stash must hold code proven *after* its last
modification.

## Phase 4: Stash with a recovery ref

Unless `--keep-tree`, stash everything, untracked files included, and
capture the stash's own SHA in the same command. Never read
`stash@{0}`: on an unchanged tree `git stash push` exits 0 and
`stash@{0}` is another stash's entry. Never split it into two commands
or run it in parallel with another stash in the repository.

Replace `<message>` with `spike: <goal> (<what passed, what's undecided>)`:

```sh
git add -A
sha=$(git stash create "<message>")
if [ -z "$sha" ]; then
  echo "no changes"
else
  git stash store -m "<message>" "$sha" && git reset -q --hard && echo "$sha"
fi
```

1. Record the printed SHA in the report; `git stash apply <sha>`
   restores it. The output `no changes` means record "no changes", not a
   SHA. Files matched by `.gitignore` are not stashed.
2. Verify the tree is back to its pre-spike state with `git status`.
   After a probe on top, run `git stash apply -q <baseline sha>`
   and then `git reset -q` to put the user's work back, and report
   the spike's own delta with `git diff <baseline sha> <spike sha>`.

## Phase 5: The replay plan

Produce the commit-by-commit plan. For each planned commit:

- **Subject** in the project's commit format (from Phase 0).
- **Contents**: which files/hunks from the stash it takes, and what gets
  rewritten rather than replayed.
- **Decisions to resolve**: each `SPIKE:` marker landing in this commit,
  as a question with a recommendation.
- **Gates**: the per-commit gate commands, right-sized per
  `references/verification-gates.md`.

Close the plan with the local-vs-CI table and the post-push watch
command: `gh pr checks --watch` for a PR, `gh run watch` when no PR
exists yet, or "none (no remote)".

## Phase 6: Replay (only with `--replay`, after approval)

1. `git stash apply <sha>` (apply, not pop). The stash stays until the
   replay finishes green.
2. Land plan items in order: stage only that item's changes, run its
   gates, commit with the planned message, written per
   `references/prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailers, and no emoji. A red gate
   stops the replay; report and hand back. Prefer file-level splits;
   to split one file, write the relevant hunks to a patch file and
   `git apply --cached <patch>` (`git add -p` is interactive).
3. After the final item: run any end-of-run `build` bucket, drop the
   stash by SHA, and if the branch has a remote counterpart offer to
   push and watch CI. Indexes shift as entries drop, so match the SHA:

```sh
ref=$(git stash list --format='%H %gd' | awk -v sha="<sha>" '$1 == sha {print $2; exit}')
[ -n "$ref" ] && git stash drop "$ref"
```

   An empty `ref` means the stash is already gone; drop nothing.

## Output contract

Write the report, and any replay commit message, per
`references/prose-rules.md`.

1. Hero block (1–3 lines): `✓ spike proven` / `⚠ spike blocked` +
   goal + exit path taken.

   A run that halts before probing (no commit, dirty tree declined,
   goal missing) is the hero line and one result sentence naming what
   is missing, then what the user must do next. No sections, no panel,
   no stash SHA, no local or temp paths.
2. `## Spike findings`: what was proven, stumbling blocks, `SPIKE:`
   markers, observed-not-addressed list. State stumbling blocks even
   when the probe succeeded: a path that fought you throughout is the
   case for the `spike-bakeoff` skill or the `spike-ratchet` skill.
3. `## Verification`: gate commands run and their results; the
   local-vs-CI split; what was deferred and why.
4. `## Stash`: message, SHA, restore command (omit with
   `--keep-tree`). A probe that changed nothing says "no changes"
   here instead of a SHA. After a probe on top, add the baseline SHA
   of the user's saved work.
5. `## Replay plan`: the numbered commit sequence from Phase 5.
6. End with an `ask-user-choice` panel: replay now / keep stash and
   stop / discard spike, unless already running inside plan mode or
   `--replay` was given. In a non-interactive run (CI, subagent),
   record the panel's question and options in the report instead of
   asking, and default to keeping the stash.

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
