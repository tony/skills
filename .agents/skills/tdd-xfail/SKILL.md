---
name: tdd-xfail
description: >-
  Use when fixing a bug with a failing test first or a regression test, and
  proving it fails for the right reason (strict xfail).
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "Agent"]
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

The plan always opens with four full sentences, no bold labels and no
noun-colon leads (never "Bug summary: ..."): the first states the symptom,
expected behavior, trigger, and affected component; the second names the test
file, fixtures, and xfail mechanism; the third says whether mocks are needed,
what real behavior they replace, and how you will verify the failure is genuine
and not mock-induced; the fourth names the phases that run (all, or only the
failing test) and, when the bug spans a dependency, the dependency checkout.

Add a further sentence only when it differs from this workflow's defaults (the
project's own gates, test-only and source-only patterns, marker-removal run and
stash round trip): a mechanism other than the obvious one, test patterns beyond
the usual, quality-gate commands that differ from a plain run, or a way to
prove the failure that differs from the marker-removed run and the stash round
trip. A pure function with one test needs a handful of lines.

Short plan for a pure function:

```text
is_business_day(5) returns True for Saturday, but Saturday is not a business
day; the function is in bizdays.py and the trigger is any weekday value of 5.
The xfail test goes in test_bizdays.py with @unittest.expectedFailure and no
fixtures. No mocks are involved, so a failure there is the real bug. All
phases run, and no dependency is involved.
```

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

Report per the final-report and stopped-run shapes in
`references/gates-and-commits.md`. Name commits by purpose (xfail test,
fix, xfail removal), never by phase or number. Name no local paths.

## Phase 0: Discover Conventions

1. Create a todo list tracking all phases.
2. Confirm the repository: `git rev-parse --show-toplevel` must be the
   project the bug lives in. If there is none, or the root is the home
   directory (`(cd ~ && pwd -P)`, since home may be a symlink) or contains it (a dotfile repository would sweep home into Phase 4's stash),
   stop and tell the user.
3. Confirm a clean tree: `git status --porcelain` must print nothing. If it
   prints changes, ask the user to commit or stash them first. Without an
   interactive question tool, stop; never stash or commit unrelated work.
4. Read the project's AGENTS.md / CLAUDE.md for test framework and conventions,
   quality gate commands, and commit format.
5. Detect the framework and select the mechanism from the xfail-mechanisms
   reference.
6. Derive the test-file patterns `diff_gate.py` takes from the project's own
   layout and naming (see "Diff gates" in the reference).
7. Use Explore agents (or read the files directly where none exist) to find the
   relevant source and existing tests.
8. When the bug spans a dependency, follow the cross-dependency steps in the
   gates-and-commits reference, running this protocol in the dependency first.

## Phase 1: Reproduce with an xfail test

Create an implemented test with the selected expected-failure annotation or
skip. Verify reproduction with the annotation removed in Phase 2.

The test must exercise real code paths. When mocking is unavoidable (network,
filesystem, external services), the failure must match the bug's actual
symptom (exception type, message, or wrong-value pattern). If the mock causes
the failure, discard the test and start over.

1. Study existing test patterns in the target file.
2. Write a test with a descriptive name, existing fixtures, the selected
   annotation, and an assertion of the correct behavior (not the buggy one).
3. Run it. Strict mode must accept its expected failure; skip mode must report
   it skipped. Check the result against the mechanism reference.
4. Run the full test file.
5. Run all quality gates.

### Gate 1: xfail confirmation

The selected test must produce its mode's annotated broken-state result.
An unexpected success or ordinary pass does not reproduce the bug. A skip
confirms only the annotation; Phase 2 must establish the genuine failure.
Stop on setup failures or exceptions that do not match the bug's symptom.

Then commit test file changes only; `diff_gate.py` in `test-only` mode (see
the reference's "Diff gates" section) must print nothing.

## Phase 2: Verify Reproduction Is Genuine

Prove the test fails because of the bug, not the test setup.

1. Temporarily remove the expected-failure annotation or skip.
2. Run the test; it must fail.
3. Check that the error matches the bug's symptom, the exception type is the
   expected one, and no misconfigured mock could produce the same failure.
4. Restore the annotation before continuing.

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
2. Run steps 1 to 3 of "Fix commit" in the gates-and-commits reference.
   Do not commit yet; Phase 4 verifies fix isolation first.

### Gate 3: zero-diff on test files

The `source-only` diff gate must print nothing. If test files changed, move
those changes to Phase 5.

## Phase 4: Verify Fix Isolation

Prove the fix, not an unrelated change, resolved the test. Use the "Stash
round trip" commands in the gates-and-commits reference.

1. Stash the fix with `push` and keep the SHA it prints. No SHA means nothing
   was stashed: treat the missing fix as a Phase 3 failure.
2. Verify the broken state in the mechanism reference: the annotated test must
   produce the selected mode's result. Temporarily remove the annotation and
   confirm the same assertion fails for the bug's symptom, then restore the
   annotation before restoring the fix.
3. Delete the untracked caches that step 2 created, then `restore` the SHA.
   On a failure, stop and report the SHA.
4. List the stashes. The list must not hold your SHA; report any stash of
   yours that remains.
5. Repeat the mechanism reference's fixed-state check with the fix restored.

### Gate 4: stash round-trip confirmation

The unannotated assertion must fail for the original symptom with the fix
stashed, and pass with the fix restored. Both annotated results must also
match the selected mode. If any check differs, investigate stale build caches,
unrelated changes, or dependency updates; a skip cannot prove isolation.

Repeat the source-only diff gate after restoring the annotation, then commit
the fix with the root cause in the message.

## Phase 5: Remove xfail Marker

Convert the xfail test to a regression test. Zero source changes in this commit.

1. Remove the expected-failure annotation or skip.
2. Rewrite test comments to describe a regression test, not a bug report.
3. Run the test; it must pass.
4. Run the full suite for the affected file or module.
5. Run all quality gates.

### Gate 5: zero-diff on source files

Run `diff_gate.py` in `test-only` mode (see the reference's "Diff gates"
section). It must print nothing.

If source files changed, move them to a separate commit and list it in the
report.

Then commit.

## Phase 6: Final Verification

1. Run the complete test suite and all quality gates.
2. Confirm three commits with correct separation: test only (xfail), source
   only (fix), test only (xfail removal).

### Gate 6: full suite green

If any test fails, check whether the fix introduced a regression. Add a
minimal fix as a new commit, list it in the report, and re-run the suite;
never rewrite the three commits.

## Recovery

When the unannotated assertion still fails after the fix, re-examine whether
the test exercises the code path you fixed and redo the root cause analysis.
An annotated result outside the mechanism reference's fixed-state outcome
also requires investigation; strict unexpected success is the expected result.
The 3-attempt stop rule is in the gates-and-commits reference.

## CI Integration

Push only when the user asks; without an answer, push nothing. When the user
opts in and the project has CI, verify the sequence against the selected mode:

- Test commit: green, with an accepted expected failure or a skip.
- Fix commit: strict mode is red specifically for unexpected success; skip
  mode stays green with the test skipped. The skip is not fix evidence.
- Annotation-removal commit: green, with the regression assertion executed.

Report the CI results observed. When CI is absent or unobserved, report only
the local checks; do not infer CI success from the diff or isolation gates.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
