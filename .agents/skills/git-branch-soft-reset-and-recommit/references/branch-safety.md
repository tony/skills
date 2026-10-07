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

- **A dirty working tree.** Check `git status --porcelain` yourself,
  untracked files included; `rebase.autoStash=true` makes git stash and
  proceed. The toolkit script ignores untracked files, so this check is
  the stricter one.
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
- **An unborn HEAD** (`git rev-parse --verify HEAD` fails): there is
  nothing to rewrite or study.
- **A repository rooted at `$HOME`, or at a directory containing it.**
  Compare `git rev-parse --show-toplevel` with the physical home path
  from `cd ~ && pwd -P`, never the string `$HOME` (a symlinked home
  slips past it); a dotfile repo
  there makes every untracked file, credentials included, part of the
  work. The report says "credential files" and names none of them.

Report but do not necessarily halt on: a stale submodule pointer (a later
blanket add would bake it in); an active sparse checkout (file listings are
incomplete); and signed commits, which a rebase strips unless signing
is re-enabled.

```console
$ git log --format='%h %G? %s' <base>..HEAD
```

## The pushed-branch gate

Rewriting a branch someone else may have checked out needs the user's
explicit consent.

```console
$ git rev-parse --abbrev-ref --symbolic-full-name '@{u}'
```

No upstream means local-only; proceed. With an upstream, take the
remote name from `git config branch.<branch>.remote` and the remote
branch from `git config branch.<branch>.merge` (it can differ from the
local name and need not be `origin`). Read the remote's true tip
**without** `git fetch`:

```console
$ git ls-remote --heads <remote> <remote-branch>
```

`fetch` refreshes the remote-tracking ref and destroys the
`--force-with-lease` protection you are about to rely on.

Then decide whether rewriting drops commits that exist only on the
remote:

```console
$ git merge-base --is-ancestor <remote-tip> HEAD
```

A non-zero exit means someone else pushed, or the remote tip is not
local yet. Halt. Report the SHA from `ls-remote`. To name who pushed,
fetch by URL into a scratch ref; a fetch by remote name also refreshes
the remote-tracking ref and defeats the lease:

```console
$ git fetch \
    "$(git remote get-url <remote>)" \
    <remote-branch>:refs/remote-check/<remote-branch>
```

```console
$ git log --format='%h %an %s' HEAD..refs/remote-check/<remote-branch>
```

## Back up before touching anything

A reflog entry is not a backup: unreachable entries expire after 30
days. Use a branch, not a tag or raw ref; only a branch is discoverable
and has a reflog of its own.

```console
$ git branch "backup/<flat>-$(date -u +%Y%m%dT%H%M%SZ)" <branch>
```

Keep the name a single flat segment after `backup/`: git refuses a
branch whose name is a path prefix of an existing one, so `backup/x` and
`backup/x/<timestamp>` cannot coexist. `<flat>` below is the branch name
with every `/` replaced by `-`.

Do not rely on `ORIG_HEAD`; the next reset, merge, or pull overwrites it.

Report the backup branch name in the final output.

## Recovery

Undo a rewrite of the checked-out branch from its backup:

```console
$ git reset --hard backup/<flat>-<ts>
```

Restore a branch that is not checked out:

```console
$ git branch --force <branch> <backup-sha>
```

Never delete and recreate a branch to move it — that destroys its
reflog.

When no ref or reflog points at the work any more:

```console
$ git fsck --unreachable --no-reflogs
```

Never run `git reflog expire --expire-unreachable=now --all` as
cleanup. It destroys the user's entire stash list.

## Pushing the result

Pushing is always an explicit, separate decision. The recommit itself
stops at the local branch.

```console
$ git push --force-with-lease --force-if-includes origin <branch>
```

Bare `--force-with-lease` compares against your remote-tracking ref, so
any `git fetch` between the rewrite and the push (an editor, a background
job, another agent) makes the lease pass and destroys a colleague's
commit. `--force-if-includes` additionally requires the remote tip to
have been integrated locally; it is a no-op unless paired with *bare*
`--force-with-lease`.

The alternative, immune to background fetches, is to capture the lease
SHA before rewriting:

```console
$ git push --force-with-lease=<branch>:<captured-sha> origin <branch>
```

Never bare `--force`: it disables the fast-forward check on every ref
pushed, which can overwrite refs nobody intended to touch.
