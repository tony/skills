# Not losing the user's work

A recommit rewrites history that may be published and may be the only
copy of a day's work. Each gate prevents a silent loss. The deterministic
checks live in `<gate>`, the absolute path to `../scripts/branch_gate.py`
that each skill resolves from its own directory; a shell runs in the
project's working directory, so write that path literally in every command.

## Contents

- Run the gates
- The pushed-branch gate
- Back up before touching anything
- Recovery
- The plan and its approval
- Pushing the result

## Run the gates

Run the gates before reading any pull request, ticket, or transcript.
Resolve a PR number to its head branch with
`gh pr view <number> --json headRefName`; never `gh pr checkout`, which
changes the working tree.

```console
$ python3 <gate> preflight <branch>
```

Add `--parent <ref>` on a stacked branch and `--mode redo` for a redo.
Each `refuse <code>: <reason>` line halts the run with a report, not a
warning; every `note <code>: <reason>` line is reported without halting.
Exit 2 means at least one refusal.

Refusals, by code:

- `home`: the repository is rooted at the physical home directory or at a
  directory containing it. A dotfile repo there makes every untracked
  file, credentials included, part of the work. The report says
  "credential files" and names none of them.
- `unborn`: HEAD has no commit, so there is nothing to rewrite or study.
- `shallow`: a shallow clone cannot be reasoned about historically.
- `branch-not-local` (redo only): the branch, for instance a fork's pull
  request head, has no local ref. Ask the user to fetch it; fetch nothing
  yourself.
- `not-checked-out`: HEAD is detached or on another branch. Advise
  checking the target branch out first; a PR number resolves to a head
  branch that is not necessarily checked out, and a soft reset would land
  on whatever is.
- `dirty`: uncommitted changes, untracked files included. The toolkit
  script's own preflight ignores untracked files, so this is the stricter
  check, and `rebase.autoStash=true` would otherwise stash and proceed.
- `in-progress`: a rebase, merge, cherry-pick, revert, bisect, or
  sequencer is under way. HEAD is not the test; the script probes the git
  dir.
- `worktree`: another worktree holds the branch, so it cannot be rewritten
  in place.
- `base`: no trunk, no single merge base, or an unresolvable parent
  (`split-mechanics.md`, "Resolve the base first").
- `empty-range`: nothing lies beyond the base.
- `merge-commit`: collapsing across a merge erases another author's
  commits while keeping their content, so every content check still passes.
  Advise asking the merge's author how to handle it, then running again once
  the range has no merge commit; never advise resetting the branch to drop
  the merge.

A redo refuses only `home`, `unborn`, `shallow`, and `branch-not-local`;
it never rewrites the branch, so `dirty` is a note there.

Notes: `signed` (a rebase strips signatures unless signing is
re-enabled, `RECUT_SIGN` in `rebase-toolkit.md`), `sparse` (file listings
are incomplete), `submodule` (a later blanket add would bake in the stale
pointer).

Halt advice names only steps that destroy nothing. Never advise
`git reset --hard`, `git clean`, `git checkout -- <path>`, a force-push,
or `git stash drop` in a refusal; if the only fix is destructive, make the
backup branch below first and name it in the advice.

## The pushed-branch gate

Rewriting a branch someone else may have checked out needs the user's
explicit consent. Read the remote's true tip without `git fetch`:

```console
$ python3 <gate> remote-tip <branch>
```

The subcommand takes the remote and remote branch from
`branch.<branch>.remote` and `branch.<branch>.merge`. With no upstream it
falls back to the sole remote, or `origin`, and the branch's own name, so a
branch pushed without `-u` still shows as pushed. It reads the tip with
[`git ls-remote`](https://git-scm.com/docs/git-ls-remote), which does not
touch the remote-tracking ref, then checks with `git merge-base
--is-ancestor` that the local branch contains it. It prints `remote=`,
`remote-branch=`, `tip=`, `pushed=yes|no`, and, when pushed, the `push=`
command for the end of the run.

`pushed=no` means the remote does not hold the branch (or there is no
remote): proceed. `pushed=yes` needs the user's explicit consent. A
`refuse remote-ahead` line means someone else pushed, or the remote tip is
not local yet: halt and report the SHA. A `refuse remote-unreachable`
line means the remote tip is unknown: halt.

`git fetch` by remote name refreshes the remote-tracking ref, which makes
a bare `--force-with-lease` pass. To name who pushed, fetch by URL into a
scratch ref. The scratch ref is the one change a refused run leaves behind:
the halt names it and gives the cleanup,
`git update-ref -d refs/remote-check/<remote-branch>`, and does not
describe the fetch:

```console
$ git fetch \
    "$(git remote get-url <remote>)" \
    <remote-branch>:refs/remote-check/<remote-branch>
```

```console
$ git log --format='%h %an %s' HEAD..refs/remote-check/<remote-branch>
```

## Back up before touching anything

A reflog entry is not a backup: unreachable entries expire after 30 days
by default (`gc.reflogExpireUnreachable` in
[git-config](https://git-scm.com/docs/git-config)). Use a branch, not a tag
or raw ref; only a branch is discoverable and has a reflog of its own.
Record the tip first, then let the script create the branch from that SHA,
read it back, and print its name:

```console
$ git rev-parse --verify <branch>
```

```console
$ python3 <gate> backup <branch> <tip-sha>
```

The name is `backup/<flat>-<UTC timestamp>`, where `<flat>` is the branch
name with every `/` replaced by `-`. Git refuses a branch whose name is a
path prefix of an existing one, so `backup/x` and `backup/x/<timestamp>`
cannot coexist; the flat segment avoids that. The script refuses when
`<tip-sha>` is not the branch's current tip.

Do not rely on `ORIG_HEAD`; the next reset, merge, or pull overwrites it.

Report the backup branch name in the final output.

## Recovery

Undo a rewrite of the checked-out branch from its backup
([git-reset](https://git-scm.com/docs/git-reset)):

```console
$ git reset --hard backup/<flat>-<ts>
```

Restore a branch that is not checked out:

```console
$ git branch --force <branch> <backup-sha>
```

Never delete and recreate a branch to move it: that destroys its reflog.

When no ref or reflog points at the work any more:

```console
$ git fsck --unreachable --no-reflogs
```

Never run `git reflog expire --expire-unreachable=now --all` as cleanup.
It destroys the user's entire stash list.

## The plan and its approval

The plan is at most about eight bullets, one line each, and narrates no
gate that passed. An explicit instruction to proceed ("go ahead", "without
waiting") is the approval; with no such instruction and no question tool,
stop after the plan. The approval covers the rewrite, never a push.

## Pushing the result

Pushing is always an explicit, separate decision. The recommit itself
stops at the local branch. Offer the `push=` line that `remote-tip`
printed:

```console
$ git push \
    --force-with-lease=<remote-branch>:<remote-tip-sha> \
    <remote> \
    <branch>:<remote-branch>
```

The explicit `<remote-branch>:<remote-tip-sha>` form compares against the
SHA read from the remote itself, so a `git fetch` between the rewrite and
the push (an editor, a background job, another agent) cannot make the
lease pass ([git-push](https://git-scm.com/docs/git-push), `--force-with-lease`).
Bare `--force-with-lease` compares against the remote-tracking ref and
loses that protection, so never `git fetch` by remote name between the
`remote-tip` read and the push.

Leave `--force-if-includes` off: git-push documents it as a no-op when
combined with `--force-with-lease=<refname>:<expect>`.

With `pushed=no` there is nothing to lease against and no force is needed;
say so instead of offering a force-push.

Never bare `--force`: it disables the fast-forward check on every ref
pushed, which can overwrite refs nobody intended to touch.
