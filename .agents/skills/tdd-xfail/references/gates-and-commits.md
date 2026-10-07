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

Derive the test-file patterns from the project's layout and naming. Write each
as its own `:(glob)` pathspec, for example `:(glob)**/test_*.py`,
`:(glob)**/*_test.py`, `:(glob)tests/**`, `:(glob)**/*.spec.ts`. Only `:(glob)`
makes `**/` match top-level files too.

The tree is clean when the workflow starts, so every change in it belongs to
the commit being prepared.

Before a source-only commit, list modified and untracked test files. The
command must print nothing:

```console
$ git status --porcelain \
    -- ':(glob)**/test_*.py' ':(glob)**/*.spec.ts'
```

Before a test-only commit, list modified and untracked files outside the test
patterns. The command must print nothing. Use one `:(exclude,glob)` pathspec
per pattern; one exclude holding several patterns excludes nothing:

```console
$ git status --porcelain \
    -- . ':(exclude,glob)**/test_*.py' ':(exclude,glob)**/*.spec.ts'
```

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

1. Fix the dependency first, with its own commit conventions.
2. Run the dependency's test suite.
3. Point this project at the fixed local source. Package managers that enforce
   lockfiles overwrite local installs, so use a path dependency, workspace link,
   or local override, then confirm the module path resolves to the local source
   and not a package cache.
4. Fix and test this project.

## Recovery

After 3 failed attempts, stop and report what was tried, what the output shows,
and the suspected cause. Ask for guidance.

## Final report

One hero line (`✓` finished or `⚠` stopped, with the result in one sentence),
then `## Evidence` (the three commit subjects with short hashes, the xfail
line from the reproduction run, and for `xfail` the fix-isolation result), then
`## Follow-ups` (omit when empty). Name no local paths or temp files.

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

## Plan awaiting approval

A run that has not started because no one approved the plan uses the
stopped-run shape: a hero line such as `⚠ Nothing written yet. The plan below
needs your approval.`, `## Plan`, `## To continue`. Plan items are plain
bullets without bold labels, and no paragraph sits between the hero line and
`## Plan`; put the diagnosis in one Plan bullet.

## Stopped run

One hero line (`⚠` plus the result in one sentence, no colon), the plan under
`## Plan` when no one has approved it yet, then `## To continue` with what the
user must do. No other sections. Name commits by purpose, never by phase or
number, and name no local paths or repository details beyond what the user
must fix.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold, and no local paths:

```text
⚠ Nothing written. The current directory is not the project's repository.

## Plan

- Add an xfail test for is_business_day(5) in the existing test file.
- Fix the upper bound in is_business_day as a separate source-only commit.
- Remove the xfail marker in a final test-only commit.

## To continue

- Run the workflow from the project's repository root.
- Approve the plan, or say what to change.
```
