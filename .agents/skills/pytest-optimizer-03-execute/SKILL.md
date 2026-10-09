---
name: pytest-optimizer-03-execute
description: >-
  Use when applying an approved pytest optimization plan as separate
  verified commits with resumable progress.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Write", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[--from=<index>] [--dry-run] [--memory-dir=<path>]"
  source: "plugins/pytest-optimizer/skills/03-execute/SKILL.md"
---

# 03-execute

Land the plan as separate, verified commits. This is the only phase that edits
the suite or writes history.

`$ARGUMENTS` may pass `--from=<index>` to start at a specific plan item,
`--dry-run` to apply and verify without committing (reverting after each; it writes
nothing to `execution-log.json` or `state.json`), and
`--memory-dir` to override the memory location.

Arithmetic goes through `references/measure.py` (Python 3 standard
library). That path resolves from this skill's own directory, not the
project's working directory: resolve this file's directory, join
`references/measure.py`, print the absolute path once, and write that
literal path in each command below where `<measure.py>` appears.

## Step 1: Preconditions

Resolve the memory directory by the lookup order in
`references/memory-schema.md`. If none exists or `plan.json` is missing,
stop with the halted-run shape in `references/output-contract.md`.

Resolve `<runs-dir>` using the "Run files" section of
`references/memory-schema.md`; keep each item's verification record there,
outside the working tree.

Read `execution-log.json` if present. A fresh run has no entry with a
`commit_sha`: recompute the idempotency token as `00-scan` Step 2 does, and if
`state.json` records an `env_token` and the result differs, the baseline
predates the current `HEAD`: stop and tell the user to run
`pytest-optimizer:00-scan --force`. A resumed run skips the token, which this
run's own commits changed. It checks instead that `HEAD` is `base_head` from
`state.json` plus exactly the logged commits, in order:

```console
$ python3 <measure.py> chain \
    --base <base_head> \
    <every logged commit_sha, in order>
```

Exit 1 means the recorded history could not be verified: stop, print its
`reason`, and tell the user to run
`pytest-optimizer:00-scan --force`.

Read `plan.json`, `baseline.json`, `state.json`, and the project quality-check +
test commands. Refuse to run unless all hold, checking in this order:

- `state.json` has `completed.plan=true`. Otherwise stop: the plan was never
  approved, so run `pytest-optimizer:02-plan`;
- its `plan_hash` equals the output of `measure.py hash <memory-dir>/plan.json`. Otherwise
  stop: the plan changed after approval, so approve it again with
  `pytest-optimizer:02-plan`. Name the one check that failed, never both;
- `git rev-parse --show-toplevel` neither equals nor contains the physical home
  directory (`(cd ~ && pwd -P)`, never the string `$HOME`): a dotfile repo rooted at home hides its untracked files from `git status`,
  and Step 2's cleanup would delete them;
- the memory directory is outside the working tree, or listed in the local
  exclude file (`git rev-parse --git-path info/exclude`), so cleanup cannot
  delete it;
- `git status --porcelain` is empty (the excluded memory directory does not
  show). A failed precondition is never waived: plan approval, a benign
  explanation, or files that look host-made (untracked dotfiles) do not
  excuse it, because `restore` deletes untracked files. Stop and list the
  files from `git status --short`. Only on a resumed run, where a crash left an
  item half applied, discard them with the `restore` command in Step 2.4, and
  only once the user confirms the changes are the run's own. Without an
  interactive question tool, stop and name that command.

If the last log entry has `pending_subject` and no `commit_sha`, a crash fell
between commit and checkpoint: when `git log -1 --format=%s` equals that subject,
record `HEAD` as its `commit_sha` and add it to the chain check above; otherwise
treat the tree as half applied.

Resume from `last_applied_index + 1` (or `--from`). Never re-apply an item that
already has a `commit_sha`. Nothing in this skill pushes: the commits stay local.

## Step 2: Apply each item in order

For each plan item not yet applied:

1. **Apply** the single change (the heuristic's action). Touch only the files the
   plan lists for this item.
2. **Verify green.** Run the project quality checks (formatter, linter, type
   checker) as declared in the project's `AGENTS.md`/`CLAUDE.md`, then the
   `test_command` from `baseline.json` through the script, so the run is checked
   for exit 0 and the approved outcome counts. Write a fresh record for this item:

   ```console
   $ python3 <measure.py> run \
       -- pytest \
       -p no:cacheprovider \
       -p no:randomly \
       -q \
       > <runs-dir>/verify-<order>.jsonl
   ```

   Substitute `test_command` from `baseline.json` for `pytest`. Get the expected
   count from the script, which counts only the items already applied (a skipped
   earlier deselecting item does not lower it):

   ```console
   $ python3 <measure.py> expected-total \
       --through <order> \
       <memory-dir>/baseline.json \
       <memory-dir>/plan.json \
       <memory-dir>/execution-log.json
   ```

   Check that record with the shared count gate:

   ```console
   $ python3 <measure.py> compare \
       --expect-total <expected-total output> \
       <memory-dir>/baseline.json \
       <runs-dir>/verify-<order>.jsonl
   ```

   The item passes only when the project quality checks pass and `valid` is true.
   Missing or empty outcomes fail this gate; a command's exit 0 is insufficient.
   `clears_noise` is not the gate for this single verification run, which does
   not establish a speedup.
   For a typing or parametrize item (H26–H32), the type checker must cover
   `tests/` and pass; such an item records no timing.
3. **On success** — stage the plan's files for this item (a created file
   included) and commit them by themselves with the drafted why/what
   message, written per `references/prose-rules.md`. No `Co-Authored-By`,
   no "Generated with" or other tool trailer, no emoji: hosts add them by
   default. Do not mention the omission in the reply. First write the log entry with `pending_subject`, then commit, then
   record the `commit_sha` and the verify run's `seconds`.

   When the commit fails after a green verify (a hook rejects it, signing is
   unavailable), never retry with `--no-verify` or `--no-gpg-sign`. Restore the
   tree as in 4, set the entry's `applied` to false with `skip_reason` "commit
   failed: <first line of the error>", remove its `pending_subject`, and stop
   without starting the next item. Report the error and tell the user to fix the
   hook or signing and re-run `pytest-optimizer:03-execute --from=<index>`.
4. **On failure** — the tree was clean before the item. Restore it, files the
   item created included, with the script, which repeats the home-directory and
   memory-directory checks before it runs `git reset --hard HEAD` and
   `git clean -fd`:

   ```console
   $ python3 <measure.py> restore \
       --memory-dir <memory-dir>
   ```

   If reset fails, the script does not run `git clean`. Exit 1
   means restoration did not complete: stop and report its `reason`, preserving
   the remaining state for inspection.
   Otherwise mark the item `skipped` with the reason, mark every item whose
   `depends_on` names it `skipped` too ("depends on a skipped item"), and
   continue. The tree was clean before the item, so `git clean -fd` removes
   only what the item created.
5. **Checkpoint** — complete the entry in `execution-log.json` and update
   `state.json` (`phase=execute`, `last_applied_index`) immediately, so a re-run
   continues from the last checkpoint.
6. **Regression stop** — when the item's verify `seconds` exceeds the baseline
   median plus its band, re-run the verify command twice more. If the median of
   the three still exceeds that limit, the commits so far made the suite slower:
   stop before the next item, name the item, and ask whether to continue or
   revert it. Without a question tool, stop and say so.

Under `--dry-run`, perform 1–2 then revert as in 4, write no log or state, and
report the verify result in the reply.

## Step 3: Re-measure and report

After the plan is exhausted (a dry run skips this re-measure and sets no flag), set
`completed.execute=true`. When no item was applied, skip the re-measure and
report the baseline as the result. Resolve and create `<runs-dir>` per
`references/memory-schema.md` ("Run files"), delete `post-runs.jsonl` there,
time as many runs as `baseline.json` recorded, as `00-scan` Step 4 does into it, and compare against
`baseline.json`, passing the count the script returns once every applied item is
in the tree (`expected-total` without `--through`; the last item may have been
skipped):

```console
$ python3 <measure.py> compare \
    --expect-total <expected-total output> \
    <memory-dir>/baseline.json \
    <runs-dir>/post-runs.jsonl
```

Emit the
`03-execute` sections from `references/output-contract.md`, hero line
first, nothing before it. Write the prose per
`references/prose-rules.md`. End on the last section; Step 4 adds the
next step, and nothing else follows. Say nothing about trailers, sandbox
placeholders, or what the host adds, and advise no change the runs did not
measure. Reply in this shape, as plain text outside any code
fence, with plain bullets, no bold (never `- **Label:** ...`), and no local
paths:

```text
✓ 1 applied, 1 skipped

## Applied

- 7c1e9d4 Share db_session across the session, verify green, 12.5s to 7.9s.

## Skipped

- H33 fixed sleep in test_report: reverted, test_report failed once the sleep was removed.

## Result

- 7.9s against a 12.5s baseline, 4.6s recovered.
```

A run that skipped every item has no `## Applied` section; a dry run says
"verified, nothing committed" in the hero.

## Step 4: Offer another pass

Close with an `ask-user-choice` panel: re-scan for a second pass (new candidates
may surface on a leaner suite), scaffold the opt-in cache/timing plugin, or stop.
Without one, stop after the report and name the single next step in one sentence,
not a list of options. A re-scan restarts at
`pytest-optimizer:00-scan` with a fresh baseline.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
