---
name: rebase
description: Rebase current branch onto trunk (origin/master or origin/main), predict and resolve conflicts
allowed-tools: ["Bash", "Read", "Edit", "AskUserQuestion"]
user-invocable: true
disable-model-invocation: true
---

## Task

Rebase the current branch onto the remote trunk branch, phase by phase.

### Phase 1: Inspect the repository and detect trunk

Gather the starting state:

1. `git branch --show-current` names the current branch. A failure means the
   directory is not a git repository: stop and say so. Empty output means a
   detached HEAD: stop and ask.
2. `git status --short` shows uncommitted changes; `--autostash` in Phase 3
   carries them across.
3. `git remote -v` lists the remotes. Stop if there is no `origin`.
4. If `git rev-parse --git-path rebase-merge` or `git rev-parse --git-path
   rebase-apply` exists, stop and tell the user to finish or abort that
   rebase first.

Then determine the trunk name as `TRUNK`, the **bare** name (every use below
adds `origin/`). Shell state does not persist between Bash calls: write the
literal name wherever `${TRUNK}` appears below. Ask the remote first; it
answers before any fetch:

```console
$ git ls-remote --symref origin HEAD
```

`TRUNK` is the part of the `ref:` line after `refs/heads/`. If the remote is
unreachable, fall back to `git symbolic-ref --short refs/remotes/origin/HEAD`
(prints `origin/<branch>`; take the part after the slash), then to whichever
of `origin/main` or `origin/master` `git rev-parse --verify` resolves.

If the current branch is `TRUNK`, stop: there is nothing to rebase onto.

### Phase 2: Fetch latest and analyze

1. Run `git fetch origin` to get the latest remote state.
2. Stop early with a one-line result when there is nothing to do: no commits
   ahead (`git rev-list --count origin/${TRUNK}..HEAD` prints `0`) or already
   up to date (`git merge-base --is-ancestor origin/${TRUNK} HEAD` exits 0).
3. Run `git log --oneline origin/${TRUNK}..HEAD` for the commits to rebase.
   If `git rev-list --merges --count origin/${TRUNK}..HEAD` is not `0`, stop:
   the rebase would flatten those merge commits. Report them and leave the
   choice (such as `git rebase --rebase-merges`) to the user.
4. Run `git diff --name-only origin/${TRUNK}...HEAD` for the files the branch
   changed, then `git diff --name-only HEAD...origin/${TRUNK}` for the files
   trunk changed since the fork. Files in both lists are the potential
   conflict zones.
5. Read the diff of each overlapping file on both sides.

Summarize the commit count, overlapping files, and conflict likelihood (none
expected / minor / significant).

### Phase 3: Execute the rebase

Record the safety facts first, in one command, and keep the printed values:

```console
$ git rev-parse HEAD && git merge-base HEAD origin/${TRUNK} && git rev-parse --abbrev-ref @{upstream}
```

The first SHA is the pre-rebase tip, the second the old base. A failing third
command means no upstream. Recovery is `git reset --keep <pre-rebase tip>`,
run by the user from a clean tree (`--keep` refuses to overwrite restored
autostash changes; `--hard` would discard them).

Then rebase onto the ref Phase 2 fetched:

```console
$ git rebase --autostash origin/${TRUNK}
```

If the output says `Applying autostash resulted in conflicts`, the rebase
finished and the stash is kept. Run `git rev-parse refs/stash` and keep that
SHA. Resolve those files by the Phase 4 step 2 rules, then run `git restore
--staged <file>` for each so the changes stay uncommitted. Run `git stash
drop` only after `git stash show -p` matches what the resolved files now
hold; if unsure, keep the stash and report its SHA.

If the rebase completes cleanly (exit code 0), skip to Phase 5.

### Phase 4: Resolve conflicts (if any)

If conflicts are detected:

1. Run `git status` to list conflicted files.
2. For each conflicted file:
   a. Read the conflict markers
   b. Compare what the branch intended with what trunk changed
   c. Resolve mechanical conflicts directly (context drift, adjacent hunks, a
      list both sides appended to), integrating trunk's structural changes
      (renames, new parameters). When the two sides give the same code
      competing behaviors, ask the user via `AskUserQuestion`; never pick a
      side silently. With no question tool (Codex, headless runs), run
      `git rebase --abort` and report both behaviors instead.
   d. Run `git add <file>` to mark it resolved
3. Run `GIT_EDITOR=true git rebase --continue` (a bare `--continue` opens an
   editor and hangs a headless run); skip quality checks until Phase 5.
4. If more conflicts appear, repeat from step 1.
5. If the rebase becomes unrecoverable, run `git rebase --abort` and report.

### Phase 5: Verify final state

1. Run `git log --oneline -10` and `git status`; the tree must be clean or
   hold only the restored autostash changes.
2. Compare content before and after, using the SHAs recorded in Phase 3:

```console
$ git range-diff <old base>..<pre-rebase tip> origin/${TRUNK}..HEAD
```

   A commit marked `=` replayed unchanged. For each `!`, run the same command
   without `--no-patch` and read the inner diff: a difference confined to `@@`
   hunk headers or context lines is benign (trunk moved the surrounding code);
   an added or removed line must trace to a conflict resolution you made, and
   an unexplained one is a defect: report it and stop. A `<` commit was
   dropped (trunk already holds the patch) and a `>` commit is new; name
   each, and stop on any you cannot explain.
3. Run the project's quality checks (formatter, linter, type checker, tests)
   once, as its AGENTS.md or CLAUDE.md defines them. If a check fails, fix it
   in a new commit only when the user asks; report it.

Never push. The skill ends with the report and the user decides the next step.

## Output

Write the report per `../../references/prose-rules.md`. Open with a one-line
hero (`✓ Rebased N commits onto origin/<trunk>` or `⚠ Stopped: <reason>`), then
exactly these sections:

1. `## Rebase` - commits replayed, conflicts and how each was resolved.
2. `## Content check` - the `range-diff` result, naming any `!` commit.
3. `## Checks` - each quality check and its result.
4. `## Recovery` - the pre-rebase tip SHA and the `git reset --keep` undo.
   With an upstream, also print the exact push command (`git push
   --force-with-lease --force-if-includes origin <branch>`) for the user to
   run. Without one, say no push is needed.

Write each commit message you create (none is expected) without a
`Co-Authored-By` line, a "Generated with" or other tool trailer, or emoji.

After the sections, ask what to do next via `AskUserQuestion`: push with the
printed command, inspect a `!` commit's patch, or done. Where no question
tool exists (Codex, headless runs), print the options as a plain list and
stop; never push without an explicit ask.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
✓ Rebased 2 commits onto origin/main

## Rebase

- Replayed 4be0d71 and 9a3f1c2 onto trunk; no conflicts.

## Content check

- range-diff shows both commits as `=`.

## Checks

- Tests and lint pass.

## Recovery

- Pre-rebase tip 4be0d71; undo with `git reset --keep 4be0d71`.
- Upstream is origin/feature/search; after review, push with
  `git push --force-with-lease --force-if-includes origin feature/search`.

Next: push the branch, inspect a commit's patch, or done.
```

A stopped run is one result sentence (nothing to rebase, rebase aborted,
conflict needs a decision), then what the user needs to do. It has no sections
and no narration of the host's tools. Reply in this shape:

```text
⚠ Stopped: rebase aborted on a conflict in src/parser.py that needs your decision.

feature/strict is back at 4a61a04 with a clean tree; nothing was pushed.
Your commit keeps only known tokens, while trunk returns [""] for blank input.
Tell me which to keep: both, one side, or another combination.
```
