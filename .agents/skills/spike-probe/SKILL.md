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
a neat commit-by-commit plan, optionally replaying it immediately.

A probe **mutates the working tree freely**; mutation is the point:
the code is the sensing instrument. What it never touches is history:
like an attached kprobe, it patches the live system to take its
measurement and detaches without a trace in `git log`.

## Core thesis

A spike answers "does this path work?" It is **evidence, not a
deliverable**. The probe's value survives as (a) a stash you can
reapply and (b) decisions the plan records. Committing spike code
converts unreviewed exploration into history.

Verify with the cheapest signal while probing, run the project's fast
gates once at exit, and defer what CI covers to CI. The plan is the
product: a numbered commit sequence mapping stash contents to commits.

## The Iron Rule

```
A SPIKE PRODUCES ZERO COMMITS
```

Not on trunk, not on the feature branch, not on a scratch branch,
not "just to checkpoint". The exit paths are: stash (default),
`--keep-tree` (leave changes unstaged), or `--replay` (commits happen
only *after* the plan is presented and approved, one plan item at a
time, each behind a green gate).

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
   verbatim. Conversation context may enrich it (file paths, error
   messages already discussed) but never overrides it.
2. **Empty → mine the conversation.** Candidate goals are review
   findings just presented, a failing test under discussion, a pasted
   stack trace, or a suggestion the user agreed with.
   - Exactly one strong candidate: adopt it and proceed to Phase 1;
     the brief there is the confirmation gate.
   - Several candidates: `ask-user-choice` (multi-select), one option
     per candidate plus "all of them".
   - None: ask what to probe before touching anything.
3. **Record provenance.** The Phase 1 brief states where the goal
   came from: typed, or inferred from which part of the
   conversation.

When the inferred goal is a set of review findings, note the boundary
in the brief: a probe explores fixes with zero commits; screening those
findings is the `respond-check` skill and landing them commit-by-commit is
the `respond-action` skill.

| Flag | Default | Effect |
|---|---|---|
| `--branch=<name>` | off | Run the probe on a new scratch branch from the current HEAD instead of the current branch's tree. Still zero commits; the branch only isolates the working tree. |
| `--keep-tree` | off | Skip the stash at spike exit; leave changes in the working tree for the user to inspect. The plan is still produced. |
| `--replay` | off | After the plan is approved, immediately implement it: apply the stash, land plan items one commit at a time, each behind a green gate. |

## Phase 0: Situational awareness

Before writing any code:

1. Confirm a git repository with at least one commit:

```console
$ git rev-parse --verify HEAD
```

   A failure means no repository or no commits, and stash and
   worktrees both need a commit to hang on. Halt before touching
   anything: say what is missing and that the user must make the
   initial commit (a spike never commits).
2. Read `AGENTS.md` / `CLAUDE.md` / `.github/CONTRIBUTING.md` for
   quality checks, commit format, and test conventions.
3. Resolve the five gate buckets (`format`, `lint`, `typecheck`,
   `test`, `build`) and the CI-coverage split per
   `references/verification-gates.md`.
4. Record the working tree state with `git status --porcelain`. A
   dirty tree halts here: ask the user whether to stash their work
   first, probe on top of it, or abort. Never mix the probe with
   uncommitted user work silently. Non-interactive default: abort.
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
Cursor / Codex / Gemini: `/plan` or `Shift+Tab`) and present a
**short** spike brief:

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
non-interactive run (CI, subagent), record the brief in the report
and proceed. Keep this to seconds, not minutes; it is a probe.

## Phase 2: The probe

Code the shortest path to "proven". During this phase:

- Verify with the **cheapest signal that moves you forward**: run the
  one test file or smoke command that exercises the new code. Do not
  run the full suite, the build, or repeated broad test passes while
  iterating.
- Mark shortcuts as you take them (a `SPIKE:` comment on hardcoded
  values, skipped edge cases, undecided semantics). These become plan
  items, not debt to fix during the probe.
- Stay inside the goal. Adjacent problems you notice go in the plan's
  "observed, not addressed" list.
- Record **stumbling blocks**, the places the approach itself fought
  back: an API that will not compose, a type that cannot be expressed,
  a constraint that surfaced too late to design around. A stumbling
  block is neither a `SPIKE:` marker (a shortcut you chose) nor an
  adjacent problem (out of scope); it is evidence the *approach* may be
  wrong, which makes it the reason to reach for the `spike-bakeoff` skill and
  the input the next probe sharpens against.

## Phase 3: Spike exit gate

Once proven, run the fast local buckets exactly as discovered:
`format`, `lint`, `typecheck`, and the scoped `test` command. Run
`build` only if the change plausibly affects build output; otherwise
note it as CI-deferred.

Gate failures here are **information, not work**: fix trivial ones
(formatting), and record non-trivial ones as plan items. The point is
that the plan below describes code whose gate status is *known*, not
guessed.

Gate commands run **as discovered**, including mutating ones
(`--fix`-style linters, formatters). If a gate changes any file,
re-run the proving smoke check from Phase 2 once before moving on;
the stash must contain code that was proven *after* its last
modification.

## Phase 4: Stash with a recovery ref

Unless `--keep-tree`, stash everything, untracked files included,
and capture the stash's own SHA in the same command. Never read
`stash@{0}`: `git stash push` prints "No local changes to save" and
exits 0 on an unchanged tree, and `stash@{0}` is then another stash's
entry. Never run it as two commands, and never in parallel with
another stash in the same repository.

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

1. Record the printed SHA in the report. A dropped or popped stash is
   otherwise unrecoverable; with the SHA it can be restored with
   `git stash apply <sha>`. The output `no changes` means the probe
   changed nothing: record "no changes", not a SHA. Files matched by
   `.gitignore` are not stashed.
2. Verify the tree is back to its pre-spike state with `git status`.
   After a probe on top, run `git stash apply -q <baseline sha>`
   and then `git reset -q` to put the user's work back, and report
   the spike's own delta with `git diff <baseline sha> <spike sha>`.

## Phase 5: The replay plan

Produce the commit-by-commit plan. For each planned commit:

- **Subject** in the project's commit format (from Phase 0).
- **Contents**: which files/hunks from the stash it takes, and what
  gets rewritten rather than replayed (e.g. test-first where the
  project's conventions demand it).
- **Decisions to resolve**: every `SPIKE:` marker that lands in this
  commit, stated as a question with a recommendation.
- **Gates**: the per-commit gate commands (fast buckets, scoped
  tests), per verification-gates.md right-sizing.

Close the plan with the local-vs-CI table and the post-push watch
command when one is observable: `gh pr checks --watch` for a PR,
`gh run watch` when no PR exists yet, or an explicit "none (no
remote)" so the deferral is visible rather than implied.

## Phase 6: Replay (only with `--replay`, after approval)

1. `git stash apply <sha>` (apply, not pop). The stash stays until the
   replay finishes green.
2. Land plan items in order: stage only that item's changes, run its
   gates, commit with the planned message, written per
   `references/prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailers, and no emoji. A red gate
   stops the replay; report and hand back. Prefer plan items that split at
   **file level**; when one file must split across commits,
   materialize per-commit patch slices (`git diff` the relevant
   hunks to a file, then `git apply --cached <patch>`). Interactive
   staging (`git add -p`) is not available to an agent.
3. After the final item: run any end-of-run `build` bucket, drop the
   stash by SHA, and if the branch has a remote counterpart offer to
   push and watch CI. `stash@{n}` indexes shift as entries drop, so
   find the entry whose SHA matches and drop only that one:

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
   markers, observed-not-addressed list. State the stumbling blocks
   even when the probe succeeded: a path that worked while fighting
   you the whole way is the case for the `spike-bakeoff` skill or
   the `spike-ratchet` skill, and reporting only the success buries it.
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


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
