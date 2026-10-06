# Repo guard

The guard keeps weave workers out of the user's checkout. It isolates first,
detects second, and never repairs on its own: it does not run `checkout`,
`clean`, `reset`, or `stash` against the user's tree except when the user asks.
`scripts/engine.py` implements it; `scripts/test_engine.py` tests it. Every
weave command uses it except `fix-review`, which edits the repository on
purpose, and a mutating command skips the final comparison.

## Snapshot

`engine.py init` records the checkout before any worker runs. It builds a tree
from a temporary copy of the index plus `git add -A`, so the user's index and
files are never touched. The tree holds every tracked change, deletion, and
untracked non-ignored file as it stood. It becomes a commit on top of `HEAD`,
pinned as `refs/weave-guard/<session>/pre`. Ignored files are not part of it.

## Isolation

Every external CLI lane runs in a disposable detached worktree created from the
snapshot commit, so the CLI reads the user's uncommitted work and any write lands
in the throwaway tree. Each attempt gets a fresh worktree under the session
directory, and the engine removes it afterwards. If the worktree cannot be
created the lane fails; it never falls back to the user's checkout.

Host sub-agents of a read-only command also get snapshot worktrees
(`worktrees create`). Mutating commands start worker worktrees from `HEAD` after
stashing the user's changes.

Each CLI's own read-only mode stays on as a second defense. `agy` has none.
A CLI that writes through an absolute path to the checkout is caught by the
comparison below.

## Detection

`guard check` snapshots the checkout again and compares per-path content hashes
and `HEAD` with the pre snapshot. This catches a further edit to an
already-dirty file, which `git status --porcelain` cannot. `dispatch` runs it
after every CLI attempt, and the orchestrating skill runs it once after all
lanes finish.

A difference is recorded and never changed. Under `$SESSION_DIR/guard/<id>/` the
engine writes `touched.json` (path to `A`, `M`, or `D`), `violation.patch`,
`post-copy/` (the current content of each touched file), and pins the post state
as `refs/weave-guard/<session>/post-<id>`. It appends `repo_guard_violation` to
`guard-events.jsonl` and warns on stderr. A repeat check of the same state adds
nothing.

A run cannot tell its own escaped write from an edit the user made meanwhile, so
the touched set includes both.

## Decision

After all lanes finish, the skill offers once; headless runs keep and report.

- **Keep**: the checkout stays as it is.
- **Revert touched paths** (`guard resolve --choice revert`): restores each
  touched path from the snapshot through a temporary index, and removes only
  paths the snapshot lacked, along with directories that become empty. Other
  paths and the user's index are untouched.
- **Quarantine all** (`guard resolve --choice quarantine`): stashes the whole
  checkout, tracked and untracked, under a stash named
  `weave-guard-<session>: quarantine`.

Every choice first records the difference, so the post-run state stays
recoverable from `post-copy/` and the pinned ref, and the original state from
the pre ref. A moved `HEAD` is reported and never undone.

## Cleanup

`guard finish` logs `repo_guard_final`. When the session never recorded a
difference it deletes the session's pinned refs; otherwise they stay as
evidence. `guard prune --days N` deletes pinned refs older than `N` days in a
repository.
