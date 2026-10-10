---
name: tdd-fix
description: >-
  Use when fixing a bug test-first: write a failing test to reproduce it,
  find the root cause, fix, and add a regression test.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent"]
metadata:
  argument-hint: "Paste or describe the bug to reproduce and fix"
  source: "plugins/tdd/skills/fix/SKILL.md"
---

# TDD Bug-Fix Workflow

Reproduce the bug as an expected-to-fail test, fix it, then turn the test into
a regression test. Three commits: xfail test, fix, xfail removal.

Initial bug report: $ARGUMENTS

Shared rules: [xfail mechanisms](references/xfail-mechanisms.md) and
[gates, commits, recovery](references/gates-and-commits.md). Write
commit messages per `references/prose-rules.md` and the reference's
"Commit messages" section.

## Phase 1: Understand the Bug

1. Create a todo list tracking all phases.
2. Identify the symptom, expected behavior, trigger conditions, and affected
   component from the report.
3. Read the project's AGENTS.md / CLAUDE.md for test conventions, quality gate
   commands, and commit format.
4. Use Explore agents (or read the files directly where none exist) to find the
   test file for this area, the suspected source file, and fixtures that help
   reproduce the scenario. Read them.
5. Summarize the root cause, the xfail test you would write, and the minimal
   fix, and wait for approval per the approval rule in the gates-and-commits
   reference; Phase 2 writes the first file. When the user asked only for the
   failing test, stop after Phase 2.
6. Confirm `git rev-parse --show-toplevel` is the project the bug lives in
   and `git status --porcelain` prints nothing. Otherwise stop before writing
   anything and never commit unrelated changes. The stopped report keeps the
   step 5 summary under `## Plan`, asks the user to confirm it, and says what
   to fix in the repository.

## Phase 2: Write a Failing Test (xfail)

Follow the project's test conventions strictly; read existing tests before
writing one. Pick the mechanism from the xfail-mechanisms reference.

1. Choose the test file and study its patterns (fixtures, assertions, imports).
2. Write a test that has a descriptive name, a comment or docstring explaining
   the bug, uses existing fixtures, asserts the correct behavior (not the buggy
   behavior), and carries the selected expected-failure annotation or skip.
3. Run the selected test: strict mode must accept its expected failure; skip
   mode must report it skipped. Check the outcome against the mechanism
   reference:

   ```console
   $ <project's test command> <the framework's single-test selector for the new test>
   ```
4. Temporarily remove the annotation and run the same test. The intended
   assertion must fail for the bug's symptom, not setup or an unrelated error.
   Restore the annotation. A skip alone is not reproduction evidence.
5. Run the full test file and quality gates.
6. Commit the test with its expected-failure annotation or skip. Derive the
   test patterns and run `diff_gate.py` in `test-only` mode (see "Diff gates"
   in the gates-and-commits reference); it must print nothing.

## Phase 3: Find the Root Cause

1. Read the source path the test exercises.
2. Add temporary debug logging if needed, and track it for cleanup.
3. Identify the root cause: the specific lines or logic gap. Document it.
4. If the bug spans a dependency, follow the cross-dependency steps in the
   gates-and-commits reference.

## Phase 4: Fix the Bug

Apply the minimal fix (see the gates-and-commits reference).

1. Apply the fix.
2. Remove the debug logging added in Phase 3.
3. Prepare and make the fix commit per "Fix commit" in the
   gates-and-commits reference.

## Phase 5: Remove xfail and Verify

1. Remove the expected-failure marker (or the restored skip).
2. Rewrite the test comment to describe a regression test, not a bug report.
3. Run the test; it must pass.
4. Run the full suite for the affected file or module.
5. Run the full quality gates.
6. Run `diff_gate.py` in `test-only` mode; it must print nothing.
   Then commit, noting the xfail is removed because the fix is verified.

## Phase 6: Recovery Loop

When the unannotated assertion still fails after the fix, or the annotated
result differs from the selected mode's fixed-state result:

1. Check the reproduction. Read the test and run it verbosely. If it tests the
   wrong thing, return to Phase 2, rewrite it, and recommit.
2. Check the fix. Add debug logging to confirm the fix executes. Stale builds
   and cached installs can run old code, so confirm module paths point to local
   source and reinstall if not. If the fix is wrong, undo your own uncommitted
   source edits (after the fix commit, add a corrective commit; never rewrite
   commits), return to Phase 3, and apply a new fix in Phase 4.

Gate every recommit with the check its phase names. After 3 failed attempts,
stop per "Recovery" in the gates-and-commits reference.

## Report

Report per the final-report and stopped-run shapes in
`references/gates-and-commits.md`. Name commits by purpose, never by
phase or number.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
