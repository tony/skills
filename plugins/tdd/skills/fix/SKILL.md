---
name: fix
description: "Use when fixing a bug test-first: reproduce it as an xfail test, find the root cause, fix, and verify."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task"]
argument-hint: Paste or describe the bug to reproduce and fix
user-invocable: true
disable-model-invocation: true
---

# TDD Bug-Fix Workflow

Reproduce the bug as an expected-to-fail test, fix it, then turn the test into
a regression test. Three commits: xfail test, fix, xfail removal.

Initial bug report: $ARGUMENTS

Shared rules: [xfail mechanisms](../../references/xfail-mechanisms.md) and
[gates, commits, recovery](../../references/gates-and-commits.md). Write
commit messages per `../../references/prose-rules.md`, with no
`Co-Authored-By`, no "Generated with" or other tool trailers, and no emoji.

## Phase 1: Understand the Bug

1. Create a todo list tracking all phases.
2. Identify the symptom, expected behavior, trigger conditions, and affected
   component from the report.
3. Read the project's AGENTS.md / CLAUDE.md for test conventions, quality gate
   commands, and commit format.
4. Use Explore agents to find the test file for this area, the suspected source
   file, and fixtures that help reproduce the scenario. Read them.
5. Summarize the root cause, the xfail test you would write, and the minimal
   fix, and ask the user to confirm. Without an interactive question tool, the
   request is the confirmation. When the user asked only for the failing test,
   stop after Phase 2.
6. Confirm `git rev-parse --show-toplevel` is the project the bug lives in
   and `git status --porcelain` prints nothing. Otherwise stop before writing
   anything and never commit unrelated changes. The stopped report keeps the
   step 5 summary, asks the user to confirm it, and says what to fix in the
   repository.

## Phase 2: Write a Failing Test (xfail)

Follow the project's test conventions strictly; read existing tests before
writing one. Pick the mechanism from the xfail-mechanisms reference.

1. Choose the test file and study its patterns (fixtures, assertions, imports).
2. Write a test that has a descriptive name, a comment or docstring explaining
   the bug, uses existing fixtures, asserts the correct behavior (not the buggy
   behavior), and carries the expected-failure marker.
3. Run it and confirm it fails as expected:

   ```console
   $ <project's test command> <test_file>::<test_name>
   ```
4. Run the full test file.
5. Run the quality gates.
6. Commit the failing test, marked as an xfail for a known bug. Before the
   commit, `git status --porcelain` lists test files only; stage nothing else.

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
3. Run the test. With a strict mechanism it now reports an unexpected pass
   (XPASS in pytest). With a skip-based mechanism, remove the skip, run the
   test, and expect a pass.
4. Run the quality gates. With a strict mechanism, run the non-test gates only;
   the XPASS failure is expected.
5. Commit the fix with the root cause in the message. Before the commit,
   `git status --porcelain` lists no test files.

## Phase 5: Remove xfail and Verify

1. Remove the expected-failure marker (or skip).
2. Rewrite the test comment to describe a regression test, not a bug report.
3. Run the test; it must pass.
4. Run the full suite for the affected file or module.
5. Run the full quality gates.
6. When everything passes, commit, noting the xfail is removed because the fix
   is verified.

## Phase 6: Recovery Loop

When the test still fails after the fix:

1. Check the reproduction. Read the test and run it verbosely. If it tests the
   wrong thing, return to Phase 2, rewrite it, and recommit.
2. Check the fix. Add debug logging to confirm the fix executes. Stale builds
   and cached installs can run old code, so confirm module paths point to local
   source and reinstall if not. If the fix is wrong, revert it, return to
   Phase 3, and apply a new fix in Phase 4.

## Report

Report per the final-report and stopped-run shapes in
`../../references/gates-and-commits.md`. Name commits by purpose, never by
phase or number.
