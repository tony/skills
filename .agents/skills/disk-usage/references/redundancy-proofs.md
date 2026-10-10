# Redundancy proofs

Script paths here (`../scripts/...`) resolve from this file's directory; print
the absolute path once and write it literally in each command.

## Contents

- The vacuous-truth trap
- Required proof for "redundant"
- Required proof for "mergeable"
- Classification outcomes

A directory may only be classified redundant when a command has *proved*
it. A name such as `*-backup-*` or `*.old` is not proof.

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

Reading case 2 as case 1 can delete data without a proved replacement. **Never classify on a
`differ` count without also establishing the size of the intersection.**

## Required proof for "redundant"

Compare path sets, then the content of every shared path, and report
the intersection, both differences, and the byte size of each. A
directory is redundant only when the set unique to it is empty, every
shared file has the same SHA-256 in both trees, and every entry was
readable. Run the script:

```console
$ python3 /abs/path/to/scripts/redundancy.py \
    <candidate> \
    <keeper>
```

Exit status 0 is REDUNDANT, 1 is NOT REDUNDANT, 2 is INCONCLUSIVE. The
script never prints REDUNDANT on path sets alone: size and mtime are not
compared, because size collisions are common in append-structured
formats such as JSONL transcripts. NOT REDUNDANT lists the shared paths
whose content differs; unique paths are counted separately. A directory
that cannot be listed, or a regular file that cannot be opened, in either tree
makes the result INCONCLUSIVE and lists the entries; what cannot be read
cannot be proved duplicated. Report an INCONCLUSIVE proof as failed and
classify the candidate as unique until access is fixed.

Symlinks (including broken ones) count as entries compared by target.
Empty directories are not compared; the script counts them, and the
report names them as skipped.

## Required proof for "mergeable"

A candidate is mergeable into a keeper when it holds unique files and
no shared path differs in content. The merge is then additive; no
existing file is written.

Merge agent history only through the owning tool's verified import path,
after its discovery and indexing behavior is established. For any other tree, an additive merge is:

```console
$ rsync -a --ignore-existing <candidate>/ <keeper>/
```

Re-run the proof afterward with the source as candidate and the
destination as keeper. The source must have no unique entries or
content differences before it can be removed.

## Classification outcomes

**Redundant** — zero unique files, all shared paths checksum-identical.
Deletable once the keeper is confirmed readable by its owning tool.

**Mergeable** — holds unique files, zero content conflicts on shared
paths. Merge additively, verify, then delete the source.

**Conflicted** — holds unique files *and* shared paths whose contents
differ. Never resolve this automatically. Report both sides and stop;
a differing transcript usually means two divergent forks of one
session, and picking a winner is the user's call.

**Unique** — no overlap with the compared keeper. Treat as primary
data unless another keeper proves redundancy.
