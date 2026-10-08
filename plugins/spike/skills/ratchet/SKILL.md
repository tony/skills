---
name: ratchet
description: "Use when asked to spike, bake off, then spike again; rinse and repeat, keep spiking, converge on a design, and stop when nothing new fights back."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Agent"]
argument-hint: "[<goal>] [--rounds=<n>] [--replay]"
---


# `/spike:ratchet`

Convergence harness. `/spike:probe` answers "does this path work?",
`/spike:bakeoff` "which path is best?". Neither answers "what is the
right design?", which emerges from hitting real code several times and
watching what keeps fighting back. The ratchet runs both in rounds until
the design stops resisting.

## Core thesis

Across rounds the code is disposable and **the ledger is the
product**: each round keeps what it learned (approaches rejected,
decisions settled, questions open) and discards its implementation.

Run a ratchet when the shape of the answer is unknown, such as a port
to another language. One clear approach is `/spike:probe`; two or three
named approaches competing once is `/spike:bakeoff`.

## The Iron Rule

```
EVERY ROUND PRODUCES ZERO COMMITS
```

Inherited whole from `/spike:probe`, rationalization table included,
regardless of round count. Rounds end in stashes; commits happen
only in `--replay`, after the final plan is approved.

**Red flag** unique to this skill: "round 3 is basically final, commit
it as a checkpoint so round 4 has a base." Round 4 starts from the
stash, and the ledger is the base.

## The ledger

One markdown file, written outside the working tree. `spike.sh` creates
and prints the directory it lives in; use the printed path literally
afterwards. In every command, `<scripts>` stands for the absolute path of
`../../scripts` resolved from this skill's directory (the shell runs in
the project, not here); write that path literally:

```console
$ <scripts>/spike.sh ledger-dir
```

The ledger lives at `<that path>/<goal-slug>.md`. When the git directory
refuses the write, the script prints a fresh `spike-ledger.XXXXXX`
directory under `${TMPDIR:-/tmp}` instead, and a write into the printed
directory that still fails goes to `mktemp -d "${TMPDIR:-/tmp}/spike-ledger.XXXXXX"`.
The report's `## Stashes` section ends with a ledger bullet: `spike/<goal-slug>.md`
in the git directory, or the full temp path when the fallback was used,
since the user must act on that path to keep the ledger. A ledger in the
working tree gets swallowed by the round's stash or erased by
`git clean -xdf`; the common dir resolves to one path from every
bakeoff worktree.

Name the ledger in the Phase 1 brief as `spike/<goal-slug>.md` under
the repository's git directory; show the absolute path only if asked.
Append to an existing ledger; never truncate it.

Each round appends one section:

- **Probed**: what this round built, and its stash SHA.
- **Stumbling blocks**: what fought back, per `/spike:probe`'s
  definition. New ones only; repeats are marked as repeats.
- **Bakeoff**: contenders, winner, why, and which grafts were taken
  (omit when no bakeoff ran this round).
- **Locked**: decisions that will not be revisited, with the evidence
  that settled them.
- **Open**: questions carried into the next round.

Keep every entry to a line or two.

## `$ARGUMENTS` contract

Non-flag text is the goal, resolved by the same ladder as
`/spike:probe`: typed goal wins, empty mines the conversation,
provenance recorded in the brief.

| Flag | Default | Effect |
|---|---|---|
| `--rounds=<n>` | 3 | Cap on rounds run unprompted; only the closing panel takes it further. |
| `--replay` | off | At Phase 4, land the approved plan per Phase 6 of `../probe/SKILL.md` instead of stopping at the panel. Never applies to a round. |

## Phase 0: Situational awareness

Read `../../references/spike-core.md` and run its Preflight once for the
whole ratchet: guard, conventions files, the five gate buckets and CI
split per `../../references/verification-gates.md`, and the dirty-tree
halt. Every round starts from a clean tree, so offer only stash first or
abort there (non-interactive default: abort); never "probe on top". The
ratchet takes no `--branch`. After the brief is approved, run Setup's
`save-user` before round 1; the user-work SHA it prints goes in the ledger
and the report. Then:

1. Resolve the ledger path and read it if it already exists.
2. Confirm `git worktree` is usable, since any round may call a
   bakeoff, and create the worktree root once as described under
   "Worktree root" in the shared file; every round's bakeoff reuses it.

## Phase 1: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

Present the **ratchet brief**:

1. The goal, one line, with provenance.
2. What "converged" means for this goal: the demo or property the
   final design must satisfy, not just the first round's smoke check.
3. The round cap, any rounds already in the ledger, and the worst-case
   cost: each round is one probe, possibly a bakeoff of N contenders,
   and a judge per lens, so state the rounds times that sub-agent count
   and let the user confirm or trim the cap.
4. Discovered gate commands and the local-vs-CI split.
5. The ledger path.
6. The intended exit: clean rewrite, or landing plan.

Wait for approval, then exit plan mode. If plan mode is unavailable,
present the brief inline and proceed on confirmation. In a
non-interactive run, record the brief and proceed. A rejected brief
changes nothing.

## Phase 2: A round

Repeat until Phase 3 says stop. Each round:

1. **Probe.** Follow the probe loop and Exit gate in
   `../../references/spike-core.md`, then its Stash steps, against the
   goal as sharpened by the ledger's open questions. The ratchet's
   Phase 0 and brief already ran, so skip Setup. The plan and replay
   phases belong to the ratchet's exit, and so does restoring the user's
   work: never run `restore` between rounds.
2. **Branch on what fought back.** A stumbling block with two or more
   genuinely different resolutions calls for `/spike:bakeoff`: read
   `../bakeoff/SKILL.md` and follow its Phases 2 through 4 and Phase 5
   steps 1 through 4 with those resolutions as contenders, using the
   worktree root from Phase 0. Skip its Phase 0 (the ratchet's stands in
   for it), its brief, and Phase 5 step 5, which would restore the user's
   work mid-run. A block with one obvious fix folds into the next probe.
   Stash serially: one stash command per Bash call, never from parallel
   contenders.
3. **Re-probe the graft.** Grafts are unproven in combination, so the
   ratchet seeds the next round's tree (`<scripts>/spike.sh replay-apply <winner
   sha>`, then the graft hunks) and that round probes from there. The
   dirty-tree halt does not fire on a tree the ratchet seeded. A graft
   that fails the check is dropped and recorded as dropped.
4. **Record.** Append the round's ledger section before the next round;
   a round without its entry did not happen.

Round-2 and later contenders branch from `HEAD`, not from a tree seeded
with the previous winner; a seeded tree is probed in the main checkout.

Except when carrying grafts, a round starts from a clean tree (the
user's own work waits in the stash from Phase 0) and inherits the
ledger's locked decisions, not the code.

## Phase 3: Convergence test

Stop when any of these holds, tested in this order. Say which one in
the report:

- **Converged**: the round surfaced no stumbling block.
- **Thrashing**: the round surfaced at least one stumbling block and
  every one was already recorded and decided earlier. More spiking cannot
  settle the question; stop and surface it.
- **Capped**: `--rounds` is exhausted. Report the open questions
  plainly.

Otherwise start the next round from the ledger's open questions.

## Phase 4: Exit

The surviving artifacts are the ledger and every round's stash SHA.
Offer the two exits. Write any commit message per
`../../references/prose-rules.md`, with no `Co-Authored-By`, no
"Generated with" or other tool trailers, and no emoji:

- **Clean rewrite**: after approval, write the final implementation
  from the ledger's locked decisions, keeping the final stash as
  reference. Write it on the clean tree, before the user's work comes
  back, so it never mixes with their edits. Run the fast gates once. The
  result stays uncommitted and `--replay` is not involved; committing it
  is the user's call. Right when the code carries the marks of abandoned
  rounds.
- **Landing plan**: a commit-by-commit plan for the final stash, built
  as Phase 5 of `../probe/SKILL.md`, landed under `--replay` as its
  Phase 6. Right when the last round's code is what the design wants.

Then restore the user's saved work with
`<scripts>/spike.sh restore <user-work sha>`, unless `--replay` runs, which
restores it after its last item. After a clean rewrite, list the rewrite's
files in the report so the user can tell them from their own edits. A
refused restore keeps the stash: report the SHA.

Recommend one and say why. Never drop earlier stashes; the ledger cites
them by SHA.

## Output contract

Write the report per `../../references/prose-rules.md`.

The first line of the reply is exactly the hero line: no lead-in sentence,
no first-person opener. Report results, not process: never narrate a
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
that needs attention) go inside `## Stashes`, never before the first section.

1. Hero block (1–3 lines): `✓ converged in <n> rounds` /
   `⚠ capped at <n> rounds` / `⚠ thrashing, stopped at round <n>` +
   the goal.

   A run that halts before round 1 (no commit, repository rooted at
   home, dirty tree declined, missing code or goal) is a
   `⚠ ratchet halted` hero line, one result sentence naming every
   blocker (order and rule as in `../probe/SKILL.md`'s output contract),
   then one line with what the user must do next. No sections, no panel,
   no stash SHAs, no local or temp paths, no command echo, no description
   of the environment. The result sentence names only the blockers, never
   why a file or tree is in that state.
2. `## Rounds`: one block per round: what was probed, what fought
   back, bakeoff winner if any, what got locked.
3. `## Design`: the locked decisions as a specification, not a history.
4. `## Open`: questions the ratchet did not settle, and for a thrashing
   stop, why spiking cannot settle them.
5. `## Stashes`: one bullet per stash: round, stash message, SHA,
   restore command. Every round appears (a round that changed nothing
   shows "no changes"), and so does every contender a round's bakeoff
   stashed; those stashes outlive the ratchet. A run that saved the
   user's work adds a bullet for it and says whether it was restored.
6. `## Next`: the recommended exit, and the landing plan when one was
   produced.
7. End with an `AskUserQuestion` panel: rewrite from the ledger / land
   the final stash / run another round / stop and keep the ledger,
   unless already in plan mode or `--replay` was given. In a
   non-interactive run, state the default taken ("Default: stop, ledger
   kept.") instead of asking.

A halted run replies in this shape:

```text
⚠ ratchet halted: converge on an async/await port of the retry queue.

Nothing was probed: the repository has no commits yet.
Make the initial commit yourself, then run /spike:ratchet again with the same goal.
```

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Round 1:** ...`), and no local paths:

```text
✓ converged in 3 rounds: port the sync worker to asyncio

## Rounds
- Round 1: probed a direct await conversion; the DB client blocks the loop.
- Round 2: bakeoff of thread executor vs async driver; async driver won. Locked: async driver.
- Round 3: no new stumbling blocks.

## Design
- Use the async driver behind a thin repository interface.
- Cancellation propagates through the worker's task group.

## Open
- Whether the metrics exporter needs its own loop.

## Stashes
- Round 1: spike: asyncio port, round 1, 1d8e0b7, restore with git stash apply 1d8e0b7
- Round 2: spike: asyncio port, round 2, 6c40a93, restore with git stash apply 6c40a93

## Next
- Recommended: clean rewrite from the ledger; the final stash still carries round 2's abandoned executor shim.
```
