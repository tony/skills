# Redundancy proofs

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
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.add(os.path.relpath(full, root))
    return out

def total(root, paths):
    return sum(os.path.getsize(os.path.join(root, p)) for p in paths)

candidate, keeper = sys.argv[1], sys.argv[2]
c, k = relpaths(candidate), relpaths(keeper)
only_c, shared = c - k, c & k
print(f"candidate files : {len(c)}")
print(f"shared with keeper: {len(shared)} ({total(candidate, shared) / 2**30:.2f} GiB)")
print(f"UNIQUE to candidate: {len(only_c)} ({total(candidate, only_c) / 2**30:.2f} GiB)")
print("REDUNDANT" if not only_c else "NOT REDUNDANT - candidate holds unique data")
```

Shared paths must then be confirmed identical by content, not by size
or mtime. Size collisions are common in append-structured formats such
as JSONL transcripts.

```
rsync -rcn --itemize-changes <candidate>/ <keeper>/
```

The `-c` flag forces a checksum comparison. Any output line means the
two trees disagree on a shared path; silence means they match.

## Required proof for "mergeable"

A candidate is mergeable into a keeper when it holds unique files and
no shared path differs in content. The merge is then additive — no
existing file is written.

```
rsync -a --ignore-existing <candidate>/ <keeper>/
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
