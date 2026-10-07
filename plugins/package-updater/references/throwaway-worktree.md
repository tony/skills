<!-- Vendored from shared/throwaway-worktree.md; edit that file, then run 'scripts/marketplace.py portable'. -->
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

Commit there. Push with `git push origin HEAD:<default>` only when the
request asks to push. Remove the worktree afterwards; the branch and its
commits stay:

```console
$ git worktree remove <printed-path>
```

Without a push request, report the branch name and print the push
command for the user to run:

```console
$ git push origin <branch>:<default>
```
