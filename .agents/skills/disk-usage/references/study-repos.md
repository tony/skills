# Study repositories

## Contents

- Cost one: full history nobody reads
- Cost two: build artifacts
- What to report

A directory of upstream clones kept for reading (vendored source,
reference checkouts, dependency study trees) is usually among the
largest reclaimable areas on a developer machine. Clones are
re-fetchable from a remote, except any local work they hold; check for
that before converting or deleting one.

Two independent costs dominate, and they need separate treatment.

## Cost one: full history nobody reads

A clone kept for reading source carries the entire commit graph. On
large upstreams the `.git` directory dwarfs the working tree by an
order of magnitude. Converting to a shallow or blobless clone keeps the
readable checkout and discards history the user never opens.

Rank clones by the ratio of `.git` to working tree, not by absolute
size.

Report, for each clone: total size, `.git` size, whether it is shallow,
and the remote it came from.

```console
$ git -C <repo> rev-parse --is-shallow-repository
```

A repository reporting `false` with a large `.git` is a conversion
candidate. One reporting `true` is already minimal.

### Conversion choices

**Blobless** (`--filter=blob:none`) keeps the full commit graph and
fetches file contents on demand. `git log`, `git blame`, and checkout
of any revision keep working, at the cost of needing network access for
history-spanning operations. The right default for a repository under
active study.

**Shallow** (`--depth=1`) keeps only the tip. Smallest result, but
`git log` and `git blame` are gone. Appropriate for a repository kept
purely as a source-reading reference.

Converting in place is possible, but re-cloning is more predictable and
costs only bandwidth:

```console
$ git clone --filter=blob:none <remote> <destination>
```

Never convert a repository holding work that is not on a remote. Check
every candidate first.

```console
$ git -C <repo> status --porcelain --branch
```

Uncommitted changes, stashes, unpushed commits, or a branch with no
upstream all disqualify a repository from any destructive conversion.
Report it and move on.

```console
$ git -C <repo> stash list
```

```console
$ git -C <repo> log --branches --not --remotes --oneline
```

## Cost two: build artifacts

Compiled output under a study tree is a side effect of one exploratory
build; Rust `target/` directories are the usual worst offender.

Aggregate artifact directories across the whole study root before
proposing anything, so the total is one number. With GNU coreutils:

```console
$ find <study-root> \
    -maxdepth 3 \
    -type d \( -name target -o -name node_modules -o -name build \) \
    -prune \
    -print0 \
  | du -sch --files0-from=- \
  | tail -1
```

BSD/Darwin `du` has no `--files0-from`, so sum the per-directory sizes
instead. This reports GiB:

```console
$ find <study-root> \
    -maxdepth 3 \
    -type d \( -name target -o -name node_modules -o -name build \) \
    -prune \
    -print0 \
  | xargs -0 du -sk \
  | awk '{total += $1} END {printf "%.1f GiB\n", total / 1048576}'
```

Restrict the depth. An unbounded search descends into vendored
dependency trees and double-counts nested artifact directories.

## What to report

Call out three groups explicitly, largest first within each:

- **Huge clones** — the largest by total size, with the `.git` share
  shown so the user can see where the weight sits.
- **Unshallow clones** — those reporting `false` with a `.git`
  directory above the survey's size floor (about one percent of the filesystem's capacity), ranked by `.git` size. These are the
  conversion candidates.
- **Artifact directories** — build output, aggregated per language, as
  a single reclaimable figure.

A clone can appear in more than one group; say so, since the reclaim
actions differ.
