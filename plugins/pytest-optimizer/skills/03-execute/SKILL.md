---
name: 03-execute
description: "Use when applying an approved pytest optimization plan as separate verified commits with resumable progress."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"]
argument-hint: "[--from=<index>] [--dry-run] [--memory-dir=<path>]"
user-invocable: true
disable-model-invocation: true
---

# 03-execute

Land the plan as separate, verified commits. This is the only phase that edits
the suite or writes history.

`$ARGUMENTS` may pass `--from=<index>` to start at a specific plan item,
`--dry-run` to apply and verify without committing (reverting after each), and
`--memory-dir` to override the memory location.

Arithmetic goes through `../../scripts/measure.py` (Python 3 standard
library). That path resolves from this skill's own directory, not the
project's working directory: resolve this file's directory, join
`../../scripts/measure.py`, print the absolute path once, and write that
literal path in each command below where `<measure.py>` appears.

## Step 1: Preconditions

Resolve the memory directory by the lookup order in
`../../references/memory-schema.md`. If none exists or `plan.json` is missing,
stop with the halted-run shape in `../../references/output-contract.md`.

Recompute the idempotency token as `00-scan` Step 2 does. If `state.json`
records an `env_token` and the result differs, the baseline predates the current `HEAD`: stop and
tell the user to run `pytest-optimizer:00-scan --force`.

Read `plan.json`, `baseline.json`, `state.json`, and the project quality-check +
test commands. Refuse to run unless:

- `git rev-parse --show-toplevel` is neither `$HOME` nor a directory containing
  it: a dotfile repo rooted at home hides its untracked files from `git status`,
  and Step 2's cleanup would delete them;
- the memory directory is outside the working tree, or listed in the local
  exclude file (`git rev-parse --git-path info/exclude`), so cleanup cannot
  delete it;
- `git status --porcelain` is empty (the excluded memory directory does not
  show), and
- `state.json` has `completed.plan=true` and its `plan_hash` equals the output of
  `measure.py hash plan.json`. Otherwise the plan was not approved in
  `pytest-optimizer:02-plan` or changed afterwards.

Read `execution-log.json` if present and resume from `last_applied_index + 1`
(or `--from`). Never re-apply an item that already has a `commit_sha`.

## Step 2: Apply each item in order

For each plan item not yet applied:

1. **Apply** the single change (the heuristic's action). Touch only the files the
   plan lists for this item.
2. **Verify green.** Run the project quality checks (formatter, linter, type
   checker) as declared in the project's `AGENTS.md`/`CLAUDE.md`, then the
   `test_command` from `baseline.json` through the script, so the run is checked
   for exit 0 and an unchanged test count:

   ```console
   $ python3 <measure.py> run \
       -- pytest -p no:cacheprovider -q
   ```

   Substitute `test_command` from `baseline.json` for `pytest`. The item passes
   when `exit` is 0, `total` equals the item's `expected_total` from `plan.json`,
   and the non-passing count (`total - passed`) equals the baseline's.
   For a typing or parametrize item (H26–H32), the type checker must cover
   `tests/` and pass.
3. **On success** — commit this change **alone** with the drafted why/what
   message, written per `../../references/prose-rules.md`. No `Co-Authored-By`,
   no "Generated with" or other tool trailer, no emoji: hosts add them by
   default. Record the `commit_sha`.
4. **On failure** — the tree was clean before the item. Restore it, files the
   item created included, with the script, which repeats the `$HOME` and
   memory-directory checks before it runs `git reset --hard HEAD` and
   `git clean -fd`:

   ```console
   $ python3 <measure.py> restore \
       --memory-dir <memory-dir>
   ```

   Exit 1 means it refused and changed nothing: stop and report its `reason`.
   Otherwise mark the item `skipped` with the reason and continue.
5. **Checkpoint** — append the outcome to `execution-log.json` and update
   `state.json` (`phase=execute`, `last_applied_index`) immediately, so a re-run
   continues from the last checkpoint.

Under `--dry-run`, perform 1–2 then revert as in 4 and log the verify result
without committing.

## Step 3: Re-measure and report

After the plan is exhausted, re-run the baseline measurement (`00-scan` Step 4)
and compare against `baseline.json` with `measure.py compare`. Emit the
`03-execute` sections from `../../references/output-contract.md`. Write the
prose per `../../references/prose-rules.md`.

## Step 4: Offer another pass

Close with an `AskUserQuestion` panel: re-scan for a second pass (new candidates
may surface on a leaner suite), scaffold the opt-in cache/timing plugin, or stop.
Without one, stop after the report. A re-scan restarts at
`pytest-optimizer:00-scan` with a fresh baseline.
