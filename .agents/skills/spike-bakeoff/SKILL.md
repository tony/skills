---
name: spike-bakeoff
description: >-
  Use when building two to four competing strategies in isolated git
  worktrees to compare them without landing commits.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Agent"]
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

Inherited from the `spike-probe` skill, rationalization table included: no
commits in any worktree or on any contender branch, not even to snapshot
a contender. A worktree commit is no more harmless than a trunk commit,
and `git diff` across stash SHAs compares contenders fine. Losers are
graft material: stash every contender with a SHA before any teardown.

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
   `ask-user-choice`; non-interactive: halt and name the candidates.
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

The shared steps live in `references/spike-core.md`; read it before
this phase. In every command, `<scripts>` stands for the absolute path of
`../../scripts` resolved from this skill's directory (the shell runs in the
project, not here); write that path literally.

Run its Preflight, resolving the gate buckets and CI split per
`references/verification-gates.md`. A bakeoff never probes on top of
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
sub-agent when the host supports it, or sequentially
otherwise:

```console
$ git worktree add \
    --detach \
    <root>/<n>-<slug> \
    HEAD
```

Each contender follows the probe loop in `references/spike-core.md`
inside its own worktree, aiming at the shared "proven" check. Tell every
sub-agent its worktree's absolute path and to work only inside it: read
and edit by absolute path under that directory, begin every Bash command
with `cd <that path> &&` (the shell's directory resets between calls),
and never touch the main checkout or another worktree.

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

**Stash first, prune second**, one contender at a time, one `spike.sh`
stash command per Bash call, never in parallel or batched: every worktree
shares one stash stack and the script refuses an overlapping stash. For each
contender:

1. In its worktree, run the Stash steps in `references/spike-core.md`
   (`untracked`, message file, `stash -F`) with the message
   `bakeoff <n>-<slug>: <strategy> (<verdict>)`, adding `--keep` before
   `-F` under `--keep-trees` so the worktree keeps the work. A contender
   that printed `no changes` is recorded as "no changes", not given a SHA.
2. Record the printed SHA; `git stash apply <sha>` recovers it from the
   main checkout after its worktree is gone.
3. Only after the SHA is recorded, check what removal will delete.
   Files matched by `.gitignore` (build output, `.env`, local caches)
   are not stashed and go with the worktree:

```console
$ git -C <root>/<n>-<slug> status --ignored --short
```

   List any ignored files in the report, then remove the worktree
   (skip with `--keep-trees`). Files the stash left in place (bytecode,
   `--leave` paths) make a plain remove refuse; the work is already
   stashed, so `teardown` retries with `--force`:

```console
$ <scripts>/spike.sh teardown <root>/<n>-<slug> <stash sha>
```

   Pass `none` in place of the SHA for a contender that printed
   `no changes`. The script refuses a SHA that is not a listed stash.

   It prints `removed` only when `git worktree list` no longer shows the
   worktree; otherwise it exits non-zero and the report names that worktree
   as still present.

4. After all contenders: run `git worktree list` and verify the main
   tree is untouched (`git status`).
5. After a stash-first Phase 0, restore the user's work with
   `<scripts>/spike.sh restore <user-work sha>` unless `--replay` runs,
   which restores it after its last item. A refused restore keeps the
   stash: report the SHA. Under `--keep-trees`, name each kept worktree
   path in the report: the user must act on it (`git worktree remove`).
   the `spike-ratchet` skill follows steps 1 through 4 and skips this restore.

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
the winner's stash with `<scripts>/spike.sh replay-apply <sha>` (apply,
not pop), land plan items one gated commit at a time, apply graft hunks
from runner-up stashes where the plan says so, and only after the final
green gate drop the contender stashes by SHA with
`<scripts>/spike.sh drop`, never the user-work stash. Commit
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
Report worktrees as removed only when `git worktree list` no longer shows them.
Warnings about the checkout (mode changes, files left in place, a tree
that needs attention) go inside `## Stashes`, never before the first section.

1. Hero block (1–3 lines): `✓ bakeoff judged: <winner>` /
   `⚠ bakeoff inconclusive` + goal + exit path taken.

   A run that halts before any worktree exists (no commit, repository
   rooted at home, dirty tree declined, missing code or goal) is a
   `⚠ bakeoff halted` hero line, one result sentence naming every
   blocker (order and rule as in the `spike-probe` skill's output contract),
   then one line with what the user must do next. No sections, no panel,
   no stash SHAs, no local or temp paths, no command echo, no description
   of the environment. The result sentence names only the blockers, never
   why a file or tree is in that state.
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
7. End with an `ask-user-choice` panel: replay the winner / probe the
   grafted winner (still zero commits) / keep stashes
   and stop / discard all, unless already in plan mode or `--replay`
   was given. Recommend the probe exit when Phase 6 judged the grafts
   too substantial to land blind. In a non-interactive run, state the
   default taken ("Default: keep the stashes.") instead of asking.

A halted run replies in this shape:

```text
⚠ bakeoff halted: compare an LRU dict with a Redis-backed session cache.

Nothing was built: the working tree has uncommitted changes that a worktree would not carry.
Commit or stash them yourself, then run spike-bakeoff again.
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


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
