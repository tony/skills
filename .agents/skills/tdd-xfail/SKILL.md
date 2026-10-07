---
name: tdd-xfail
description: >-
  Use when fixing a bug through strict xfail reproduction and needing proof
  that the test fails for the intended reason.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Task"]
metadata:
  argument-hint: "Paste or describe the bug to reproduce and fix with strict xfail guards"
  source: "plugins/tdd/skills/xfail/SKILL.md"
---

# Strict xfail TDD Workflow

Fix a bug with strict reproduction guards. Each phase has a gate that passes
before the next begins. The result is proof that the test fails for the right
reason, in three commits: test only, source only, test only.

Initial bug report: $ARGUMENTS

Shared rules: [xfail mechanisms](references/xfail-mechanisms.md) and
[gates, commits, recovery](references/gates-and-commits.md). Write
commit messages per `references/prose-rules.md` and the reference's
"Commit messages" section.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`;
in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is
unavailable, present the plan as text.

The plan covers these points, written as plain bullets without bold labels:

1. Bug summary: symptom, expected behavior, trigger conditions, affected component.
2. Test strategy: test file, fixtures, xfail mechanism.
3. Mock assessment: whether mocks are required, what real behavior they replace, and how you will verify the failure is genuine (not mock-induced).
4. Framework detection: which mechanism applies (xfail-mechanisms reference).
5. Diff-gate file sets: the test-file pathspecs and what counts as source.
6. Quality gates: commands from the project's AGENTS.md/CLAUDE.md.
7. Reproduction proof: how you will show the test fails for the bug's reason and
   not the setup (the failure message at the marker-removed run, the stash round-trip).

Cap the plan to what differs from this workflow's defaults: a pure function
with one test needs a handful of lines, not eight steps.

Present the plan and wait for approval per the approval rule in
[gates, commits, recovery](references/gates-and-commits.md). Exit plan
mode once approved; Phase 1 commits and Phase 4 stashes, which plan mode
blocks.

When the user asked only for the failing test, the plan covers Phases 0 to 2
and the run stops after Gate 2 with the test committed. Never start Phase 3
unasked.

The plan needs no repository: when a Phase 0 gate (dirty tree, wrong
repository) stops the run, the stopped report still states the plan, asks the
user to approve it, and says what to fix in the repository.

## Output shape

Report per the final-report, stopped-run, and plan-awaiting-approval shapes in
`references/gates-and-commits.md`. Name commits by purpose (xfail test,
fix, xfail removal), never by phase or number. Name no local paths.

## Phase 0: Discover Conventions

1. Create a todo list tracking all phases.
2. Confirm the repository: `git rev-parse --show-toplevel` must be the
   project the bug lives in. If there is none, or the root is `$HOME` or
   contains it (a dotfile repository would sweep home into Phase 4's stash),
   stop and tell the user.
3. Confirm a clean tree: `git status --porcelain` must print nothing. If it
   prints changes, ask the user to commit or stash them first. Without an
   interactive question tool, stop; never stash or commit unrelated work.
4. Read the project's AGENTS.md / CLAUDE.md for test framework and conventions,
   quality gate commands, and commit format.
5. Detect the framework and select the mechanism from the xfail-mechanisms
   reference.
6. Derive the test-file patterns the diff gates use from the project's own
   layout and naming. Write each as its own `:(glob)` pathspec (see "Diff gates" in the
   reference).
7. Use Explore agents to find the relevant source and existing tests.
8. When the bug spans a dependency, follow the cross-dependency steps in the
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

## Phase 1: Reproduce with an xfail test

Create a test that reproduces the bug, marked expected-to-fail.

The test must exercise real code paths. When mocking is unavoidable (network,
filesystem, external services), the failure must match the bug's actual
symptom (exception type, message, or wrong-value pattern). If the mock causes
the failure, discard the test and start over.

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

Then commit test file changes only; the test-only-commit check in the
reference's "Diff gates" section must print nothing.

## Phase 2: Verify Reproduction Is Genuine

Prove the test fails because of the bug, not the test setup.

1. Temporarily remove the xfail marker.
2. Run the test; it must fail.
3. Check that the error matches the bug's symptom, the exception type is the
   expected one, and no misconfigured mock could produce the same failure.
4. Restore the marker.

### Gate 2: genuine-failure confirmation

If the failure does not match the symptom, the reproduction is contaminated.
Rewrite the test in place without tweaking the mock setup until it looks
right, rerun Phase 1, and replace the Phase 1 commit with
`git commit --amend`. When that commit was already pushed, add a new commit
instead of amending. This phase otherwise produces no commit.

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

Run the source-only-commit check from the reference's "Diff gates" section. It must
print nothing.

If test files changed, move those changes to Phase 5.

Do not commit yet; Phase 4 verifies fix isolation first.

## Phase 4: Verify Fix Isolation

Prove the fix, not an unrelated change, resolved the test.

1. Print the current stash ref (`none` when there is no stash):

   ```console
   $ git rev-parse -q --verify refs/stash || echo none
   ```
2. Stash the fix:

   ```console
   $ git stash push --include-untracked
   ```
3. Print the stash ref again. A changed value means the stash was created.
   An unchanged value means nothing was stashed: do not pop, and treat the
   missing fix as a Phase 3 failure.
4. Run the xfail test; it must xfail again.
5. Restore the fix only when step 3 showed a new stash:

   ```console
   $ git stash pop
   ```
   On a pop conflict, stop. Keep the stash, report the SHA
   printed by `git rev-parse refs/stash`, and never run `git stash drop`.
6. Run the xfail test; it must XPASS again.

### Gate 4: stash round-trip confirmation

If the test does not return to xfail with the fix stashed, something else
resolved it. Check for a stale build cache, an unrelated working-tree change, or
a dependency update.

Then commit the fix with the root cause in the message.

## Phase 5: Remove xfail Marker

Convert the xfail test to a regression test. Zero source changes in this commit.

1. Remove the expected-failure marker.
2. Rewrite test comments to describe a regression test, not a bug report.
3. Run the test; it must pass.
4. Run the full suite for the affected file or module.
5. Run all quality gates.

### Gate 5: zero-diff on source files

Run the test-only-commit check from the reference's "Diff gates" section. It
must print nothing.

If source files changed, move them to a separate commit.

Then commit.

## Phase 6: Final Verification

1. Run the complete test suite and all quality gates.
2. Confirm three commits with correct separation: test only (xfail), source
   only (fix), test only (xfail removal).

### Gate 6: full suite green

If any test fails, check whether the fix introduced a regression. Add a
minimal fix as a new commit and re-run the suite; never rewrite the three
commits.

## Recovery

When the test still xfails after the fix, revert the fix, re-examine whether
the test exercises the code path you fixed, and redo the root cause analysis.
The 3-attempt stop rule is in the gates-and-commits reference.

## CI Integration

Push only when the user asks. The fix commit is red on purpose (strict XPASS),
so never push it unasked; without an answer, push nothing. When the user
opts in and the project has CI, push after each commit to verify the sequence:

- xfail test commit: green. The xfail is an expected failure.
- Fix commit: red. A strict mechanism makes the XPASS a failure.
- xfail removal commit: green. The marker is gone and the test passes.

Without CI, the diff gates and stash round-trip give equivalent confidence.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
