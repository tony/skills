---
name: rebase
description: Use when asked to rebase the current branch onto remote trunk, check for file overlap, and resolve conflicts
allowed-tools: ["Bash", "Read", "Edit", "AskUserQuestion"]
disable-model-invocation: true
---

## Task

Rebase the current branch onto the remote trunk branch, phase by phase. Signed
commits (`commit.gpgsign`) prompt for the key on every replayed commit and
hooks may run; if a replay blocks on a prompt, run `git rebase --abort`, then
stop and tell the user.

### Phase 1: Inspect the repository and detect trunk

Gather the starting state:

1. `git --version` must report 2.30 or newer (`range-diff` and
   `--force-if-includes` need it); stop and say so otherwise.
2. `git branch --show-current` names the current branch. A failure means the
   directory is not a git repository: stop and say so. Empty output means a
   detached HEAD: stop and ask.
3. `git status --short` shows uncommitted changes; `--autostash` in Phase 3
   carries them across.
4. `git remote -v` lists the remotes. Stop if there are none.
5. Check for a rebase already in progress. `git rev-parse --git-path` prints a
   path whether or not it exists, so test the path:

```console
$ test -e "$(git rev-parse --git-path rebase-merge)" || test -e "$(git rev-parse --git-path rebase-apply)"
```

   Exit 0 means a rebase is in progress: stop and tell the user to finish or
   abort it first. Exit 1 means none.

Shell state does not persist between Bash calls: write the literal names
wherever `<remote>` and `<trunk>` appear below.

Pick `<remote>`, the remote that carries trunk:

1. `git config --get branch.<branch>.remote` names the remote the branch
   tracks. With one remote in total, use it.
2. A remote named `upstream` alongside a different tracking remote signals a
   fork, where the tracking remote's trunk is stale: use `upstream`, and say
   so in the report.
3. Otherwise use the tracking remote, even among several remotes.
4. With no tracking remote and several remotes, use the first of `upstream`
   or `origin` that exists. If neither exists, ask which remote carries
   trunk; with no question tool, stop.

Then determine `<trunk>`, the branch name without the remote prefix (every
use below prefixes `<remote>/`). Ask the remote first; it answers before any
fetch:

```console
$ git ls-remote --symref <remote> HEAD
```

`<trunk>` is the part of the `ref:` line after `refs/heads/`. If the remote is
unreachable, fall back to `git symbolic-ref --short refs/remotes/<remote>/HEAD`
(prints `<remote>/<branch>`; take the part after the slash), then to whichever
of `<remote>/main` or `<remote>/master` `git rev-parse --verify` resolves.

If the current branch is `<trunk>`, stop: there is nothing to rebase onto.

### Phase 2: Fetch latest and analyze

1. Run `git fetch <remote>` to get the latest remote state.
2. Stop early, as a stopped run (`⚠ Stopped: ...`, never `✓`), when there is
   nothing to do: already up to date (`git merge-base --is-ancestor
   <remote>/<trunk> HEAD` exits 0), or no commits ahead
   (`git rev-list --count <remote>/<trunk>..HEAD` prints `0`).
   A branch with no commits ahead that is behind trunk is a fast-forward:
   say so and print `git merge --ff-only <remote>/<trunk>` for the user.
3. Run `git log --oneline <remote>/<trunk>..HEAD` for the commits to rebase.
   If `git rev-list --merges --count <remote>/<trunk>..HEAD` is not `0`, stop:
   the rebase would flatten those merge commits. Report them and leave the
   choice (such as `git rebase --rebase-merges`) to the user.
4. Run `git diff --name-only <remote>/<trunk>...HEAD` for the files the branch
   changed, then `git diff --name-only HEAD...<remote>/<trunk>` for the files
   trunk changed since the fork. Files in both lists overlap.
5. Read the diff of each overlapping file on both sides.
6. With git 2.38 or newer, a dry run lists the files that would conflict:

```console
$ git merge-tree --write-tree --name-only HEAD <remote>/<trunk>
```

   Exit 0 means a clean merge; exit 1 prints a tree SHA, then the conflicted
   files. It simulates one merge, while the rebase replays each commit, so
   treat it as a hint. Older git has only the overlap lists.

Summarize the commit count, overlapping files, and the expected conflicts
(none / minor / significant), labeled as a reading of overlap, not a
guarantee.

### Phase 3: Execute the rebase

Record the safety facts first, in one command, and keep the printed values:

```console
$ git rev-parse HEAD && git merge-base HEAD <remote>/<trunk> && git rev-parse --abbrev-ref @{upstream}
```

The first SHA is the pre-rebase tip, the second the old base. A failing third
command means no upstream; otherwise it prints `<tracking remote>/<upstream
branch>`, which can differ from the local branch name. Recovery is
`git reset --keep <pre-rebase tip>`, run by the user from a clean tree
(`--keep` refuses to overwrite restored autostash changes; `--hard` would
discard them). It undoes the local branch
only: a branch already pushed needs the user to force-push the old tip too.

Then rebase onto the ref Phase 2 fetched:

```console
$ git rebase --autostash <remote>/<trunk>
```

If the rebase completes (exit code 0), skip to Phase 5. If it stops on
conflicts, continue with Phase 4.

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
      side silently. With no question tool (Codex, headless runs) during the
      rebase, run `git rebase --abort` and report both behaviors instead.
      After the rebase finished (Phase 5 autostash), see Phase 5.
   d. Run `git add <file>` to mark it resolved
3. Run `GIT_EDITOR=true git rebase --continue` (a bare `--continue` opens an
   editor and hangs a headless run); skip quality checks until Phase 5.
4. If more conflicts appear, repeat from step 1; once the rebase completes,
   go to Phase 5.
5. If the rebase becomes unrecoverable, run `git rebase --abort` and report.

### Phase 5: Verify final state

1. Run `git log --oneline -10` and `git status`; the tree must be clean or
   hold only the restored autostash changes.
   If the rebase output (from Phase 3, or from the `--continue` that finished
   Phase 4) said `Applying autostash resulted in conflicts`, the rebase is
   done and the stash is kept. Run `git rev-parse refs/stash` and keep that
   SHA. Resolve those files by the Phase 4 step 2c rules, then run `git
   restore --staged <file>` for each so the changes stay uncommitted. Where
   step 2c would ask and no question tool exists, leave the file conflicted
   with its markers; do not abort, since the rebase is done. Never run `git
   stash drop` or `git stash pop`, and never tell the user to: write "stash"
   and its full SHA, and say the stash is kept. The rebase finished, so this
   is a full report with the stash SHA under `## Rebase`. Use the hero `✓ Rebased ...` when
   every file was resolved, and `⚠ Rebased ...` naming each file left
   conflicted otherwise.
2. Compare content before and after, using the SHAs recorded in Phase 3:

```console
$ git range-diff <old base>..<pre-rebase tip> <remote>/<trunk>..HEAD
```

   A commit marked `=` replayed unchanged. For each `!`, read the inner diff
   `range-diff` prints beneath it: a difference confined to `@@`
   hunk headers or context lines is benign (trunk moved the surrounding code);
   an added or removed line must trace to a conflict resolution you made, and
   an unexplained one is a defect: report it and stop. A `<` commit has no
   match in the new range and a `>` commit has none in the old. When a `<` and
   a `>` share a subject, a small replayed patch fell below the matching
   threshold, so rerun with `--creation-factor=100` before reading either as
   dropped or new. A `<` still unpaired was dropped (trunk already holds the
   patch) and a `>` still unpaired is new; name each, and stop on any you
   cannot explain.
3. Run the project's quality checks (formatter, linter, type checker, tests)
   once, as its AGENTS.md or CLAUDE.md defines them. If a check fails, fix it
   in a new commit only when the user asks; report it. Run no other checks;
   with none defined, say so in one line.

Never push, and never offer to run a push: print the command and let the user
run it. The skill ends with the report.

## Output

Write the report per `../../references/prose-rules.md`. Open with a one-line
hero (`✓ Rebased N commits onto <remote>/<trunk>`, adding `, dropped M already on
trunk` when `range-diff` shows `<` commits, `⚠ Rebased ...` when the autostash
restore left a file conflicted, or `⚠ Stopped: <reason>`), then exactly these
sections:

1. `## Rebase`: commits replayed, conflicts and how each was resolved.
2. `## Content check`: the `range-diff` result, naming any `!` commit.
3. `## Checks`: each quality check and its result.
4. `## Recovery`: the pre-rebase tip SHA and the `git reset --keep` undo.
   With an upstream, also print the exact push command (`git push
   --force-with-lease --force-if-includes <tracking remote> HEAD:<upstream
   branch>`, both from the Phase 3 `@{upstream}` value) for the user to run.
   Without one, write only "<branch> has no upstream, so no push is needed":
   no push command, and no advice on publishing the branch.

Write the report impersonally: "Replayed 4be0d71", not "I replayed 4be0d71".

Write each commit message you create (none is expected) without a
`Co-Authored-By` line, a "Generated with" or other tool trailer, or emoji.

After the sections, ask what to do next via `AskUserQuestion`: inspect a `!`
commit's patch, or done. The push command is already printed; a request to
push is answered by pointing at it. Where no question tool exists (Codex,
headless runs), print the options as a plain list and stop.

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
  `git push --force-with-lease --force-if-includes origin HEAD:feature/search`.

Next: inspect a commit's patch, or done.
```

A stopped run is one result sentence (nothing to rebase, rebase aborted,
conflict needs a decision), then what the user needs to do. It has no sections
and no narration of the host's tools. Offer at most one combination for a
conflict, without analysis, unless the user asks. State the stop impersonally
("rebase aborted", not "I aborted"). Reply in this shape:

```text
⚠ Stopped: rebase aborted on a conflict in src/parser.py that needs your decision.

feature/strict is back at 4a61a04 with a clean tree; nothing was pushed.
Your commit keeps only known tokens, while trunk returns [""] for blank input.
Reply with which to keep: both, one side, or another combination.
```
