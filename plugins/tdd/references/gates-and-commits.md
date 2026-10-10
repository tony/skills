# Gates, commits, and recovery

Shared by `fix` and `xfail`.

## Contents

- Approval
- Diff gates
- Quality gates
- Minimal fix
- Fix commit
- Commit messages
- Stash round trip
- Cross-dependency bugs
- Recovery
- Final report
- Stopped run

## Approval

Write nothing until the plan is approved. The request itself is the approval
when it says to proceed ("go ahead with the full workflow") or limits scope
("only the failing test"), for the phases it names only. Otherwise ask the
user to approve the plan; where no question tool exists, a request with no
explicit scope gets the plan and a stop. Approval never covers a push.

## Diff gates

Derive the test-file patterns from the project's layout and naming, for
example `**/test_*.py`, `**/*_test.py`, `tests/**`, `**/*.spec.ts`. `**/`
matches zero or more directories, so top-level files match too.

`<diff-gate>` is `../scripts/diff_gate.py` resolved from this reference's
directory to an absolute path, written literally in every command, and run
with `python3`. It reads `git status`, ignores untracked build caches
(`__pycache__/`, `.pytest_cache/`, `node_modules/.cache/`), prints each
offending path, and exits 1 when any exist. The tree is clean when the
workflow starts, so every other change belongs to the commit being prepared.
Any Git failure or diagnostic stops the gate as an incomplete observation,
even when Git exits zero. The error includes Git's exit status and diagnostic.
A tracked file flagged skip-worktree or assume-unchanged (sparse checkout,
`git update-index`) hides edits from `git status`, so the gate stops on any
such flag as well.

Before a source-only commit, run the gate in `source-only` mode; it prints
every modified or untracked test file and must exit 0 without output:

```console
$ python3 <diff-gate> source-only \
    --pattern '**/test_*.py' \
    --pattern '**/*.spec.ts'
```

Before a test-only commit, run it in `test-only` mode; it prints every
modified or untracked file outside the patterns and must exit 0 without output:

```console
$ python3 <diff-gate> test-only \
    --pattern '**/test_*.py' \
    --pattern '**/*.spec.ts'
```

Stage by file name, never `git add -A` or `git commit -a`, so each commit
holds only the files its gate allows.

The gate classifies whole files. When the project keeps tests in the same
file as source (Rust `#[cfg(test)]` modules, doctests), a path pattern cannot
separate the two commits. Stage by hunk with `git add -p`, then confirm
`git diff --cached` holds only test hunks (test commits) or only source hunks
(fix commit) before committing, and say in the report that the file-level
gate did not cover that commit.

## Quality gates

Read the project's AGENTS.md or CLAUDE.md for the formatter, linter, type
checker, and test commands (for example `ruff format`, `eslint`, `tsc --noEmit`,
`cargo test`). Run them before every commit. A commit with failing tests, lint
errors, or type errors is not acceptable.

## Minimal fix

Change only what is broken. Do not refactor surrounding code or add features.
Follow the project's existing patterns.

## Fix commit

Both workflows prepare the source-only fix commit this way:

1. Perform the fixed-state check from the mechanism reference.
2. Strict mode: the annotated test fails for unexpected success, so run the
   non-test gates and defer the full suite to annotation removal. Any other
   failure does not qualify. Skip mode: run all quality gates with the skip
   restored; the unskipped passing assertion is the fix evidence.
3. Run `diff_gate.py` in `source-only` mode; it must print nothing.
4. Commit with the root cause in the message.

After annotation removal, both modes require the complete suite and all
quality gates to pass.

## Commit messages

Use the project's commit format from AGENTS.md or CLAUDE.md. Add no
`Co-Authored-By` line, no "Generated with" or other tool trailer, and no emoji;
hosts add them by default. Without a project format, name
the component, whether the commit adds the xfail test, fixes the bug, or
removes the xfail, why it was needed, and what changed. Wrap body lines at 72
characters; let URLs, paths, hashes, and long identifiers overflow.

## Stash round trip

Stash entries are shared by every linked worktree, so a peer can push or pop
between your commands and `stash@{0}` is not yours. Never run a bare
`git stash pop` or `git stash drop`. `<stash-roundtrip>` is
`../scripts/stash_roundtrip.py` resolved from this reference's directory to
an absolute path, written literally in every command, and run with `python3`.

Stash the changes. It prints the new stash's commit SHA and exits 1 when
nothing was stashed; treat the missing changes as a failure of the phase
before:

```console
$ python3 <stash-roundtrip> push
```

Delete the untracked caches the stashed-state test run created (they
regenerate; never other untracked files), then restore by that SHA. It
applies the stash commit and drops only the entry with the same SHA:

```console
$ python3 <stash-roundtrip> restore <sha>
```

On a restore failure, stop, keep the stash, and report its SHA.

## Cross-dependency bugs

When the bug spans this project and a dependency:

1. Ask the user for the dependency's own checkout. Never edit an installed or
   vendored copy (site-packages, `node_modules`, a package cache, a `vendor/`
   directory); a lockfile reinstall overwrites it.
2. In that checkout, run the repository checks first: `git rev-parse
   --show-toplevel` must be the dependency and not home or a parent of it
   (`(cd ~ && pwd -P)` gives the physical home path), and `git status
   --porcelain` must print nothing. Otherwise stop and tell the user.
3. Fix the dependency there with its own commit conventions, and run its test
   suite.
4. Point this project at the checkout with a path dependency, workspace link,
   or local override, then confirm the module path resolves to the checkout
   and not a package cache. Keep that override uncommitted: revert it before
   each diff gate and commit here, and reapply it to run tests.
5. Fix and test this project.
6. Tests that pass only through the override do not verify the committed
   dependency configuration. Report the consumer's committed dependency
   reference as unverified and list updating it to the released fix as a
   follow-up.

## Recovery

After 3 failed attempts, stop and report what was tried, what the output shows,
and the suspected cause. Leave the work as it stands: no reset, revert, or
clean. The report lists the commits made, the files left uncommitted, and any
stash SHA, then asks for guidance.

## Final report

One hero line (`✓` finished or `⚠` stopped) holding the whole result in a
single sentence, then `## Evidence` (every commit made, with short hashes,
including extra commits for a regression or a mid-run correction; the selected
mode and observed reproduction results; and for `xfail` the fix-isolation
result once the fix exists), then `## Follow-ups` (omit when empty). Follow-ups list only
actions for the user, at most one per thing this run observed, each naming
that observation; no general advice (input validation, CI behavior) and no
claim the run did not check, never narration of what the run did. A scoped run that
stopped after the failing test lists one commit and says in the hero line that
the fix is not made. Name no local paths or temp files. Report results only,
never the workflow rules followed (trailers, commit format, gate policy).

For skip mode, include the unskipped assertion failure and, when a fix exists,
its unskipped pass. Report annotated skips as skips, never as XPASS or proof
that the assertion ran.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Commit:** ...`), and no local paths:

```text
✓ Fixed the business-day off-by-one in add_days; three commits, all gates green.

## Evidence

- 3f9c2ab tests(fix[add_days]) Add xfail test for weekend rollover
- 81d0e4c fix(add_days) Skip weekends when rolling over
- c0a7e55 tests(add_days) Remove xfail marker
- Reproduction: 1 xfailed (AssertionError: expected Monday, got Saturday).
- With the fix stashed the test xfails again; with it restored it XPASSes.

## Follow-ups

- Check add_hours for the same weekend handling; it is unchanged.
```

A scoped run that made one commit looks like this:

```text
✓ Committed the failing test for the is_business_day Saturday bug; the fix is not made.

## Evidence

- 3f9c2ab tests(fix[is_business_day]) Add xfail test for Saturday
- Reproduction: 1 expected failure (AssertionError: True is not false).

## Follow-ups

- Ask for the fix when you want it.
```

## Stopped run

One hero line (`⚠` plus the result in a single sentence, no colon), then one
state section, then `## To continue` with what the user must do. No other
sections.

- Before approval, or when a Phase 0 gate stops the run, the state section is
  `## Plan`: plain bullets with no bold labels or noun-colon leads (never
  "Diagnosis: ..."), the diagnosis in one bullet,
  no paragraph between the hero line and the heading.
- After a recovery stop, it is `## State`: commits made, files left
  uncommitted, any stash SHA, and what was tried.

Name commits by purpose, never by phase or number. For a wrong repository
root, say only that the root is wrong; never describe what is in it. Name no
local paths.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold, and no local paths:

```text
⚠ Nothing written because the current directory is not the project's repository.

## Plan

- Add an xfail test for is_business_day(5) in the existing test file.
- Fix the upper bound in is_business_day as a separate source-only commit.
- Remove the xfail marker in a final test-only commit.

## To continue

- Run the workflow from the project's repository root.
- Approve the plan, or say what to change.
```
