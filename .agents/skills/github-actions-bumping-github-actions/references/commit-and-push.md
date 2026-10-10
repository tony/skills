# Committing and publishing bumps

## Contents

- Edit exactly the approved lines
- Commit
- Reuse a branch
- Push
- Read back what was published

## Edit exactly the approved lines

Replace each pin line the inventory recorded, old text to new text, in the
checkout the commit is made in (its worktree path when it uses one). When
the old text is not found, the file changed after the inventory: stop for
that repository and inventory it again. Do not edit by line number.

## Commit

Stage the named workflow files with `git -C <path> add -- <files>`; never
`add -A`, `add .`, or `commit -a`. Then read what is staged:

```console
$ git -C <path> diff \
    --cached \
    -U0
```

Commit only when every changed line is a `uses` pin or its version comment
and each matches an approved plan entry. Anything else, such as a
concurrent edit, stops that repository: name the file and leave the work
in place.

Run hooks; never pass `--no-verify`. A hook that fails stops that
repository and its output is reported. After the commit, show the commit:

```console
$ git -C <path> show \
    --format=%h \
    -U0 \
    <sha>
```

It must show the approved lines and nothing else. A hook that rewrote
other content makes the commit unexpected: report it and do not push.

## Reuse a branch

A branch left by an earlier run is reused only when
`git -C <path> log <remote>/<default>..<branch> --format=%h%x20%s` lists
nothing but bump commits matching approved plan entries and no other
worktree has it checked out. Otherwise create a new name with a numeric
suffix. Never reset, rebase, or force an existing branch.

## Push

Push only with `--push` (or an explicit request to push), and only to the
target the calling skill names. Before pushing, list what the push would
publish:

```console
$ git -C <path> log \
    <remote>/<default>..HEAD \
    --format=%h%x20%s
```

Push only when every listed commit was made in this run (its SHA was
recorded) or, on resume, matches an approved plan entry and passes the
`show` check above. Any other commit is the user's: do not push, name it
and how the branch diverges, never advise a reset or drop of it, and print
the push command. Stop a fleet loop on a rate-limit error or a rejected
push and report which repositories remain. A rejected push is not retried
with force. A local default branch holding the user's commits has diverged
from the remote after a push from a worktree; report it as diverged, not
behind.

## Read back what was published

After a push, ask the remote for the target:

```console
$ git -C <path> ls-remote \
    <remote> \
    refs/heads/<target>
```

Report "pushed" only when it prints the SHA just pushed. A different or
empty answer is reported as unconfirmed, with the SHA the remote returned.
Without a push, report the local branch holding the commit and print its
push command.
