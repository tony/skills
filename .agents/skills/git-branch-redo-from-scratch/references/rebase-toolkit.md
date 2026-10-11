# Interactive rebase without an editor

`git rebase -i` is built around two editor invocations: one for the
todo list, one per reworded message. An agent has no editor and no
TTY, so both must be replaced before any of it is usable.

## Contents

- The two hooks
- The toolkit script
- Reading the todo without side effects
- Config that changes the rules
- Verifying every commit
- Rewriting a message with no editor
- Recovering
- Things that eat commits

## The two hooks

`GIT_SEQUENCE_EDITOR` is invoked with the path to the todo list.
`GIT_EDITOR` is invoked with the path to a commit message.

Git runs each through the shell, appending the file path as the last
argument: a sequence editor of `cp -- plan.txt` runs
`cp -- plan.txt <todo-path>`, overwriting the todo with your plan.

Set `GIT_EDITOR=false`, never `true`, for any step that should not
need a message editor. `false` turns a step that would have blocked
into an immediate, loud failure; `true` silently accepts an empty
message.

## The toolkit script

`scripts/rebase-todo.sh`, at `./rebase-todo.sh` from this file,
wraps the idioms below. It refuses a dirty tree or an operation in
progress, and reports a rebase it left stopped.

`<toolkit>` is the absolute path to `rebase-todo.sh`; each skill states how
it resolves. A shell runs in the project's working directory, not this
plugin's, so use the literal path in every command.

Report any operation in progress, so a later command does not fail
mysteriously:

```console
$ sh <toolkit> status
```

Print the todo list for a range:

```console
$ sh <toolkit> show <base>
```

Replay the range using an edited plan as the todo list:

```console
$ sh <toolkit> apply <base> plan.txt
```

Run a command after every commit, in place:

```console
$ sh <toolkit> verify <base> 'make test'
```

Fold every pending `fixup!` and `amend!` commit:

```console
$ sh <toolkit> squash <base>
```

Exit 0 is success, 1 means git failed and may have left a rebase
stopped (the message says so and prints the abort command), 2 is a
usage error or a preflight refusal.

`RECUT_UPDATE_REFS=1` adds `--update-refs` so local branches pointing
into the range move with it. `RECUT_SIGN=1` re-signs the rewritten
commits.

## Reading the todo without side effects

Capturing the todo from a real `git rebase -i` replays the range and
changes SHAs. Generate the plain pick list instead:

```console
$ git log --reverse --no-merges --format='pick %h %s' <base>..HEAD
```

## Config that changes the rules

Three user settings silently change a scripted rebase. Pin all three.

`rebase.rebaseMerges=true` turns the todo from a flat pick list into
one containing `label`, `reset`, and `merge` lines. Code that assumes
every line is a `pick` will corrupt the rebase.

`rebase.missingCommitsCheck` defaults to `ignore`, so a commit whose
todo line goes missing disappears with exit 0 and no warning. Set it
to `error` for any generated plan.

`rebase.autoStash=true` suppresses git's refusal to rebase a dirty tree,
and a conflict while reapplying the autostash still exits 0, leaving
conflict markers. Check `git status --porcelain` yourself.

```console
$ git \
    -c rebase.rebaseMerges=false \
    -c rebase.missingCommitsCheck=error \
    -c rebase.autoStash=false \
    rebase -i <base>
```

## Verifying every commit

`--exec` runs a command after each commit and stops at the first
failure: the per-commit gate.

```console
$ git rebase --keep-base --exec 'make test' <base>
```

`--keep-base` is not optional. Without it, `git rebase --exec <cmd>
<upstream>` rebases the branch onto upstream as a side effect and
silently drops any commit that becomes empty, while still exiting 0.
With it, the tip SHA is unchanged and the run is a true in-place
check.

The command runs against each commit's worktree, so copy the harness
outside the repo and call it by absolute path. It must tolerate early
states of the series: a runner that fails when no tests exist yet
reports every early commit as broken.

## Rewriting a message with no editor

`git commit --fixup=reword:<sha>` requires an editor and is unusable
headless. Write the `amend!` commit by hand instead; `--autosquash`
treats it identically. Git rejects `-m` together with `-F`, so put
everything in the message file: the line `amend! <original subject>`,
a blank line, then the complete replacement message (its subject, a
blank line, its body). Everything after the first blank line becomes
the new message.

```console
$ git commit --allow-empty -F new-message.txt
```

Then fold it:

```console
$ GIT_SEQUENCE_EDITOR=true \
  GIT_EDITOR=false \
  git rebase -i --autosquash <base>
```

## Recovering

A failed `--exec` or a conflict leaves the rebase in progress on a
detached HEAD, which poisons every later git command until it is
cleared.

`git rebase --abort` restores the branch. `git rebase --quit` leaves HEAD
detached at the half-rewritten result and restores nothing.

Detect an in-progress operation with `status` (or `preflight` in
`branch-safety.md`), never from HEAD: `git status` reports a detached HEAD
with no sign a rebase is underway. The script resolves each marker through
[`git rev-parse --git-path`](https://git-scm.com/docs/git-rev-parse),
because in a linked worktree `.git` is a file.

## Things that eat commits

- A plain rebase drops commits that are patch-identical to something
  already upstream. Keeping them needs both `--reapply-cherry-picks`
  and `--empty=keep`.
- Rewriting without `--update-refs` strands any other local branch
  that pointed into the range on the orphaned history. Check with
  `git branch --contains` first.
- A rebase strips GPG and SSH signatures from every commit it
  rewrites unless `commit.gpgSign` is set or `-S` is passed.
- Piping `git rebase` into a truncating command such as `head` kills
  it mid-rebase and leaves stale state. Redirect to a file instead.
