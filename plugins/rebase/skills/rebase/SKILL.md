---
name: rebase
description: Rebase current branch onto trunk (origin/master or origin/main), predict and resolve conflicts
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
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
2. `git status --short` shows uncommitted changes. `--autostash` in Phase 3
   carries them across the rebase.
3. `git remote -v` lists the remotes. Stop if there is no `origin`.
4. `git rev-parse --git-path rebase-merge` and `git rev-parse --git-path
   rebase-apply` name the directories git keeps while a rebase is in
   progress. If either exists, stop and tell the user to finish or abort that
   rebase first.

Then determine the trunk branch name and store it as `TRUNK`, the **bare**
name: every use below prefixes it with `origin/` itself, so storing
`origin/main` here would ask git for `origin/origin/main`.

Ask the remote first, because it answers before anything has been fetched:

```console
$ git ls-remote --symref origin HEAD
```

The `ref:` line names the remote's default branch, so `TRUNK` is the part after
`refs/heads/`. A repository built with `git init` plus `git remote add` has no
remote-tracking refs until Phase 2 fetches, so local lookups cannot answer this
yet.

If the remote is unreachable, fall back to `git symbolic-ref --short
refs/remotes/origin/HEAD` (which prints `origin/<branch>`; take the part after
the slash), and failing that to whichever of `origin/main` or `origin/master`
`git rev-parse --verify` resolves.

If the current branch is `TRUNK`, stop: there is nothing to rebase onto.

### Phase 2: Fetch latest and analyze

1. Run `git fetch origin` to get the latest remote state.
2. Stop early with a one-line result when there is nothing to do: no commits
   ahead (`git rev-list --count origin/${TRUNK}..HEAD` prints `0`) or already
   up to date (`git merge-base --is-ancestor origin/${TRUNK} HEAD` exits 0).
3. Run `git diff origin/${TRUNK}...HEAD --stat` to see what the branch changes.
4. Run `git log --oneline origin/${TRUNK}..HEAD` to see the commits that will be rebased.
5. Run `git diff --name-only origin/${TRUNK}...HEAD` for the files the branch
   changed, then `git diff --name-only HEAD...origin/${TRUNK}` for the files
   trunk changed since the branch forked. Files in both lists are the potential
   conflict zones. If the branch list is empty, there are none.
6. Read the diff of each overlapping file on both sides to judge how the
   changes interact.

Summarize for the report: how many commits will be rebased, which files the
branch changed, which of those trunk also changed, and the conflict likelihood
(none expected / minor / significant).

### Phase 3: Execute the rebase

Record the safety facts first, in one command, and keep the printed values:

```console
$ git rev-parse HEAD && git merge-base HEAD origin/${TRUNK} && git rev-parse --abbrev-ref @{upstream}
```

The first SHA is the pre-rebase tip, the second the old base. A failing third
command means the branch has no upstream and was likely never pushed. If it
has one, the rebased history diverges from it and the user will need a
force-push, which this skill never does. Recovery is `git reset --hard <pre-rebase
tip>` from the user, or `git reflog` to find it.

Then run:

```console
$ git pull --rebase origin ${TRUNK} --autostash
```

If the output says `Applying autostash resulted in conflicts`, the rebase
itself finished, the conflict markers are in the working tree, and the stash
is kept. Resolve those files under the Phase 4 rules, then run `git stash drop`
and `git restore --staged <file>` for each, so the changes stay uncommitted.

If the rebase completes cleanly (exit code 0), skip to Phase 5.

### Phase 4: Resolve conflicts (if any)

If conflicts are detected:

1. Run `git status` to see which files have conflicts.
2. For each conflicted file:
   a. Read the file to see the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
   b. Understand both sides by examining what the branch intended vs what trunk changed
   c. Resolve mechanical conflicts directly (context drift, adjacent hunks, a
      list both sides appended to), integrating trunk's structural changes
      (renames, new parameters). When the two sides give the same code
      competing behaviors, ask the user via `AskUserQuestion`; never pick a
      side silently. With no question tool (Codex, headless runs), run
      `git rebase --abort` and report both behaviors instead.
   d. Run `git add <file>` to mark it resolved
3. Run `git rebase --continue` to proceed. Do not run the quality checks
   mid-rebase; Phase 5 runs them once on the final result.
4. If more conflicts appear, repeat from step 1 of this phase.
5. If the rebase becomes unrecoverable, run `git rebase --abort` and report what went wrong.

### Phase 5: Verify final state

1. Run `git log --oneline -10` to confirm the rebased history looks correct.
2. Run `git status` to confirm a clean working tree (or only the restored
   autostash changes).
3. Compare content before and after, using the SHAs recorded in Phase 3:

```console
$ git range-diff <old base>..<pre-rebase tip> origin/${TRUNK}..HEAD
```

   A commit marked `=` replayed unchanged; `!` shows a changed patch. Every
   `!` must trace to a conflict resolution you made. An unexplained one is a
   defect: report it and stop.
4. Run the project's quality checks (formatter, linter, type checker, tests)
   once, as its AGENTS.md or CLAUDE.md defines them. If a check fails, fix it
   in a new commit only when the user asks; report it.

Never force-push. The skill ends here and the user decides the next step.

## Output

Write the report per `../../references/prose-rules.md`. Open with a one-line
hero (`✓ Rebased N commits onto origin/<trunk>` or `⚠ Stopped: <reason>`), then
exactly these sections:

1. `## Rebase` - commits replayed, conflicts and how each was resolved.
2. `## Content check` - the `range-diff` result, naming any `!` commit.
3. `## Checks` - each quality check and its result.
4. `## Recovery` - the pre-rebase tip SHA, and whether the branch now needs a
   force-push.

A stopped run is one result sentence (nothing to rebase, rebase aborted,
conflict needs a decision), then what the user needs to do. It has no sections.
