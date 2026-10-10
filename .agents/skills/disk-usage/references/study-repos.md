# Study repositories

## Contents

- Cost one: full history
- Cost two: build artifacts
- What to report

A directory of upstream clones kept for reading may contain both
re-fetchable content and local work. Verify the remote still supplies
the required revisions and check local work before proposing conversion.

Two independent costs dominate, and they need separate treatment.

## Cost one: full history

A full clone carries history as well as its checkout. Measure both
before proposing a shallow or blobless replacement, and ask which
history operations the user needs.

Rank clones by the ratio of `.git` to working tree, not by absolute
size.

Report, for each clone: total size, `.git` size, whether it is shallow,
and the remote it came from.

```console
$ git -C <repo> rev-parse --is-shallow-repository
```

A repository reporting `false` with a large `.git` is a conversion
candidate. `true` reports shallow history, not minimal disk usage.

### Conversion choices

**Blobless** (`--filter=blob:none`) keeps the full commit graph and
fetches file contents on demand. `git log`, `git blame`, and checkout
of any revision keep working, at the cost of needing network access for
history-spanning operations. The right default for a repository under
active study.

**Shallow** (`--depth=1`) limits history to the tip. History-spanning
`git log` and `git blame` stop at that boundary. Appropriate for a
repository kept purely as a source-reading reference.

Clone into a separate destination so the original stays available during
verification. This costs time, bandwidth, and temporary disk space:

```console
$ git clone --filter=blob:none <remote> <destination>
```

Never convert a repository holding work that is not on a remote. Check
every candidate first.

```console
$ git -C <repo> status --porcelain --branch --untracked-files=all --ignored
```

Uncommitted, untracked, or ignored files, stashes, unpushed commits, or a
branch with no upstream disqualify a repository from destructive conversion.
Report it and move on.

```console
$ git -C <repo> stash list
```

```console
$ git -C <repo> log --all --not --remotes --oneline
```

Remote-tracking refs are cached evidence. Before removing an original
clone, verify that the replacement contains every needed revision and
ref, including detached work and local tags; preserve local configuration
separately. A clean branch alone does not prove the clone disposable.

## Cost two: build artifacts

Classify output under study trees with the four tiers; active
projects and hand-written or tracked files remain protected.

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
  | xargs -r -0 du -sk \
  | awk '{total += $1} END {printf "%.1f GiB\n", total / 1048576}'
```

Restrict the depth. An unbounded search descends into vendored
dependency trees and double-counts nested artifact directories.

## What to report

Call out three groups explicitly, largest first within each:

- **Huge clones**: the largest by total size, with the `.git` share
  shown so the user can see where the weight sits.
- **Unshallow clones** — those reporting `false` with a `.git` directory
  above the survey's size floor, ranked by `.git` size. These are the
  conversion candidates.
- **Artifact directories** — build output, aggregated per language, as
  a single reclaimable figure.

A clone can appear in more than one group; say so, since the reclaim
actions differ.
