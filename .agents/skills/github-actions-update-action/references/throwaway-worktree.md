# Working in a throwaway worktree

Use one when the repository is checked out on a feature branch or has
uncommitted work, so the commits start from the remote default branch.
The local default branch may be stale, and a push from it is rejected as
a non-fast-forward.

Refuse when `git rev-parse --show-toplevel` prints `$HOME` or a
directory containing it: a dotfile repository rooted at home would pull
the whole home directory into the worktree.

Fetch, then create the directory. The command prints its path; use that
literal path in every later command, because shell state does not
persist between calls:

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
    origin/<default>
```

Commit there. Push only when the request asks to push, and only to the
target the calling skill names. A skill that lands commits on the default
branch directly pushes `HEAD:<default>`; a skill that opens a pull request
pushes its own branch:

```console
$ git push \
    --set-upstream \
    origin <branch>
```

Remove the worktree afterwards; the branch and its commits stay:

```console
$ git worktree remove <printed-path>
```

Without a push request, report the branch name and print the push
command for the user to run, using the same target (`<target>` is `<default>` or `<branch>`):

```console
$ git push origin <branch>:<target>
```
