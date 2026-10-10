# Gates, commits, and recovery

Shared by `fix` and `xfail`.

## Contents

- Approval
- Diff gates
- Quality gates
- Minimal fix
- Commit messages
- Cross-dependency bugs
- Recovery
- Final report
- Plan awaiting approval
- Stopped run

## Approval

Ask the user to approve the plan. When no question tool is available, the
request's explicit scope is the approval, for the phases it names only ("only
the failing test" approves the test phases). A request with no explicit scope
gets the plan and a stop. Approval never covers a push.

## Diff gates

Derive the test-file patterns from the project's layout and naming, for
example `**/test_*.py`, `**/*_test.py`, `tests/**`, `**/*.spec.ts`. `**/`
matches zero or more directories, so top-level files match too.

`<diff-gate>` is `./diff_gate.py` resolved from this reference's
directory to an absolute path, written literally in every command, and run
with `python3`. It reads `git status`, ignores untracked build caches
(`__pycache__/`, `.pytest_cache/`, `node_modules/.cache/`), prints each
offending path, and exits 1 when any exist. The tree is clean when the
workflow starts, so every other change belongs to the commit being prepared.
Any Git failure or diagnostic stops the gate as an incomplete observation,
even when Git exits zero. The error includes Git's exit status and diagnostic.

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

## Quality gates

Read the project's AGENTS.md or CLAUDE.md for the formatter, linter, type
checker, and test commands (for example `ruff format`, `eslint`, `tsc --noEmit`,
`cargo test`). Run them before every commit. A commit with failing tests, lint
errors, or type errors is not acceptable.

Exception: the commit that applies the fix to a strict xfail test runs the
non-test gates only. The strict XPASS failure is the proof the fix works; the
full suite passes once the marker is removed.

## Minimal fix

Change only what is broken. Do not refactor surrounding code or add features.
Follow the project's existing patterns.

## Commit messages

Use the project's commit format from AGENTS.md or CLAUDE.md. Add no
`Co-Authored-By` line, no "Generated with" or other tool trailer, and no emoji;
hosts add them by default. Without a project format, name
the component, whether the commit adds the xfail test, fixes the bug, or
removes the xfail, why it was needed, and what changed. Wrap body lines at 72
characters; let URLs, paths, hashes, and long identifiers overflow.

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

## Recovery

After 3 failed attempts, stop and report what was tried, what the output shows,
and the suspected cause. Ask for guidance.

## Final report

One hero line (`✓` finished or `⚠` stopped) holding the whole result in a
single sentence, then `## Evidence` (every commit made, with short hashes,
including extra commits for a regression or a mid-run correction; the xfail
line from the reproduction run; and for `xfail` the fix-isolation result once
the fix exists), then `## Follow-ups` (omit when empty). Follow-ups list only
actions for the user, never narration of what the run did. A scoped run that
stopped after the failing test lists one commit and says in the hero line that
the fix is not made. Name no local paths or temp files.

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

- add_hours has the same weekend handling; not changed.
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

## Plan awaiting approval

A run that has not started because no one approved the plan uses the
stopped-run shape: a hero line such as `⚠ Nothing written yet because the plan
needs your approval.`, `## Plan`, `## To continue`. Plan items are plain
bullets without bold labels, and no paragraph sits between the hero line and
`## Plan`; put the diagnosis in one Plan bullet.

## Stopped run

One hero line (`⚠` plus the result in a single sentence, no colon), the plan under
`## Plan` when no one has approved it yet, then `## To continue` with what the
user must do. No other sections. Name commits by purpose, never by phase or
number. For a wrong repository root, say only that the root is wrong; never
describe what is in it. Name no local paths.

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
