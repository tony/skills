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

Two-dot `git diff <base-branch>..HEAD` against a *moving ref* invents
deletions of files the base branch added after the fork. Resolve the
base to a SHA once, then use that SHA.

Refuse to continue unless exactly one merge base exists; with two,
`git merge-base` picks one without warning.

```
git merge-base --all <base-ref> HEAD | wc -l
```

Prefer the fork point, which consults the base ref's reflog and
survives a force-updated base branch:

```
git merge-base --fork-point <base-ref> HEAD
```

It prints nothing and exits 1 when the reflog is empty (a fresh clone or
CI). Treat empty output as "no answer" and fall back to plain
`git merge-base`; never pass an empty string to `git reset --soft`.

**On a stacked branch the base is the parent branch tip, never
trunk.** Recutting a child against trunk absorbs the parent pull
request. Recommit stacks bottom-up and re-derive each child's base
afterward.

## Refuse before collapsing

- Merge commits in the range. `git rev-list --merges <base>..HEAD`
  must be empty. Collapsing across a merge silently produces a
  single-parent commit: work reachable only through the second parent
  is erased from history while its content survives, so every content
  check still passes.
- A dirty tree, or any operation in progress.
- `git reset --soft` is fatal mid-merge; check for `MERGE_HEAD`.

## Collapse

```
git reset --soft <base-sha>
```

HEAD and the branch ref move to the base; the index and working tree
are untouched (assert with `git write-tree` before and after). Use
`--soft`, never `--mixed`: mixed drops gitignored-but-force-added files
from the index, after which `git add` on them fails without `-f`.

Take the inventory of what is now staged:

```
git diff --cached --name-status -M -z
```

```
git diff --cached --summary
```

`--stat` renders a pure mode change or rename as a bare `| 0`.

## Commit whole files

When a logical change is entirely whole files, commit them directly
and leave everything else staged:

```
git commit -m "subject" --only -- path/one path/two
```

**Message flags must come before the `--`.** Everything after `--` is
a pathspec, so `git commit --only -- file.txt -m "msg"` makes git
look for files named `-m` and `msg`.

`--only` records the *working tree* content of those paths, not the
index. That is safe right after a soft reset and unsafe for a file being
split, where the index differs from the working tree.

A rename is a delete plus an add in the index. If you unstaged one side,
name both sides or you get a half-rename:

```
git add -- old-name new-name
```

## Split one file across several commits

Unstage the file once, then loop. Regenerate the patch from the
*current* index every round — replaying pre-generated patches lets
context drift.

```
git restore --staged -- path/to/file
```

For a file the branch *added*, unstaging makes it untracked and
`git diff` then shows nothing. Restore its visibility first:

```
git add -N -- path/to/file
```

Each round, generate, filter, apply to the index only, and commit:

```
git diff --binary -- path/to/file > /tmp/round.patch
```

```
awk 'BEGIN{w[1]=1} /^@@/{n++;k=(n in w);if(k)print;next} n==0{print;next} k' /tmp/round.patch > /tmp/part.patch
```

```
git apply --cached --recount --whitespace=nowarn /tmp/part.patch
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

```
git diff --cached --name-only
```

## Preserve authorship

The committer is whoever runs the recommit; do not fake it. Preserve the
author:

```
GIT_AUTHOR_NAME="$AN" GIT_AUTHOR_EMAIL="$AE" GIT_AUTHOR_DATE="$AD" git commit -F /tmp/msg.txt
```

Prefer the environment variables over `--author`: a value without angle
brackets is silently treated as a search pattern over history, copies no
date, and is fatal when nothing matches.

Harvest the identities before collapsing:

```
git log --no-merges --format='%H %an <%ae> %aI' <base>..HEAD
```

## Prove the recommit changed nothing

Tree equality against the pre-recommit backup is the definitive check.
Exit 0 means the two trees are identical:

```
git diff --quiet <backup-branch> HEAD
```

`git range-diff` explains *how* the commits were regrouped, which an
endpoint diff cannot:

```
git range-diff <base-sha> <backup-branch> HEAD
```

Read it as an explanation, not a gate: heavy regrouping shows as
unrelated drop-and-add pairs.

Then check each commit with the toolkit's `verify`.
