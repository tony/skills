---
name: bakeoff
description: "Use when building two to four competing strategies in isolated git worktrees to compare them without landing commits."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Agent"]
argument-hint: "[<goal>] [--strategies=\"a; b; c\"] [--prongs=<2-4>] [--keep-trees] [--replay]"
disable-model-invocation: true
---


# `/spike:bakeoff`

Multi-strategy spike harness. Where `/spike:probe` sends one
instrument down one path, a bakeoff enters 2–4 **deliberately
different strategies** for the same goal, builds each in its own git
worktree, judges them adversarially, and hands back a verdict plus a
commit-by-commit plan for the winner.

Every contender mutates its worktree freely. No contender touches
history: the worktrees are torn down after judging, and only stashes
(recoverable by SHA) and the verdict survive.

## Core thesis

When the approach is uncertain, building each strategy small and
comparing real evidence (diffs, gate results, blast radius, idiom fit)
beats arguing in the abstract. A bakeoff is N probes plus a judgment:
each contender follows the probe discipline (cheapest verification,
`SPIKE:` markers, stay in goal), and the bakeoff adds isolation,
blindness (contenders do not see each other), and adversarial judging.

A second bakeoff because the first winner hit new resistance means
`/spike:ratchet`, which carries a ledger across rounds.

## The Iron Rule

```
A BAKEOFF PRODUCES ZERO COMMITS
```

The zero-commit rule and its rationalization table are in
`../../references/spike-core.md` (Zero commits): no
commits in any worktree or on any contender branch, not even to snapshot
a contender. A worktree commit is no more harmless than a trunk commit,
and `git diff` across stash SHAs compares contenders fine. Losers are
graft material: stash every contender with a SHA before any teardown.

**Red flags (STOP):** `git commit` anywhere; `git worktree remove
--force` on a tree that has not been stashed; "snapshot commit";
merging a contender branch. All of these mean: stash with a SHA,
prune, and write the verdict.

## `$ARGUMENTS` contract

Non-flag text is the goal. Resolve it by the ladder below:

1. **Typed goal wins**: non-flag `$ARGUMENTS` text, verbatim.
2. **Empty → mine the conversation** (review findings, a failing
   test, an agreed problem). One strong candidate: adopt it (the
   Phase 1 brief is the confirmation gate). Several:
   `AskUserQuestion`; non-interactive: halt and name the candidates.
   None: ask; non-interactive: halt and name the missing goal.
3. **Record provenance** in the Phase 1 brief.

**Strategies** resolve by their own ladder:

1. `--strategies="a; b; c"`: semicolon-separated, verbatim, one
   contender each.
2. Otherwise, mine the conversation for competing options ("we could
   do A or B"); they become the contenders, with provenance.
3. Otherwise, propose 2–4 genuinely distinct strategies in the brief
   (different architecture, layer, or dependency posture, not cosmetic
   variants).

| Flag | Default | Effect |
|---|---|---|
| `--strategies="a; b; c"` | off | Explicit contender list; skips strategy mining. |
| `--prongs=<2-4>` | auto | Cap the number of contenders. |
| `--keep-trees` | off | Skip teardown; leave all worktrees in place for manual inspection. Each contender's work is stashed without being cleared (`stash --keep`), so the tree still shows it, and SHAs are recorded. |
| `--replay` | off | After the verdict and plan are approved, land the winner immediately: apply its stash, one gated commit per plan item. |

## Phase 0: Situational awareness

The shared steps live in `../../references/spike-core.md`; read it before
this phase. In every command, `<scripts>` stands for the absolute path of
`../../scripts` resolved from this skill's directory (the shell runs in the
project, not here); write that path literally.

Run its Preflight, resolving the gate buckets and CI split per
`../../references/verification-gates.md`. A bakeoff never probes on top of
the user's work, because `git worktree add ... HEAD` carries none of it:
offer only stash first or abort (non-interactive default: abort). It takes
no `--branch`. Once the brief is approved, run Setup's `save-user` before
the first worktree; its printed user-work SHA goes in the report with its
restore command. A rejected brief changes nothing. Then:

1. Confirm `git worktree` is usable and there is disk headroom for N
   checkouts.
2. Create the worktree root as described under "Worktree root" in the
   shared file.
3. Note any setup a fresh checkout needs to run gates (dependency
   install, codegen), because each kitchen must be able to bake.

## Phase 1: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

Present the **bakeoff brief**:

1. The goal, one line, with provenance (typed / inferred from what).
2. The contenders: one line per strategy stating what makes it
   *distinct*; merge entries that differ only cosmetically. Each is a
   full probe plus a judge per lens, so state the sub-agent count (N
   contenders plus the judges) and let the user confirm or trim it.
3. What "proven" means per contender: the shared smoke check every
   contender must pass to reach judging.
4. The judging rubric (the lenses in `bakeoff-round.md`, plus any goal-specific
   criteria the user cares about).
5. Discovered gate commands and the local-vs-CI split.
6. Worktree names and root; the exit path: stash-and-teardown /
   `--keep-trees` / `--replay`.

Wait for approval, then exit plan mode. If plan mode is unavailable,
present the brief inline and proceed on confirmation. In a
non-interactive run, record the brief in the report and proceed.

## Phase 2: The round

Run `../../references/bakeoff-round.md` in full: bake, gate, judge, then
stash and tear down. Its judging lenses and any goal-specific ones come
from the brief's rubric. Then:

1. After a stash-first Phase 0, restore the user's work with
   `<scripts>/spike.sh restore <user-work sha>` unless `--replay` runs,
   which restores it after its last item. A refused restore keeps the
   stash: report the SHA.
2. Under `--keep-trees`, name each kept worktree path in the report: the
   user must act on it (`git worktree remove`).

## Phase 3: The verdict and replay plan

Produce the verdict, then a commit-by-commit plan for the **winner's
stash**, built per `../../references/replay.md` (The replay plan:
subjects in the project's commit format, contents per commit,
`SPIKE:` decisions to resolve, per-commit gates), plus:

- **Grafts**: plan items that pull specific hunks from runner-up
  stashes (by SHA and file), stated as recommendations. Mark them
  **unproven in combination**: no contender was built with them. When
  they are too substantial to land blind, recommend re-probing: apply
  the winner's stash and the graft hunks, then run
  `/spike:probe` on that tree, answering its dirty-tree halt with
  *probe on top of it*. That proves winner-plus-grafts as one tree at
  zero commits.
- The losing strategies, one line each: why they lost, and under what
  conditions they would have won.

Close with the local-vs-CI table and the post-push watch command
when observable, as in the replay plan.

## Phase 4: Replay (only with `--replay`, after approval)

Follow `../../references/replay.md` (Replay) from the main checkout: apply
the winner's stash with `<scripts>/spike.sh replay-apply <sha>` (apply,
not pop), land plan items one gated commit at a time, apply graft hunks
from runner-up stashes where the plan says so, and only after the final
green gate drop the contender stashes by SHA with
`<scripts>/spike.sh drop`, never the user-work stash. Commit
messages follow that reference's rules.

Re-run the shared proving check before committing **each** plan item
that carries a graft, not once after the last: a graft in an early
commit is already history when a later check fails, and this phase never
rewrites commits. A graft that fails is dropped from the plan and
recorded as dropped; do not debug it here.

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
Report worktrees as removed only when `git worktree list` no longer shows them.
Warnings about the checkout (mode changes, files left in place, a tree
that needs attention) go inside `## Stashes`, never before the first section.

1. Hero block (1–3 lines): `✓ bakeoff judged: <winner>` /
   `⚠ bakeoff inconclusive` + goal + exit path taken.

   A run that halts before any worktree exists (no commit, repository
   rooted at home, dirty tree declined, missing code or goal) is a
   `⚠ bakeoff halted` hero line, one result sentence naming every
   blocker per `../../references/spike-core.md` (Halted run).
2. `## Contenders`: one line per strategy: what it tried, proven or
   blocked, headline gate status.
3. `## Verdict`: one plain line per lens naming each contender's standing
   (`Correctness: A holds, B ...`, no bold label), then the winner, the
   graft list, and why the losers lost.
4. `## Verification`: gate commands run per contender; local-vs-CI
   split; deferrals.
5. `## Stashes`: one bullet per contender: name, strategy, stash message,
   SHA, restore command. Every contender appears, losers included; one
   that changed nothing shows "no changes" in place of the SHA. A run that
   saved the user's work adds a bullet for it and says whether it was
   restored.
6. `## Replay plan`: the numbered commit sequence for the winner,
   grafts marked.
7. End with an `AskUserQuestion` panel: replay the winner / probe the
   grafted winner (still zero commits) / keep stashes
   and stop / discard all, unless already in plan mode or `--replay`
   was given. Recommend the probe exit when the verdict judged the grafts
   too substantial to land blind. In a non-interactive run, state the
   default taken ("Default: keep the stashes.") instead of asking.

A halted run replies in this shape:

```text
⚠ bakeoff halted: compare an LRU dict with a Redis-backed session cache.

Nothing was built: the working tree has uncommitted changes that a worktree would not carry.
Commit or stash them yourself, then run /spike:bakeoff again.
```

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Winner:** ...`), and no local paths:

```text
✓ bakeoff judged: B (write-behind cache)
Goal: cut p99 latency of the export endpoint. Exit path: stash and teardown.

## Contenders
- A, in-process LRU: proven; format, lint, and typecheck pass, 2 tests fail.
- B, write-behind cache: proven; all gates pass.
- C, query rewrite: blocked; the planner ignores the new index.

## Verdict
- Correctness: A and B pass the proving check; C is blocked.
- Blast radius: B touches two files, A touches five.
- Idiom fit: B matches the existing cache module.
- Gate status: A fails two tests; B passes all gates.
- Winner B. Graft from A: its eviction test.

## Verification
- Local: format, lint, typecheck, scoped tests. CI-only: integration suite.

## Stashes
- A, LRU: bakeoff 1-lru: in-process LRU (lost), 9f2c4d1, restore with git stash apply 9f2c4d1
- B, write-behind: bakeoff 2-write-behind: write-behind cache (won), 5ab3e08, restore with git stash apply 5ab3e08
- C, query rewrite: bakeoff 3-query: query rewrite (blocked), no changes

## Replay plan
1. cache(feat[store]) Add write-behind store
2. cache(test[store]) Cover flush and eviction (graft from A, unproven)
```
