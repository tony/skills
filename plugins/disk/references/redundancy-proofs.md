# Redundancy proofs

## Contents

- The vacuous-truth trap
- Required proof for "redundant"
- Required proof for "mergeable"
- Classification outcomes
- Naming is not evidence

A directory may only be classified redundant when a command has *proved*
it. This file defines what counts as proof, and the near-misses that
have masqueraded as proof.

## The vacuous-truth trap

`diff -rq A B` reports two kinds of finding:

- `Only in <dir>: <name>` — an entry present on one side. When the
  missing entry is a **directory**, `diff` prints one line and does not
  recurse into it.
- `Files A/f and B/f differ` — a path present on **both** sides whose
  contents differ.

A run that reports zero `differ` lines therefore has two possible
meanings, and they point in opposite directions:

1. Every shared path is byte-identical. A is redundant with B.
2. There are no shared paths at all. A and B are disjoint, and A is
   entirely unique.

Reading case 2 as case 1 concludes "safe to delete" about a directory
that is the only copy of its contents. The `differ` count alone cannot
distinguish them. **Never classify on a `differ` count without also
establishing the size of the intersection.**

## Required proof for "redundant"

Compare path sets directly and report the intersection, both
differences, and the byte size of each. A directory is redundant only
when the set unique to it is empty.

```python
import os, sys

def relpaths(root):
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]:
            out.add(os.path.relpath(os.path.join(dirpath, name), root))
    return out

def total(root, paths):
    return sum(os.lstat(os.path.join(root, p)).st_size for p in paths)

candidate, keeper = sys.argv[1], sys.argv[2]
c, k = relpaths(candidate), relpaths(keeper)
only_c, shared = c - k, c & k
print(f"candidate files : {len(c)}")
print(f"shared with keeper: {len(shared)} ({total(candidate, shared) / 2**30:.2f} GiB)")
print(f"UNIQUE to candidate: {len(only_c)} ({total(candidate, only_c) / 2**30:.2f} GiB)")
print("REDUNDANT" if not only_c else "NOT REDUNDANT - candidate holds unique data")
```

Symlinks (including broken ones) count as entries sized by `lstat`.
Empty directories are not compared: list them with `find <candidate> -type d -empty`
and report them as skipped.

Shared paths must then be confirmed identical by content, not by size
or mtime. Size collisions are common in append-structured formats such
as JSONL transcripts.

```console
$ rsync -rcn --itemize-changes <candidate>/ <keeper>/
```

The `-c` flag forces a checksum comparison. Output lines show how the
trees differ, not only whether they do:

- `>f+++++++++ <path>`: the candidate holds a file the keeper lacks.
- `>fcsT...... <path>`: a shared path differs in content.
- No lines: nothing in the candidate is missing from or different in the
  keeper.
- `skipping non-regular file "<name>"`: a symlink was not compared.
  Report it as skipped.

An empty rsync output plus an empty unique set from the script above
proves redundancy. Either one alone does not.

## Required proof for "mergeable"

A candidate is mergeable into a keeper when it holds unique files and
no shared path differs in content. The merge is then additive — no
existing file is written.

Never write into an agent history store with `rsync`: the owning tool
indexes sessions in a state database and does not see files it did not
write (see `agent-history.md`). Merge history only through the tool's
own import path, or after confirming its discovery glob and state
database. For any other tree, an additive merge is:

```console
$ rsync -a --ignore-existing <candidate>/ <keeper>/
```

Re-run the path-set comparison afterward with the arguments reversed.
The set unique to the candidate must now be empty, which is what makes
the candidate safe to remove.

## Classification outcomes

**Redundant** — zero unique files, all shared paths checksum-identical.
Deletable once the keeper is confirmed readable by its owning tool.

**Mergeable** — holds unique files, zero content conflicts on shared
paths. Merge additively, verify, then delete the source.

**Conflicted** — holds unique files *and* shared paths whose contents
differ. Never resolve this automatically. Report both sides and stop;
a differing transcript usually means two divergent forks of one
session, and picking a winner is the user's call.

**Unique** — no overlap with any keeper. Not a backup at all, despite
its name. Treat as primary data.

## Naming is not evidence

A directory called `*-backup-*`, `*.old`, `*.bak`, or `archive-*`
carries no information about redundancy. Backups are routinely taken,
then diverge as the live tree is rotated, pruned, or re-slugged — after
which the "backup" is the only copy of everything the live tree
dropped. Run the proof.
