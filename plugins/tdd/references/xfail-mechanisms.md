# Expected-failure mechanisms

Pick the mechanism that matches the project's test framework. Prefer one that
fails the suite when the test starts passing (strict).

- pytest: `@pytest.mark.xfail(strict=True, reason="...")` (or `xfail_strict = true` in the project's pytest config); add `raises=` when
  the exception type is known. Fixed bug: XPASS, reported as `FAILED` with
  `[XPASS(strict)]`.
- Jest: `it.failing('...')`. Fixed bug: the test passes, so the suite fails.
- Vitest: `it.fails('...')`. Fixed bug: same as Jest.
- Rust: `#[should_panic(expected = "...")]`. Without `expected`, any panic
  passes, so always set it. Fixed bug: no panic, so the test fails.
- Python unittest: `@unittest.expectedFailure`. Fixed bug: reported as an
  unexpected success, which fails the run.
- Go and any framework without a strict form: `t.Skip("known bug: ...")` or the
  framework's skip. A skipped test never runs, so it cannot XPASS. Verify by
  removing the skip, running the test, and restoring the skip.
- `.todo`, `#[ignore]`, and pending markers do not run the test. Use them only
  as a skip.

Strictness varies by framework version. Confirm the chosen mechanism with a
throwaway run: a passing test under the marker must fail the suite.

Reading the mechanism: a strict mechanism turns "bug fixed" into a failing
result, so run only the non-test gates at the fix commit. A skip-based
mechanism gives no such signal; run the unskipped test directly.
