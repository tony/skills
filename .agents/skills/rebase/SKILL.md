---
name: rebase
description: >-
  Rebase current branch onto trunk (origin/master or origin/main), predict
  and resolve conflicts
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit"]
metadata:
  source: "plugins/rebase/skills/rebase/SKILL.md"
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

Then determine the trunk branch name and store it as `TRUNK`, the **bare**
name: every use below prefixes it with `origin/` itself, so storing
`origin/main` here would ask git for `origin/origin/main`.

Ask the remote first, because it answers before anything has been fetched:

```
git ls-remote --symref origin HEAD
```

The `ref:` line names the remote's default branch, so `TRUNK` is the part after
`refs/heads/`. A repository built with `git init` plus `git remote add` has no
remote-tracking refs until Phase 2 fetches, so local lookups cannot answer this
yet.

If the remote is unreachable, fall back to `git symbolic-ref --short
refs/remotes/origin/HEAD` (which prints `origin/<branch>`; take the part after
the slash), and failing that to whichever of `origin/main` or `origin/master`
`git rev-parse --verify` resolves.

### Phase 2: Fetch latest and analyze

1. Run `git fetch origin` to get the latest remote state.
2. Run `git diff origin/${TRUNK}...HEAD --stat` to see what the branch changes.
3. Run `git log --oneline origin/${TRUNK}..HEAD` to see the commits that will be rebased.
4. Run `git diff --name-only origin/${TRUNK}...HEAD` for the files the branch
   changed, then `git diff --name-only HEAD...origin/${TRUNK}` for the files
   trunk changed since the branch forked. Files in both lists are the potential
   conflict zones. If the branch list is empty, there are none.
5. Read the diff of each overlapping file on both sides to judge how the
   changes interact.

Report a brief summary of:
- How many commits will be rebased
- Which files the branch changed
- Which of those files trunk also changed
- An assessment of conflict likelihood (none expected / minor / significant)

### Phase 3: Execute the rebase

Run:
```
git pull --rebase origin ${TRUNK} --autostash
```

If the rebase completes cleanly (exit code 0), skip to Phase 5.

### Phase 4: Resolve conflicts (if any)

If conflicts are detected:

1. Run `git status` to see which files have conflicts.
2. For each conflicted file:
   a. Read the file to see the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
   b. Understand both sides by examining what the branch intended vs what trunk changed
   c. Resolve the conflict by editing the file, preserving the intent of both changes when possible. When in doubt, prefer the branch's changes, but integrate trunk's changes if they are structural (renames, new parameters, etc.)
   d. Run `git add <file>` to mark it resolved
3. Before continuing the rebase, run the project's quality checks (formatter,
   linter, type checker, tests) as its AGENTS.md or CLAUDE.md defines them. If
   any check fails, fix the issues and re-stage with `git add`.
4. Run `git rebase --continue` to proceed.
5. If more conflicts appear, repeat from step 1 of this phase.
6. If the rebase becomes unrecoverable, run `git rebase --abort` and report what went wrong.

### Phase 5: Verify final state

1. Run `git log --oneline -10` to confirm the rebased history looks correct.
2. Run `git status` to confirm a clean working tree.
3. Run the project's quality checks once more.
4. Report how many commits were rebased, whether any conflicts were resolved, and the result of each quality check.

Never force-push. Report the final state and let the user decide the next step.
