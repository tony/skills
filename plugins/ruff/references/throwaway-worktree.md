<!-- Vendored from shared/throwaway-worktree.md; edit that file, then run 'scripts/marketplace.py portable'. -->
# Working in a throwaway worktree

The calling skill says when to use one. The usual reasons: the checkout
is on a feature branch, has uncommitted work, or holds a local default
branch that differs from the remote's, and the commits must start from a
known base. The local default branch may be stale, and a push from it is
rejected as a non-fast-forward.

`<base>` below is the commit the calling skill names; without one it is
`<remote>/<default>`.

`<repo>` below is the repository's top-level directory
(`git rev-parse --show-toplevel`). Every git command names its repository
with `git -C`, so none depends on the shell's directory.

`<remote>` below is the remote the default branch tracks: `origin` when it
exists, the only remote when there is one, otherwise ask (`git remote -v`
lists them).

Refuse when `git rev-parse --show-toplevel` prints the home directory or
a directory containing it: a dotfile repository rooted at home would pull
the whole home directory into the worktree. Compare against `(cd ~ && pwd -P)`,
not `$HOME`: the toplevel is a physical path, and home may be a symlink.

Fetch the default branch first:

```console
$ git -C <repo> fetch <remote> <default>
```

Then create the directory. The command prints its path; use that literal
path in every later command, because shell state does not persist between
calls:

```console
$ mktemp -d "${TMPDIR:-/tmp}/worktree.XXXXXX"
```

A worktree may start detached while the phases are read-only
(`git -C <repo> worktree add --detach <printed-path> <base>`).
Before its first commit it switches to a named local branch
(`git -C <printed-path> switch -c <branch>`): commits on a detached HEAD
are unreachable once the worktree is removed, so none lands there. Use the
branch name the skill gives, or `wip/<topic>`. If the branch already
exists, `switch` to a name the user passed and suffix a generated one
(`wip/<topic>-2`); never reset an existing branch, and pick another name
when another worktree has it checked out.

A skill that commits straight away creates the branch with the worktree:

```console
$ git -C <repo> worktree add \
    -b <branch> \
    <printed-path> \
    <base>
```

Commit with `git -C <printed-path>`. Run the project's required checks in
the worktree before any push; a failure caused by the change publishes
nothing. Push only when the request asks to push, and only to the target
the calling skill names. A skill that lands commits on the default branch
directly pushes `HEAD` to it:

```console
$ git -C <printed-path> push <remote> HEAD:<default>
```

A skill that opens a pull request pushes its own branch:

```console
$ git -C <printed-path> push \
    --set-upstream \
    <remote> <branch>
```

Remove the worktree after the checks and any push; the branch and its
commits stay:

```console
$ git -C <repo> worktree remove <printed-path>
```

Without a push request, report the branch name and print the push
command for the user to run, using the same target (`<target>` is
`<default>` or `<branch>`):

```console
$ git -C <repo> push <remote> <branch>:<target>
```
