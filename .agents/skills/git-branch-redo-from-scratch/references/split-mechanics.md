# Splitting a collapsed branch into atomic commits

Resolve the base, collapse the branch into the index, then carve the
index up one logical change at a time. The working tree stays pinned at
the branch's final content, so intermediate commits are checked only
after the series is committed, with the toolkit's `verify`.

`<gate>` is `./branch_gate.py` and `<toolkit>` is
`./rebase-todo.sh`, each resolved to an absolute path by the
calling skill.

## Contents

- Resolve the base first, once, to a SHA
- Collapse
- Commit whole files
- Split one file across several commits
- Preserve authorship
- Prove the recommit changed nothing

## Resolve the base first, once, to a SHA

Two-dot `git diff <base-branch>..HEAD` against a *moving ref* invents
deletions of files the base branch added after the fork. Resolve the base
to a full 40-character SHA once, then use that SHA everywhere; the
per-commit gate compares against it:

```console
$ python3 <gate> base
```

The base is the merge base of the branch and its parent, never the
parent's tip: when the parent has advanced since the fork, a soft reset to
its tip would revert the parent's new commits in the staged diff.
[`git merge-base`](https://git-scm.com/docs/git-merge-base) prints the
fork commit, and with `--fork-point` it consults the base ref's reflog to
survive a force-updated base. `--fork-point` prints nothing and exits 1
when the reflog lacks the fork point (a fresh clone or CI). The subcommand
prefers the fork point, falls back to the plain merge base on that empty
answer, and refuses unless exactly one merge base exists, because
without `--all` git-merge-base prints only one of several.

With no `--parent`, the parent is trunk: the remote's default branch
(`origin/HEAD`), else `origin/main`, `origin/master`, `main`, `master`.
A branch with a pull request names its own parent, which on a stacked
branch is the branch below it:

```console
$ gh pr view --json baseRefName
```

Pass it as `--parent <ref>`. Without `gh` or a pull request, ask the user
for the parent. Recutting a child against trunk absorbs the parent pull
request, so recommit a stack bottom-up and re-derive each child's base
after its parent is rebuilt.

A remote-tracking parent such as `origin/main` is the last-fetched copy
and may be stale; the subcommand says so on stderr, and the plan repeats it.
This workflow never fetches. A redo off its branch passes
`--branch <branch>`.

## Collapse

The collapse is `git reset --soft <base-sha>`, which `backup
--soft-reset` runs after the backup is created and read back
(`branch-safety.md`). HEAD and the branch ref move to the base; the index
and working tree are untouched. Use `--soft`, never `--mixed`: mixed
resets the index to the base tree, so a gitignored-but-force-added file
the branch added is no longer tracked, and `git add` on it fails without
`-f` ([git-reset](https://git-scm.com/docs/git-reset)).

Take the inventory of what is now staged:

```console
$ git diff --cached --name-status -M -z
```

```console
$ git diff --cached --summary
```

`--stat` renders a pure mode change or rename as a bare `| 0`.

## Commit whole files

When a logical change is entirely whole files, commit them directly
and leave everything else staged. After a soft reset every path is
tracked, so `--only` works:

```console
$ git commit -F <scratch>/msg.txt --only -- path/one path/two
```

Write the message file with the host's file tool, never a shell
heredoc: a subject drawn from PR text can contain the delimiter line.

`--only` fails with `pathspec ... did not match any file(s) known to
git` on a path git does not track yet, as in a rebuild where the files
sit untracked. Stage those paths first, check the staged set, then
commit the index:

```console
$ git add -- path/one path/two
```

```console
$ git commit -F <scratch>/msg.txt
```

**Message flags must come before the `--`.** Everything after `--` is
a pathspec, so `git commit --only -- file.txt -F msg.txt` makes git
look for files named `-F` and `msg.txt`.

`--only` records the *working tree* content of those paths, not the
index ([git-commit](https://git-scm.com/docs/git-commit)). That is safe for whole files and unsafe for a file being
split, where the index differs from the working tree.

A rename is a delete plus an add in the index. If you unstaged one side,
stage back exactly that side or you get a half-rename. Naming a path
that is already gone from both index and working tree is fatal, so name
only the side you unstaged. The new side:

```console
$ git add -- new-name
```

The old side (a deletion):

```console
$ git add -u -- old-name
```

## Split one file across several commits

Unstage the file once, then loop. Regenerate the patch from the
*current* index every round; replaying pre-generated patches lets
context drift.

```console
$ git restore --staged -- path/to/file
```

For a file the branch *added*, unstaging makes it untracked and
`git diff` then shows nothing. Restore its visibility first:

```console
$ git add -N -- path/to/file
```

Make a scratch directory outside the repository once, and use the
path it prints in every later command (shell variables do not survive
between separate commands):

```console
$ mktemp -d "${TMPDIR:-/tmp}/split.XXXXXX"
```

Each round, generate, filter, apply to the index only, and commit.
`hunks` keeps the patch header and the listed hunks, numbered from 1:

```console
$ git diff --binary -- path/to/file > <scratch>/round.patch
```

```console
$ python3 <gate> hunks <scratch>/round.patch 1,3 > <scratch>/part.patch
```

```console
$ git apply --cached --recount --whitespace=nowarn <scratch>/part.patch
```

The last round needs no patch: `git add -- path/to/file` takes the
remainder.

Notes on the patch step:

- Editing *inside* a hunk body without fixing the header counts fails
  hard; `--recount` fixes it, `--3way` does not.
- `--cached` is required: `git apply --index` refuses whenever the index
  and working tree differ.
- Never pass `--whitespace=fix`; it rewrites content and breaks the
  content-identity guarantee.
- Binary paths need `git diff --binary`, or applying fails with
  `cannot apply binary patch ... without full index line`.
- Write patches outside the repository, where they would show up as
  untracked.

Assert the staged set before every commit: a bare `git commit` after
`git apply --cached` commits the *entire* index. `staged` lists each
unexpected or missing path and exits 2 unless the set is exactly the paths
named:

```console
$ python3 <gate> staged path/to/file
```

## Preserve authorship

The committer is whoever runs the recommit; do not fake it. Preserve the
author:

```console
$ GIT_AUTHOR_NAME='Ada Lovelace' \
  GIT_AUTHOR_EMAIL='ada@example.com' \
  GIT_AUTHOR_DATE='2026-10-01T09:30:00+00:00' \
  git commit -F <scratch>/msg.txt
```

Substitute the harvested author, email, and date as literals; write the
message file into the same scratch directory.

Prefer the environment variables over `--author`: a value without angle
brackets is silently treated as a search pattern over history, copies no
date, and is fatal when nothing matches.

Harvest the identities from the backup, which keeps the original series:

```console
$ git log --no-merges --format='%H %an <%ae> %aI' <base-sha>..backup/<flat>-<ts>
```

After the rebuild, `series` prints each commit as `hash author <email>
date subject` for the report, and with `--authors-of` exits 2 when a
commit carries an author or date the original series lacked, or an
original author is missing from both the authors and the messages'
`Co-authored-by` trailers:

```console
$ python3 <gate> series <base-sha> HEAD --authors-of backup/<flat>-<ts>
```

## Prove the recommit changed nothing

Tree equality against the pre-recommit backup is the definitive check.
Exit 0 means the two trees are identical:

```console
$ git diff --quiet <backup-branch> HEAD
```

`git range-diff` explains *how* the commits were regrouped, which an
endpoint diff cannot:

```console
$ git range-diff <base-sha> <backup-branch> HEAD
```

Read it as an explanation, not a gate: heavy regrouping shows as
unrelated drop-and-add pairs.

Then check each commit with the toolkit's `verify`.
