# Gates, commits, and recovery

Shared by `fix` and `xfail`.

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

Use the project's commit format from AGENTS.md or CLAUDE.md. Without one, name
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

Reply in this shape, as plain text outside any code fence, with plain bullets
and no bold (never `- **Commit:** ...`):

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
