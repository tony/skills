# Repo guard

The guard detects escaped worker writes and concurrent checkout changes. It
never repairs on its own: it does not run `checkout`,
`clean`, `reset`, or `stash` against the user's tree except when the user asks.
`scripts/engine.py` implements it; `scripts/test_engine.py` tests it. Every
weave command uses it except `fix-review`, which edits the repository on
purpose. A mutating run that applies nothing must verify its original state
before claiming the checkout is unchanged.

## Contents

- Snapshot
- Isolation
- Detection
- Decision
- Cleanup
- Unsafe toplevels and no-repo mode

## Snapshot

`engine.py init` records the checkout before any worker runs (outside no-repo
mode, below). It builds a tree
from a temporary index rebuilt from staging entries plus `git add -A`, so the user's index and
files are never touched. The tree holds every tracked change, deletion, and
untracked non-ignored file as it stood. It becomes a commit on top of `HEAD`,
pinned as `refs/weave-guard/<session>/pre`. Ignored files are not part of it.
It also records staging entries and the HEAD branch. A mutating session pins
an `initial` snapshot before stashing, then takes its dispatch snapshot after
stashing. Stash restoration uses `--index` to preserve partial staging.
The temporary index has no stat-cache shortcuts, so assume-unchanged and
skip-worktree flags cannot conceal working-file changes. User index flags
remain untouched.

## Isolation

Every read-only external CLI lane runs in a disposable detached worktree created from the
snapshot commit, so the CLI reads the user's uncommitted work and any write lands
in the throwaway tree. Each attempt gets a fresh worktree under the session
directory, and the engine removes it afterwards. If the worktree cannot be
created the lane fails; it never falls back to the user's checkout.

Host sub-agents of a read-only command also get snapshot worktrees
(`worktrees create`). Mutating commands start every worker's registered
worktree from `HEAD` after stashing the user's changes, including the host
`claude` lane under `model-clis`.
Native launches include the engine's literal per-call directory prefix and
absolute file-path rules. These instructions are not a sandbox: a shell `cd`
does not persist between sub-agent tool calls, and hosts do not universally
accept an arbitrary worker cwd.

Each CLI's own read-only mode stays on as a second defense. `agy` has none.
A CLI that writes through an absolute path to the checkout is caught by the
comparison below.

## Detection

`guard check` snapshots the checkout again and compares per-path content hashes
and `HEAD` with the pre snapshot, including staging and the HEAD branch. This catches a further edit to an
already-dirty file, which `git status --porcelain` cannot. `dispatch` runs it
after every CLI attempt, and the orchestrating skill runs it once after all
lanes finish.

A difference is recorded and never changed. Under `<session_dir>/guard/<id>/` the
engine writes `touched.json` (path to `A`, `M`, or `D`), `violation.patch`,
`post-copy/` (the current content of each touched file), and pins the post state
as `refs/weave-guard/<session>/post-<id>`. It appends `repo_guard_violation` to
`guard-events.jsonl` and warns on stderr. A repeat check of the same state adds
nothing.

A run cannot tell its own escaped write from an edit the user made meanwhile, so
the touched set includes both.

## Decision

Mutating runs halt on any drift under either backend. The engine refuses the
first adoption while an active run differs from its dispatch baseline.
Worktrees, leaked files, and the original stash stay intact.

Read-only runs offer once; headless runs keep and report.

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

`guard finish` runs before presentation and logs `repo_guard_final`. A mutating
run with no adoption compares against its initial working bytes, staging, and
HEAD after stash restoration. An adopted run reports no unchanged attestation.
When the session never recorded a
difference it deletes the session's pinned refs; otherwise they stay as
evidence. Existing `pre-reset-*` recovery pins are never deleted by `finish`.
`guard prune --days N` deletes pinned refs older than `N` days in a
repository, and the skills run it once per session at the end. Pins are
ordinary refs, so `git push --mirror` would publish them; prune first.

## Unsafe toplevels and no-repo mode

The engine refuses to snapshot, stash, or add worktrees to a toplevel that is
`/`, the home directory, or a directory that contains the home directory,
because `git add -A` there would pull a whole home tree into the object store.
A read-only command in such a checkout, in a directory with no repository, or
in a repository with no commits runs in no-repo mode instead: `session.json`
has `unguarded: true` and no snapshot, `guard check` returns
`{"ok": true, "violation": false, "unguarded": true}`, and lanes run in an
empty scratch directory under the session. Mutating commands and `fix-review`
refuse.
