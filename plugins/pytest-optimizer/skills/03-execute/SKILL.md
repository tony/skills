---
name: 03-execute
description: "Use when applying an approved pytest optimization plan as separate verified commits in an isolated worktree, with resumable progress."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"]
argument-hint: "[--from=<index>] [--dry-run] [--memory-dir=<path>]"
disable-model-invocation: true
---

# 03-execute

Land the plan as separate, verified commits on a new branch cut from the
approved base. Every edit, test run and commit happens in an owned scratch
worktree. The user's checkout, index and branches are never modified; the run
ends by naming the result branch and the command that merges it.

`$ARGUMENTS` may pass `--from=<index>` to start at a specific plan item,
`--dry-run` to run the same steps in a detached worktree that is discarded
(it writes nothing to `execution-log.json` or `state.json`), and
`--memory-dir` to override the memory location.

Arithmetic and state go through `../../scripts/measure.py` and Git isolation through
`../../scripts/isolate.py` (Python 3 standard library). Both paths resolve from
this skill's own directory, not the project's working directory: resolve this
file's directory, join each path, print the absolute paths once, and write those
literal paths in each command below where `<measure.py>` and `<isolate.py>`
appear.

## Step 1: Preconditions

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`. If none exists or `plan.json` is missing,
stop with the halted-run shape in `../../references/output-contract.md`.

Resolve `<runs-dir>` using the "Run files" section of
`../../references/memory-schema.md`; keep each item's verification record there.

Read `plan.json` and `state.json`. Refuse to run unless the evidence is bound:
the plan was approved and is unchanged since (`plan_hash`), `state.json` has an
`env_token`, every plan item carries it and a `patch_sha256`, and `HEAD` equals
`base_head`. The command checks them in that order and names the first failure:

```console
$ python3 <isolate.py> stale \
    --memory-dir <memory-dir> \
    --phase execute
```

On exit 1, print its `reason` and send the user to the phase its `rerun` names
(`pytest-optimizer:` followed by it).

Then read `baseline.json`, `control.json`, `collection.txt`,
`execution-log.json` if present, and the project quality-check and test
commands. The user's checkout may be dirty and may keep changing while this
skill runs: nothing here reads or writes its files, index or branches, so a
dirty tree is not a stop.

A resumed run (`state.json` has `exec_branch`) checks the result branch instead
of the checkout, listing every logged `commit_sha` in order:

```console
$ python3 <measure.py> chain \
    --base <base_head> \
    --head <exec_branch> \
    <every logged commit_sha, in order>
```

Exit 1 means the recorded history could not be verified: stop, print its
`reason`, and tell the user to run `pytest-optimizer:00-scan --force`.

Resume from `last_applied_index + 1` (or `--from`). Never re-apply an item that
already has a `commit_sha`. Nothing in this skill pushes.

## Step 2: Open the owned worktree

A fresh run (no `exec_branch`) takes a run id, then cuts the result branch from
the approved base:

```console
$ python3 <measure.py> run-id
```

```console
$ python3 <isolate.py> start \
    --repo . \
    --base <base_head> \
    --branch pytest-optimizer/<run_id>
```

Print its `tree` and `dir`, and store `run_id`, `exec_branch` and `exec_dir` in
`state.json` with `measure.py state update <memory-dir>/state.json --set
'exec_branch="<branch>"'` and the same for the others. A dry run omits `--branch`, which detaches the worktree, and
stores nothing. When the host refuses the worktree, stop: execution needs a real
branch.

A resumed run reuses `exec_dir`'s `tree` when it still exists, otherwise reopens
the branch (the command first prunes the stale worktree record a cleaned temp
directory leaves behind):

```console
$ python3 <isolate.py> start \
    --repo . \
    --base <base_head> \
    --branch <exec_branch> \
    --existing
```

Then clear any half-applied item, inside the owned tree only:

```console
$ python3 <isolate.py> reset \
    --cwd <tree>
```

If the last log entry has `pending_tree` and no `commit_sha`, a crash fell
between commit and checkpoint. Check whether the branch tip is that commit:

```console
$ python3 <isolate.py> landed \
    --cwd <tree> \
    --parent <pending_parent> \
    --tree <pending_tree>
```

On success, record the tip as the entry's `commit_sha`. On failure, reset the
owned tree to the item's `pending_parent` with `isolate.py reset --cwd <tree>
--to <pending_parent>` and re-apply the item; a matching commit subject never
establishes identity.

Run the project's commands below with `workdir` from the `start` output as the
working directory (`<tree>` itself, or the project's subdirectory when the
repository holds several projects), and the git and `isolate.py` commands on
`<tree>`. The tree holds only tracked files: rebuild the
environment there with the project's sync command, as `01-benchmark` does. The
tree is a Git boundary, not a sandbox: a project hook or an absolute path in a
test can still write outside it.

## Step 3: Apply each item in order

For each plan item not yet applied:

1. **Apply** the item's measured patch, bound by the hash `01-benchmark`
   recorded. Do not re-describe or retype the change:

   ```console
   $ python3 <isolate.py> apply \
       --cwd <tree> \
       --patch <memory-dir>/<patch> \
       --sha256 <patch_sha256> \
       --file <each path in files>
   ```

   Exit 1 (altered patch, stale context, a path outside the plan) is a failed
   item: go to 4.
2. **Verify green.** Run the project quality checks as declared in the
   project's `AGENTS.md`/`CLAUDE.md`, then the `test_command` from
   `baseline.json` with the item's measurement flags
   (`../../references/durations-parsing.md`, "Measurement command"):

   ```console
   $ python3 <measure.py> run \
       --cwd <workdir> \
       -- pytest \
       -p no:cacheprovider \
       -p no:randomly \
       > <runs-dir>/verify-<order>.jsonl
   ```

   Substitute `test_command` for `pytest`, and drop `-p no:cacheprovider` when
   the item's `cache` is `enabled`. Get the expected count from the script, which
   counts only the items already applied:

   ```console
   $ python3 <measure.py> expected-total \
       --through <order> \
       <memory-dir>/baseline.json \
       <memory-dir>/plan.json \
       <memory-dir>/execution-log.json
   ```

   Check outcome counts with the shared gate, which reads `valid` here and
   never `clears_noise`, since one run does not establish a speedup. Pass the
   number in the `expected_total` field as `--expect-total`:

   ```console
   $ python3 <measure.py> compare \
       --min-runs 1 \
       --expect-total <expected_total> \
       <memory-dir>/baseline.json \
       <runs-dir>/verify-<order>.jsonl
   ```

   Check that the same tests exist. Write the listing from `test_command`
   (not a bare `pytest`) run in the tree to
   `<runs-dir>/verify-<order>-collection.txt` as `00-scan` Step 2 does, and
   compare node ids against `collection.txt`, allowing only the removals of
   applied items (skip this for a typing or parametrize item, which changes ids
   by design):

   ```console
   $ python3 <measure.py> ids \
       --plan <memory-dir>/plan.json \
       --log <memory-dir>/execution-log.json \
       --through <order> \
       <memory-dir>/collection.txt \
       <runs-dir>/verify-<order>-collection.txt
   ```

   The item passes only when the quality checks pass, `valid` is true, and the
   ids match. Missing or empty outcomes fail; an exit 0 is insufficient. For a
   typing or parametrize item (H26-H32) the type checker must cover `tests/`.
3. **Gate, then commit.** Check that the staged bytes are exactly the item's
   files and the verification created or changed nothing else:

   ```console
   $ python3 <isolate.py> gate \
       --cwd <tree> \
       --file <each path in files>
   ```

   On exit 1 the item failed (go to 4); the verification changed paths outside
   the plan, which includes a formatter rewriting the patched files. On success
   write the log entry with `pending_subject`, `pending_parent` and
   `pending_tree` from the gate output, then commit with the drafted why/what
   message from `plan.json`, written per `../../references/prose-rules.md`
   (no trailers, no emoji; hosts add them by default; do not mention this):

   ```console
   $ git -C <tree> commit \
       --message <subject> \
       --message <body>
   ```

   Then confirm the commit holds the gated bytes, so a hook that edited files
   cannot slip past the verification:

   ```console
   $ python3 <isolate.py> landed \
       --cwd <tree> \
       --parent <pending_parent> \
       --tree <pending_tree>
   ```

   On success record the `commit_sha` and the verify run's `seconds`. When the
   commit fails (a hook rejects it, signing is unavailable) or `landed` fails,
   never retry with `--no-verify` or `--no-gpg-sign`: run
   `isolate.py reset --cwd <tree> --to <pending_parent>`, set the entry's
   `applied` to false with `skip_reason` "commit failed: <first line of the
   error>", remove its `pending_*` fields, and stop without starting the next
   item. Report the error and tell the user to fix the hook or signing and re-run
   `pytest-optimizer:03-execute --from=<index>`.
4. **On failure** (patch, verification, ids or gate), discard the item inside the
   owned tree. The command refuses any directory this run did not create:

   ```console
   $ python3 <isolate.py> reset \
       --cwd <tree>
   ```

   Exit 1 means the discard did not complete: stop, report its `reason`, and
   leave the tree for inspection. Otherwise mark the item `skipped` with the
   reason, mark every item whose `depends_on` names it `skipped` too ("depends on
   a skipped item"), and continue. Failures never reach the user's checkout, so
   no later step depends on repairing it.
5. **Checkpoint**: complete the entry in `execution-log.json` and update
   `state.json` immediately, so a re-run continues from the last checkpoint:

   ```console
   $ python3 <measure.py> state \
       update <memory-dir>/state.json \
       --set 'phase="execute"' \
       --set 'last_applied_index=<index>'
   ```
6. **Regression stop**: compare the item's verify `seconds` with the control:

   ```console
   $ python3 <measure.py> regress \
       <memory-dir>/control.json \
       <seconds>
   ```

   When `rerun` is true, re-run the verify command twice more and call it again
   with all three timings. Exit 1 (`regressed`) means the commits so far made the
   suite slower: stop before the next item, name the item, and ask whether to
   continue or drop it from the branch. Without a question tool, stop and say
   so.

A dry run keeps its log at `<runs-dir>/dry-run-log.json` (use it for the
`expected-total` and `ids` commands) and writes no state; it ends with the
discard in Step 4.

## Step 4: Re-measure and report

When no item was applied, remove the worktree and the unused branch, skip the
re-measure, and report the control as the result:

```console
$ python3 <isolate.py> finish \
    --dir <exec_dir> \
    --drop-branch-at <base_head>
```

Otherwise, with the final tree still open, resolve and create `<runs-dir>`, delete
`post-runs.jsonl` there, run one untimed warm-up, and time as many runs as
`baseline.json` recorded into it with the measurement flags above; if any applied
item has `cache` `enabled`, run them with the cache provider on so the warm-up
populates it and say so in the result. Compare against `control.json`, the same
fresh checkout without the changes, passing the count the script returns once
every applied item is in the tree:

```console
$ python3 <measure.py> compare \
    --expect-total <expected_total> \
    <memory-dir>/control.json \
    <runs-dir>/post-runs.jsonl
```

Then remove the worktree; the branch stays. Read `removed` in the output: when it
is not true, the worktree is still there, so say so in the closing sentence:

```console
$ python3 <isolate.py> finish \
    --dir <exec_dir>
```

Unless this was a dry run, mark the phase done with `measure.py state complete
<memory-dir>/state.json --phase execute`. Emit the `03-execute`
sections from `../../references/output-contract.md`, hero line first, nothing
before it. Write the prose per `../../references/prose-rules.md`. Reply in this
shape, as plain text outside any code fence, with plain bullets, no bold
(never `- **Label:** ...`), and no local paths:

```text
✓ 1 applied, 1 skipped on branch pytest-optimizer/run-1

## Applied

- 7c1e9d4 Share db_session across the session, verify green.

## Skipped

- H33 fixed sleep in test_report: discarded in the scratch worktree, test_report failed once the sleep was removed.

## Result

- 7.9s against 12.5s for the same checkout without the changes, 4.6s faster; the same 40 tests ran.

Merge it with git merge --ff-only pytest-optimizer/run-1 when you are ready.
```

A run that skipped every item opens with `⚠`, has no `## Applied` section, no
merge sentence and no text about removing the worktree or branch, and states each failed verification as the printed result
(counts and exit status), with no cause or threshold beyond that output; a dry run says "verified, nothing committed" in the hero and names no
branch. The merge sentence comes first: after it, the
`AskUserQuestion` panel offers a re-scan for a second pass (new candidates may
surface on a leaner suite), the opt-in cache/timing scaffolds, or stop. Without
a question tool, print those options as a plain list and stop. A re-scan restarts at
`pytest-optimizer:00-scan` with a fresh baseline, after the user merges.
