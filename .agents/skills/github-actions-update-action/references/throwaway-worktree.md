# Working in a throwaway worktree

The calling skill says when to use one. The usual reason: the checkout
is on a feature branch or has uncommitted work, and the commits must start
from the remote default branch. The local default branch may be stale, and
a push from it is rejected as a non-fast-forward.

`<remote>` below is the remote the default branch tracks: `origin` when it
exists, the only remote when there is one, otherwise ask (`git remote -v`
lists them).

Refuse when `git rev-parse --show-toplevel` prints the home directory or
a directory containing it: a dotfile repository rooted at home would pull
the whole home directory into the worktree. Compare against `cd ~ && pwd -P`,
not `$HOME`: the toplevel is a physical path, and home may be a symlink.

Fetch the default branch first:

```console
$ git fetch <remote> <default>
```

Then create the directory. The command prints its path; use that literal
path in every later command, because shell state does not persist between
calls:

```console
$ mktemp -d "${TMPDIR:-/tmp}/worktree.XXXXXX"
```

Create the worktree on a named local branch, never detached: commits on a
detached HEAD are unreachable once the worktree is removed. Use the branch
name the skill gives, or `wip/<topic>`. If the branch already exists,
pick another name; never reset an existing one.

```console
$ git worktree add \
    -b <branch> \
    <printed-path> \
    <remote>/<default>
```

Commit there. Push only when the request asks to push, and only to the
target the calling skill names. A skill that lands commits on the default
branch directly pushes `HEAD` to it:

```console
$ git push <remote> HEAD:<default>
```

A skill that opens a pull request pushes its own branch:

```console
$ git push \
    --set-upstream \
    <remote> <branch>
```

Remove the worktree afterwards; the branch and its commits stay:

```console
$ git worktree remove <printed-path>
```

Without a push request, report the branch name and print the push
command for the user to run, using the same target (`<target>` is
`<default>` or `<branch>`):

```console
$ git push <remote> <branch>:<target>
```
