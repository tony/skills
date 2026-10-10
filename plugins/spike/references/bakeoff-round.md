# Bakeoff round

The contender mechanics `/spike:bakeoff` and a `/spike:ratchet` round that
bakes off share: bake each contender in its own worktree, gate it, judge
the set, stash every contender, and tear the worktrees down. `<scripts>`
and the worktree root are as defined in `spike-core.md`.

Contents:

- Bake
- Contest exit gate
- Judging
- Stash all contenders, then tear down

## Bake

For each contender, create its worktree and run it as an independent
sub-agent when the host supports it, or sequentially
otherwise:

```console
$ git worktree add \
    --detach \
    <root>/<n>-<slug> \
    HEAD
```

Each contender follows the probe loop in `spike-core.md`
inside its own worktree, aiming at the shared "proven" check. Tell every
sub-agent its worktree's absolute path and to work only inside it: read
and edit by absolute path under that directory, begin every Bash command
with `cd <that path> &&` (the shell's directory resets between calls),
and never touch the main checkout or another worktree.

Contenders are **blind to each other**: no shared scratch files, no
peeking. They bake in parallel but never stash: the coordinator stashes
under "Stash all contenders" below, one contender at a time, because every worktree shares one
stash stack.

A contender that cannot reach "proven" exits with a failure note (what
blocked it), which is evidence for the verdict.

## Contest exit gate

In each worktree, run the fast local buckets exactly as discovered:
`format`, `lint`, `typecheck`, scoped `test`, right-sized per
`verification-gates.md`. Gate results are **judging
inputs, not work**: fix only formatting; record everything else on the
scorecard. If a mutating gate changes files, re-run the shared proving
check once.

## Judging

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

## Stash all contenders, then tear down

**Stash first, prune second**, one contender at a time, one `spike.sh`
stash command per Bash call, never in parallel or batched: every worktree
shares one stash stack and the script refuses an overlapping stash. For each
contender:

1. In its worktree, run the Stash steps in `spike-core.md`
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

   Report the ignored files and confirm they are disposable output of this
   contender. Preserve anything else before removing the worktree
   (skip with `--keep-trees`). `teardown` removes bytecode and ignored output
   with `--force` when needed, but refuses remaining source edits, staged
   changes, or commits absent from the recorded stash. If `--leave` kept
   other files, keep the worktree or explicitly approve their removal first:

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
