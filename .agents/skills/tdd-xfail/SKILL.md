---
name: tdd-xfail
description: >-
  Use when fixing a bug through strict xfail reproduction and needing proof
  that the test fails for the intended reason.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task"]
metadata:
  argument-hint: "Paste or describe the bug to reproduce and fix with hermetic xfail guards"
  source: "plugins/tdd/skills/xfail/SKILL.md"
---

# Hermetic xfail TDD Workflow

Fix a bug with strict reproduction guards. Each phase has a gate that passes
before the next begins. The result is proof that the test fails for the right
reason, in three commits: test only, source only, test only.

Initial bug report: $ARGUMENTS

Shared rules: [xfail mechanisms](references/xfail-mechanisms.md) and
[gates, commits, recovery](references/gates-and-commits.md). Write
commit messages per `references/prose-rules.md`.

## Orchestration Plan

Before executing any phase, enter plan mode and produce an orchestration
plan. Plan-mode activation varies by host:

- Claude Code: `EnterPlanMode` tool
- Cursor / Codex / Gemini: `/plan` or `Shift+Tab`

The plan must contain:

1. **Bug summary** — symptom, expected behavior, trigger conditions, affected component
2. **Test strategy** — which test file, which fixtures, which xfail mechanism
3. **Mock assessment** — are mocks required? If so, what real behavior do they replace, and how will you verify the failure is genuine (not mock-induced)?
4. **Framework detection** — which mechanism applies (xfail-mechanisms reference)
5. **Diff-gate file sets** — which paths are test files, which are source files
6. **Quality gates** — commands from the project's AGENTS.md/CLAUDE.md

Present the plan to the user and wait for approval before executing.

If plan mode is unavailable, write the plan as numbered steps in your
response and confirm with the user before proceeding.

## Phase 0: Discover Conventions

1. Create a todo list tracking all phases.
2. Read the project's AGENTS.md / CLAUDE.md for test framework and conventions,
   quality gate commands, and commit format.
3. Detect the framework and select the mechanism from the xfail-mechanisms
   reference.
4. Identify the test-file glob patterns the diff gates use. Common patterns:
   `**/test_*`, `**/*_test.*`, `**/tests/**`, `**/__tests__/**`,
   `**/*.test.*`, `**/*.spec.*`.
5. Use Explore agents to find the relevant source and existing tests.
6. When the bug spans a dependency, follow the cross-dependency steps in the
   gates-and-commits reference, running this protocol in the dependency first.

### Frameworks without strict xfail

A skipped test never executes, so it cannot XPASS. Run a skip-remove-run-reskip
cycle at each verification phase:

- Phase 1: write the test with the skip. Run it and confirm it is skipped.
- Phase 2: remove the skip, run the test (it must fail for the right reason),
  restore the skip.
- Phase 3: apply the fix, remove the skip, run the test (it must pass), restore
  the skip.
- Phase 4: stash the fix, remove the skip, run the test (it must fail again),
  restore the skip, pop the stash.
- Phase 5: remove the skip permanently.

The diff gates and three-commit structure are unchanged.

## Phase 1: Reproduce — Write xfail Test

Create a test that reproduces the bug, marked expected-to-fail.

The test must exercise real code paths. When mocking is unavoidable (network,
filesystem, external services), the test must show the failure matches the
bug's actual symptom: same exception type, message, or wrong-value pattern. If
the mock causes the failure instead of the bug, discard the test and start over.

1. Study existing test patterns in the target file.
2. Write a test with a descriptive name, existing fixtures, the strict
   mechanism, and an assertion of the correct behavior (not the buggy one).
3. Run it. It must report an expected failure (`xfail` in pytest, not `FAILED`).
4. Run the full test file.
5. Run all quality gates.

### Gate 1: xfail confirmation

The test must produce an expected-failure result. If it passes outright, it does
not reproduce the bug; rewrite it. If it fails with an exception not matching
`raises`, it targets the wrong symptom.

6. Commit test file changes only.

## Phase 2: Verify Reproduction Is Genuine

Prove the test fails because of the bug, not the test setup.

1. Temporarily remove the xfail marker.
2. Run the test; it must fail.
3. Check that the error matches the bug's symptom, the exception type is the
   expected one, and no misconfigured mock could produce the same failure.
4. Restore the marker.

### Gate 2: genuine-failure confirmation

If the failure does not match the symptom, the reproduction is contaminated.
Delete the test and return to Phase 1; do not tweak the mock setup until it
looks right. This phase produces no commit.

## Phase 3: Apply Fix

Fix the source. Zero test file changes in this commit. Apply the minimal fix
(see the gates-and-commits reference).

1. Apply the fix to the source code.
2. Run the xfail test. A strict mechanism now reports the unexpected pass as a
   failure: pytest shows `[XPASS(strict)]`; Jest `it.failing`, Vitest
   `it.fails`, and Rust `#[should_panic]` report a failed test.
3. Run the non-test quality gates (formatter, linter, type checker). Skip the
   full test suite; the strict XPASS failure confirms the fix.

### Gate 3: zero-diff on test files

List modified and untracked files matching the test patterns from Phase 0. The
command must print nothing:

```
git status --porcelain -- <test-file-patterns>
```

If test files changed, move those changes to Phase 5.

Do not commit yet; Phase 4 verifies fix isolation first.

## Phase 4: Verify Fix Isolation

Prove the fix, not an unrelated change, resolved the test.

1. Stash the fix: `git stash -u`
2. Run the xfail test; it must xfail again.
3. Restore the fix: `git stash pop`
4. Run the xfail test; it must XPASS again.

### Gate 4: stash round-trip confirmation

If the test does not return to xfail with the fix stashed, something else
resolved it. Check for a stale build cache, an unrelated working-tree change, or
a dependency update.

5. Commit the fix with the root cause in the message.

## Phase 5: Remove xfail Marker

Convert the xfail test to a regression test. Zero source changes in this commit.

1. Remove the expected-failure marker.
2. Rewrite test comments to describe a regression test, not a bug report.
3. Run the test; it must pass.
4. Run the full suite for the affected file or module.
5. Run all quality gates.

### Gate 5: zero-diff on source files

List modified and untracked files outside the test patterns. The command must
print nothing:

```
git status --porcelain -- . ':!<test-file-patterns>'
```

If source files changed, move them to a separate commit.

6. Commit.

## Phase 6: Final Verification

1. Run the complete test suite and all quality gates.
2. Confirm three commits with correct separation: test only (xfail), source
   only (fix), test only (xfail removal).

### Gate 6: full suite green

If any test fails, check whether the fix introduced a regression. Apply a
minimal fix and re-run from Phase 3.

## Recovery

- Phase 2 fails (the test fails, but not because of the bug): delete the test
  and return to Phase 1.
- Phase 3 fails (the test still xfails after the fix): revert the fix,
  re-examine whether the test exercises the code path you fixed, and redo the
  root cause analysis.
- Phase 4 fails (the test does not return to xfail with the fix stashed): find
  the true cause before proceeding.
- After 3 failed attempts at any phase, stop per the recovery rule in the
  gates-and-commits reference.

## CI Integration

When the project has CI, push after each commit to verify the sequence:

- Phase 1 commit: green. The xfail is an expected failure.
- Phase 4 commit: red. `strict=True` makes the XPASS a failure.
- Phase 5 commit: green. The marker is gone and the test passes.

Without CI, the diff gates and stash round-trip give equivalent confidence.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
