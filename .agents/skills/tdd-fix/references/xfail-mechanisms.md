# Expected-failure mechanisms

Identify the project's framework, version, and configured runner. Prefer a
mechanism that fails the suite when the test starts passing (strict). Verify
that behavior with a throwaway passing test under the annotation; do not
change the project's runner or configuration to obtain it without approval.

- pytest: `@pytest.mark.xfail(strict=True, reason="...")`; add `raises=` when
  the exception type is known. Fixed bug: `[XPASS(strict)]` fails the run.
  Keep execution enabled; `run=False` cannot verify the assertion.
- Jest: `it.failing('...', body)` requires the configured `jest-circus` runner.
  If unavailable, use the skip mode below. Fixed bug: the body passes, so the
  runner fails the test for unexpected success.
- Vitest: `it.fails('...')`. Fixed bug: same as Jest.
- Rust: `#[should_panic(expected = "...")]`. Without `expected`, any panic
  passes, so set a symptom-specific substring. An assertion of the correct
  return value can reproduce a wrong-value bug by panicking. Fixed bug: that
  assertion passes without a panic, so the runner fails the test.
- Python unittest: `@unittest.expectedFailure`. Fixed bug: reported as an
  unexpected success, which fails the run.
- RSpec: `pending "reason"` inside an implemented example executes its body.
  Fixed bug: the example passes, so RSpec fails it as `FIXED`. `skip`/`xit`
  do not execute the body; a placeholder without a body cannot reproduce a bug.
- Go, JUnit, and other runners without a strict form: use the framework's
  skip on an implemented test, such as `t.Skip("known bug: ...")`, `@Disabled`,
  or `@Ignore`. Rust `#[ignore]` also skips execution. A `.todo` placeholder
  must become an implemented assertion before it can enter this workflow.

## Outcome checks

Keep the same test and assertion across these states:

| Implementation and annotation | Strict mode | Skip mode |
|---|---|---|
| Broken, annotated | Expected failure accepted by the runner | Test skipped; no reproduction proof |
| Broken, annotation removed | Intended assertion fails for the bug's symptom | Intended assertion fails for the bug's symptom |
| Fixed, annotated | Runner fails the test for unexpected success | Test skipped; no fix proof |
| Fixed, annotation removed | Intended assertion passes | Intended assertion passes |

Every run must select the intended test and report its result. For execution
checks, confirm the intended assertion was reached. An empty selection, skip,
setup/import failure, or unrelated exception cannot establish reproduction or
a fix. Expected-failure mechanisms can accept the wrong failure: inspect the
unannotated failure's location and symptom, even when `raises=` is set.

For the fixed-state check, temporarily remove the annotation and verify the
assertion passes, then restore the annotation and verify the mode's result.
A strict run must fail specifically for unexpected success, not another error.
Restore the original annotation before any source-only diff gate or commit;
remove it permanently only in the final test-only commit.
