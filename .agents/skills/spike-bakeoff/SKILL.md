---
name: spike-bakeoff
description: >-
  Use when building two to four competing strategies in isolated git
  worktrees to compare them without landing commits.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
metadata:
  argument-hint: "[<goal>] [--strategies=\"a; b; c\"] [--prongs=<2-4>] [--keep-trees] [--replay]"
  source: "plugins/spike/skills/bakeoff/SKILL.md"
---

# this skill

Multi-strategy spike harness. Where the `spike-probe` skill sends one
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
the `spike-ratchet` skill, which carries a ledger across rounds.

## The Iron Rule

```
A BAKEOFF PRODUCES ZERO COMMITS
```

Inherited from the `spike-probe` skill: no commits in any worktree or on any
contender branch, not even to snapshot a contender.

| Rationalization | Reality |
|---|---|
| "It's a throwaway worktree — a commit there is harmless" | Worktree branches outlive worktrees and leak into PRs. Stash, then prune. |
| "Committing each contender makes them easier to diff" | `git stash show -p <sha>` and `git diff` across stash SHAs diff fine. Stash. |
| "The winner is decided — commit it straight from its worktree" | The winner exits as a stash and a plan; commits happen in `--replay`, one gated plan item at a time, from the main checkout. |
| "The losers don't matter — force-remove their worktrees" | Losers are graft material for the synthesis. Stash every contender with a SHA before any teardown. |

**Red flags (STOP):** `git commit` anywhere; `git worktree remove
--force` on a tree that has not been stashed; "snapshot commit";
merging a contender branch. All of these mean: stash with a SHA,
prune, and write the verdict.

## `$ARGUMENTS` contract

Non-flag text is the goal. Resolve it by the same ladder as
the `spike-probe` skill:

1. **Typed goal wins**: non-flag `$ARGUMENTS` text, verbatim.
2. **Empty → mine the conversation** (review findings, a failing
   test, an agreed problem). One strong candidate: adopt it (the
   Phase 1 brief is the confirmation gate). Several:
   `ask-user-choice`. None: ask.
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
| `--keep-trees` | off | Skip teardown; leave all worktrees in place for manual inspection. Stashes are still created and SHAs recorded. |
| `--replay` | off | After the verdict and plan are approved, land the winner immediately: apply its stash, one gated commit per plan item. |

## Phase 0: Situational awareness

Read the `spike-probe` skill and follow its Phase 0: commit check,
conventions files, the five gate buckets and CI split per
`references/verification-gates.md`, and the dirty-tree halt.
Then the bakeoff-specific checks:

1. Confirm `git worktree` is usable and there is disk headroom for N
   checkouts.
2. Choose a worktree root outside the repo (e.g. a sibling temp
   directory) and contender names: `bakeoff/<n>-<slug>`.
3. Note any setup a fresh checkout needs to run gates (dependency
   install, codegen), because each kitchen must be able to bake.

## Phase 1: Orchestration plan

Enter plan mode if the host supports it (Claude Code:
`EnterPlanMode`; Cursor / Codex / Gemini: `/plan` or `Shift+Tab`) and
present the **bakeoff brief**:

1. The goal, one line, with provenance (typed / inferred from what).
2. The contenders: one line per strategy stating what makes it
   *distinct*; merge entries that differ only cosmetically.
3. What "proven" means per contender: the shared smoke check every
   contender must pass to reach judging.
4. The judging rubric (Phase 4 lenses, plus any goal-specific
   criteria the user cares about).
5. Discovered gate commands and the local-vs-CI split.
6. Worktree names and root; the exit path: stash-and-teardown /
   `--keep-trees` / `--replay`.

Wait for approval, then exit plan mode. If plan mode is unavailable,
present the brief inline and proceed on confirmation. In a
non-interactive run, record the brief in the report and proceed.

## Phase 2: The bake

For each contender, create its worktree and run it as an independent
sub-agent (Task tool) when the host supports it, or sequentially
otherwise:

```console
$ git worktree add <root>/<n>-<slug> HEAD
```

Each contender follows the Phase 2 discipline in the `spike-probe` skill
inside its own worktree, aiming at the shared "proven" check.

Contenders are **blind to each other**: no shared scratch files, no
peeking. They bake in parallel but never stash: the coordinator stashes
in Phase 5, one contender at a time, because every worktree shares one
stash stack.

A contender that cannot reach "proven" exits with a failure note (what
blocked it), which is evidence for the verdict.

## Phase 3: Contest exit gate

In each worktree, run the fast local buckets exactly as discovered:
`format`, `lint`, `typecheck`, scoped `test`, right-sized per
`references/verification-gates.md`. Gate results are **judging
inputs, not work**: fix only formatting; record everything else on the
scorecard. If a mutating gate changes files, re-run the shared proving
check once.

## Phase 4: Judging

Adversarial comparison, one pass per lens, each judge trying to
**refute** the contender's claim to the win rather than admire it:

- **Correctness**: does the proving check really demonstrate the
  goal, or does a `SPIKE:` marker hide the hard part?
- **Blast radius**: diff size and files touched; what does each
  approach entangle?
- **Simplicity / idiom fit**: which reads like the project already
  wrote it?
- **Gate status**: what passed, what failed, what was deferred.
- Any goal-specific lenses from the brief (performance, migration
  cost, dependency posture).

Run the lenses as independent sub-agent judges when the host supports
them, otherwise sequentially. Produce a scorecard per contender, a
**winner**, and a **graft list**: ideas from runners-up worth carrying
into the winner's plan (a test case, an edge-case guard).

A split verdict is valid: report `⚠ inconclusive` with the scorecards.

## Phase 5: Stash all contenders, then tear down

**Stash first, prune second**, one contender at a time, never in
parallel. For each contender:

1. In its worktree, run the stash sequence from the `spike-probe` skill
   Phase 4 with the message
   `bakeoff/<n>-<slug>: <strategy> (<verdict>)`. It captures the
   stash's own SHA in the same command; never read `stash@{0}`, which
   is another contender's entry when this one changed nothing. A
   contender that printed `no changes` is recorded as "no changes",
   not given a SHA.
2. Record the printed SHA; `git stash apply <sha>` recovers it from the
   main checkout after its worktree is gone.
3. Only after the SHA is recorded, check what removal will delete.
   Files matched by `.gitignore` (build output, `.env`, local caches)
   are not stashed and go with the worktree:

```console
$ git -C <root>/<n>-<slug> status --ignored --short
```

   List any ignored files in the report, then remove the worktree
   (skip with `--keep-trees`):

```console
$ git worktree remove <root>/<n>-<slug>
```

4. After all contenders: `git worktree prune`, and verify the main
   tree is untouched (`git status`).

## Phase 6: The verdict and replay plan

Produce the verdict, then a commit-by-commit plan for the **winner's
stash**, built as the probe's Phase 5 in the `spike-probe` skill
(subjects in the project's commit format, contents per commit,
`SPIKE:` decisions to resolve, per-commit gates), plus:

- **Grafts**: plan items that pull specific hunks from runner-up
  stashes (by SHA and file), stated as recommendations. Mark them
  **unproven in combination**: no contender was built with them. When
  they are too substantial to land blind, recommend re-probing: apply
  the winner's stash and the graft hunks, then follow
  the `spike-probe` skill on that tree, answering its dirty-tree halt with
  *probe on top of it*. That proves winner-plus-grafts as one tree at
  zero commits.
- The losing strategies, one line each: why they lost, and under what
  conditions they would have won.

Close with the local-vs-CI table and the post-push watch command
when observable, as in probe.

## Phase 7: Replay (only with `--replay`, after approval)

Follow Phase 6 of the `spike-probe` skill from the main checkout: apply
the winner's stash (apply, not pop), land plan items one gated commit
at a time, apply graft hunks from runner-up stashes where the plan
says so, and only after the final green gate drop the contender
stashes by SHA, using the SHA-matching drop in that phase. Commit
messages follow the probe's rules: no `Co-Authored-By`, no "Generated
with" or other tool trailers, no emoji.

Re-run the shared proving check before committing **each** plan item
that carries a graft, not once after the last: a graft in an early
commit is already history when a later check fails, and this phase never
rewrites commits. A graft that fails is dropped from the plan and
recorded as dropped; do not debug it here.

## Output contract

Write the report, and any replay commit message, per
`references/prose-rules.md`.

1. Hero block (1–3 lines): `✓ bakeoff judged: <winner>` /
   `⚠ bakeoff inconclusive` + goal + exit path taken.

   A run that halts before any worktree exists (no commit, dirty tree
   declined, missing code or goal) is a `⚠ bakeoff halted` hero line
   and one result sentence naming what is missing, then what the user
   must do next. No sections, no panel, no stash SHAs, no local or
   temp paths.
2. `## Contenders`: one line per strategy: what it tried, proven or
   blocked, headline gate status.
3. `## Verdict`: scorecards per lens, the winner, the graft list,
   and why the losers lost.
4. `## Verification`: gate commands run per contender; local-vs-CI
   split; deferrals.
5. `## Stashes`: table: contender, strategy, stash message, SHA,
   restore command. Every contender appears, losers included; one that
   changed nothing shows "no changes" in the SHA column.
6. `## Replay plan`: the numbered commit sequence for the winner,
   grafts marked.
7. End with an `ask-user-choice` panel: replay the winner / probe the
   grafted winner (still zero commits) / keep stashes
   and stop / discard all, unless already in plan mode or `--replay`
   was given. Recommend the probe exit when Phase 6 judged the grafts
   too substantial to land blind. In a non-interactive run, record the
   question in the report and default to keeping the stashes.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Winner:** ...`), the `## Stashes`
table aside:

```text
✓ bakeoff judged: B (write-behind cache)
Goal: cut p99 latency of the export endpoint. Exit path: stash and teardown.

## Contenders
- A, in-process LRU: proven; format, lint, and typecheck pass, 2 tests fail.
- B, write-behind cache: proven; all gates pass.
- C, query rewrite: blocked; the planner ignores the new index.

## Verdict
- Winner B: smallest blast radius and the closest fit to the existing
  cache module.
- Graft from A: its eviction test.

## Verification
- Local: format, lint, typecheck, scoped tests. CI-only: integration suite.

## Stashes
| Contender | Strategy | Stash message | SHA | Restore |
|---|---|---|---|---|
| A | LRU | bakeoff/1-lru: in-process LRU (lost) | 9f2c4d1 | git stash apply 9f2c4d1 |

## Replay plan
1. cache(feat[store]) Add write-behind store
2. cache(test[store]) Cover flush and eviction (graft from A, unproven)
```


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
