---
name: ratchet
description: "Use when asked to spike, bake off, then spike again; rinse and repeat, keep spiking, converge on a design, and stop when nothing new fights back."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Agent"]
argument-hint: "[<goal>] [--rounds=<n>] [--replay]"
user-invocable: true
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

Inherited whole from `/spike:probe`, including its rationalization
table, regardless of round count. Rounds end in stashes; commits happen
only in `--replay`, after the final plan is approved.

**Red flag** unique to this skill: "round 3 is basically final, commit
it as a checkpoint so round 4 has a base." Round 4 starts from the
stash, and the ledger is the base.

## The ledger

One markdown file, written outside the working tree. `spike.sh` (see
`../probe/SKILL.md`, which says how its path resolves) creates and prints
the directory it lives in; use the printed path literally afterwards:

```console
$ spike.sh ledger-dir
```

The ledger lives at `<that path>/<goal-slug>.md`. A ledger in the
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

Read `../probe/SKILL.md` and follow its Phase 0 once for the whole
ratchet: commit check, conventions files, the five gate buckets and CI
split per `../../references/verification-gates.md`, and the dirty-tree
halt. Every round starts from a clean tree, so offer only stash first or
abort there (non-interactive default: abort); never "probe on top". The
ratchet takes no `--branch`. The user-work SHA that stash first prints
goes in the ledger and the report. Then:

1. Resolve the ledger path and read it if it already exists.
2. Confirm `git worktree` is usable, since any round may call a
   bakeoff.

## Phase 1: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

Present the **ratchet brief**:

1. The goal, one line, with provenance.
2. What "converged" means for this goal: the demo or property the
   final design must satisfy, not just the first round's smoke check.
3. The round cap, and any rounds already in the ledger.
4. Discovered gate commands and the local-vs-CI split.
5. The ledger path.
6. The intended exit: clean rewrite, or landing plan.

Wait for approval, then exit plan mode. If plan mode is unavailable,
present the brief inline and proceed on confirmation. In a
non-interactive run, record the brief and proceed.

## Phase 2: A round

Repeat until Phase 3 says stop. Each round:

1. **Probe.** Read `../probe/SKILL.md` and follow its Phases 2 through 4
   against the goal as sharpened by the ledger's open questions. Probe's
   Phase 0 and brief already ran above; its plan and replay phases
   belong to the ratchet's exit, and so does restoring the user's
   work: skip the restore in its Phase 4.
2. **Branch on what fought back.** A stumbling block with two or more
   genuinely different resolutions calls for `/spike:bakeoff`: read
   `../bakeoff/SKILL.md` and follow its Phases 2 through 5 with those
   resolutions as contenders; the ratchet's Phase 0 and brief stand in
   for the bakeoff's. A block with one obvious fix folds into the next
   probe. Stash serially: one stash command at a time, never from
   parallel contenders.
3. **Re-probe the graft.** Grafts are unproven in combination, so the
   ratchet seeds the next round's tree (apply the winner's stash, then
   the graft hunks) and that round probes from there. Probe's
   dirty-tree halt does not fire on a tree the ratchet seeded. A graft
   that fails the check is dropped and recorded as dropped.
4. **Record.** Append the round's ledger section before the next round;
   a round without its entry did not happen.

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
Restore the user's saved work first with
`spike.sh restore <user-work sha>`, unless `--replay` runs, which
restores it after its last item. A refused restore keeps the stash:
report the SHA. Offer the two exits. Write any commit message per
`../../references/prose-rules.md`, with no `Co-Authored-By`, no
"Generated with" or other tool trailers, and no emoji:

- **Clean rewrite**: after approval, write the final implementation
  from the ledger's locked decisions, keeping the final stash as
  reference. Run the fast gates once. The result stays uncommitted and
  `--replay` is not involved; committing it is the user's call. Right
  when the code carries the marks of abandoned rounds.
- **Landing plan**: a commit-by-commit plan for the final stash, built
  as Phase 5 of `../probe/SKILL.md`, landed under `--replay` as its
  Phase 6. Right when the last round's code is what the design wants.

Recommend one and say why. Never drop earlier stashes; the ledger cites
them by SHA.

## Output contract

Write the report per `../../references/prose-rules.md`.

1. Hero block (1–3 lines): `✓ converged in <n> rounds` /
   `⚠ capped at <n> rounds` / `⚠ thrashing, stopped at round <n>` +
   the goal.

   A run that halts before round 1 (no commit, repository rooted at
   home, dirty tree declined, missing code or goal) is a
   `⚠ ratchet halted` hero line and one result sentence naming what is
   missing, then what the user must do next. No sections, no panel, no
   stash SHAs, no local or temp paths, no command echo, no description
   of the environment.
2. `## Rounds`: one block per round: what was probed, what fought
   back, bakeoff winner if any, what got locked.
3. `## Design`: the locked decisions as a specification, not a history.
4. `## Open`: questions the ratchet did not settle, and for a thrashing
   stop, why spiking cannot settle them.
5. `## Stashes`: table: round, stash message, SHA, restore
   command. Every round appears (a round that changed nothing shows
   "no changes"), and so does every contender a round's bakeoff
   stashed; those stashes outlive the ratchet. A run that saved the
   user's work adds a row for it and says whether it was restored.
6. `## Next`: the recommended exit, and the landing plan when one was
   produced.
7. End with an `AskUserQuestion` panel: rewrite from the ledger / land
   the final stash / run another round / stop and keep the ledger,
   unless already in plan mode or `--replay` was given. In a
   non-interactive run, record the question and default to stopping
   with the ledger kept.

A halted run replies in this shape:

```text
⚠ ratchet halted: converge on an async/await port of the retry queue.
The repository has no commits yet. Make the initial commit yourself, then run /spike:ratchet again with the same goal.
```

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Round 1:** ...`), the `## Stashes`
table aside:

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
| Round | Stash message | SHA | Restore |
|---|---|---|---|
| 1 | spike: asyncio port, round 1 | 1d8e0b7 | git stash apply 1d8e0b7 |

## Next
- Recommended: clean rewrite from the ledger; the final stash still carries round 2's abandoned executor shim.
```
