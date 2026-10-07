# Splitting a collapsed branch into atomic commits

Resolve the base, collapse the branch into the index, then carve the
index up one logical change at a time. The working tree stays pinned at
the branch's final content, so intermediate commits are checked only
after the series is committed, with the toolkit's `verify`.

## Contents

- Resolve the base first, once, to a SHA
- Refuse before collapsing
- Collapse
- Commit whole files
- Split one file across several commits
- Preserve authorship
- Prove the recommit changed nothing

## Resolve the base first, once, to a SHA

A remote-tracking base such as `origin/main` is the last-fetched copy
and may be stale; this workflow never fetches, so say in the plan when
the base is one.

Two-dot `git diff <base-branch>..HEAD` against a *moving ref* invents
deletions of files the base branch added after the fork. Resolve the
base to a full 40-character SHA once, then use that SHA. Expand an
abbreviation with `git rev-parse --verify "<abbrev>^{commit}"`; the
per-commit gate compares against it.

Find the base ref. Trunk is the remote's default branch:

```console
$ git symbolic-ref --short refs/remotes/origin/HEAD
```

When `origin/HEAD` is unset it fails; fall back to whichever of
`origin/main` or `origin/master` exists. A branch with a pull request names
its own base, which is the parent on a stacked branch:

```console
$ gh pr view --json baseRefName
```

Without `gh` or a pull request, ask the user for the parent.

Refuse to continue unless exactly one merge base exists; with two,
`git merge-base` picks one without warning.

```console
$ git merge-base --all <base-ref> HEAD | wc -l
```

Prefer the fork point, which consults the base ref's reflog and
survives a force-updated base branch:

```console
$ git merge-base --fork-point <base-ref> HEAD
```

It prints nothing and exits 1 when the reflog is empty (a fresh clone or
CI). Treat empty output as "no answer" and fall back to plain
`git merge-base`; never pass an empty string to `git reset --soft`.

**On a stacked branch the base is the parent branch tip, never
trunk.** Recutting a child against trunk absorbs the parent pull
request. Recommit a stack bottom-up, and re-derive each child's base after
its parent is rebuilt.

## Refuse before collapsing

- Merge commits in the range. `git rev-list --merges <base>..HEAD`
  must be empty. Collapsing across a merge silently produces a
  single-parent commit: work reachable only through the second parent
  is erased from history while its content survives, so every content
  check still passes.
- A dirty tree, or any operation in progress.
- `git reset --soft` is fatal mid-merge; check for `MERGE_HEAD`.

## Collapse

```console
$ git reset --soft <base-sha>
```

HEAD and the branch ref move to the base; the index and working tree
are untouched (assert with `git write-tree` before and after). Use
`--soft`, never `--mixed`: mixed drops gitignored-but-force-added files
from the index, after which `git add` on them fails without `-f`.

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
index. That is safe for whole files and unsafe for a file being
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
*current* index every round — replaying pre-generated patches lets
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
`w[1]=1` keeps hunk 1; list more hunks with `w[2]=1` and so on:

```console
$ git diff --binary -- path/to/file > <scratch>/round.patch
```

```console
$ awk 'BEGIN{w[1]=1} /^@@/{n++;k=(n in w);if(k)print;next} n==0{print;next} k' \
    <scratch>/round.patch > <scratch>/part.patch
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
`git apply --cached` commits the *entire* index:

```console
$ git diff --cached --name-only
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

Harvest the identities before collapsing:

```console
$ git log --no-merges --format='%H %an <%ae> %aI' <base>..HEAD
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
