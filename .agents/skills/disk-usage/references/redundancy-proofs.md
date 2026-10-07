# Redundancy proofs

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

Reading case 2 as case 1 deletes the only copy. **Never classify on a
`differ` count without also establishing the size of the intersection.**

## Required proof for "redundant"

Compare path sets directly and report the intersection, both
differences, and the byte size of each. A directory is redundant only
when the set unique to it is empty and every entry in both trees was
readable. Run the script, resolved relative to this file:

```console
$ python3 references/redundancy.py \
    <candidate> \
    <keeper>
```

Exit status 0 is REDUNDANT, 1 is NOT REDUNDANT, 2 is INCONCLUSIVE. An
unreadable directory or file in either tree makes the result
INCONCLUSIVE and lists the entries; a subtree that cannot be listed
cannot be proved empty. Report an INCONCLUSIVE proof as failed and
classify the candidate as unique until access is fixed.

Symlinks (including broken ones) count as entries sized by `lstat`.
Empty directories are not compared; the script counts them, and the
report names them as skipped.

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

An empty rsync output plus a REDUNDANT result from the script
proves redundancy. Either one alone does not.

## Required proof for "mergeable"

A candidate is mergeable into a keeper when it holds unique files and
no shared path differs in content. The merge is then additive — no
existing file is written.

Never write into an agent history store with `rsync`: the owning tool
indexes sessions in a state database and does not see files it did not
write. Merge history only through the tool's own import path. For any
other tree, an additive merge is:

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
