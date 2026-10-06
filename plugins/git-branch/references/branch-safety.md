# Not losing the user's work

A recommit rewrites history that may be published and may be the only
copy of a day's work. Each gate prevents a silent loss.

## Contents

- Refuse before starting
- The pushed-branch gate
- Back up before touching anything
- Recovery
- Pushing the result

## Refuse before starting

Each of these halts the run with a report, not a warning:

- **A dirty working tree.** Check `git status --porcelain` yourself;
  `rebase.autoStash=true` makes git stash and proceed.
- **An operation already in progress.** Probe the git dir for
  `rebase-merge`, `rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`,
  `REVERT_HEAD`, `BISECT_LOG`, `sequencer`, each resolved through
  `git rev-parse --git-path`; HEAD is not the test.
- **Merge commits in the range.** Collapsing across one erases another
  author's commits while keeping their content.
- **The branch checked out in another worktree.** It cannot be
  rewritten in place; `git worktree list --porcelain` names the
  holder.
- **A shallow clone**, which cannot be reasoned about historically.

Report but do not necessarily halt on: a stale submodule pointer (a later
`git add -A` bakes it in); an active sparse checkout (file listings are
incomplete); and signed commits, which a rebase strips unless signing
is re-enabled.

```
git log --format='%h %G? %s' <base>..HEAD
```

## The pushed-branch gate

Rewriting a branch someone else may have checked out needs the user's
explicit consent.

```
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
```

No upstream means local-only; proceed. With an upstream, read the
remote's true tip **without** `git fetch`:

```
git ls-remote --heads origin <branch>
```

`fetch` refreshes the remote-tracking ref and destroys the
`--force-with-lease` protection you are about to rely on.

Then decide whether rewriting drops commits that exist only on the
remote:

```
git merge-base --is-ancestor <remote-tip> HEAD
```

A non-zero exit means someone else pushed, or the remote tip is not
local yet. Halt. Report the SHA from `ls-remote`. To name who pushed,
fetch by URL into a scratch ref; a fetch by remote name also refreshes
`origin/<branch>` and defeats the lease:

```
git fetch "$(git remote get-url origin)" <branch>:refs/remote-check/<branch>
```

```
git log --format='%h %an %s' HEAD..refs/remote-check/<branch>
```

## Back up before touching anything

A reflog entry is not a backup: unreachable entries expire after 30
days. Use a branch, not a tag or raw ref; only a branch is discoverable
and has a reflog of its own.

```
git branch "backup/<branch>-$(date -u +%Y%m%dT%H%M%SZ)" <branch>
```

Keep the name a single flat segment after `backup/`: git refuses a
branch whose name is a path prefix of an existing one, so `backup/x` and
`backup/x/<timestamp>` cannot coexist.

Do not rely on `ORIG_HEAD`; the next reset, merge, or pull overwrites it.

Report the backup branch name in the final output.

## Recovery

Undo a rewrite of the checked-out branch from its backup. `<branch>@{1}`
is only the previous reflog step, correct for a rewrite that moved the
branch once:

```
git reset --hard backup/<branch>-<ts>
```

Restore a branch that is not checked out:

```
git branch --force <branch> <backup-sha>
```

Never delete and recreate a branch to move it — that destroys its
reflog.

When no ref or reflog points at the work any more:

```
git fsck --unreachable --no-reflogs
```

Never run `git reflog expire --expire-unreachable=now --all` as
cleanup. It destroys the user's entire stash list.

## Pushing the result

Pushing is always an explicit, separate decision. The recommit itself
stops at the local branch.

```
git push --force-with-lease --force-if-includes origin <branch>
```

Bare `--force-with-lease` compares against your remote-tracking ref, so
any `git fetch` between the rewrite and the push (an editor, a background
job, another agent) makes the lease pass and destroys a colleague's
commit. `--force-if-includes` additionally requires the remote tip to
have been integrated locally; it is a no-op unless paired with *bare*
`--force-with-lease`.

The alternative, immune to background fetches, is to capture the lease
SHA before rewriting:

```
git push --force-with-lease=<branch>:<captured-sha> origin <branch>
```

Never bare `--force`: it disables the fast-forward check on every ref
pushed, which can overwrite refs nobody intended to touch.
