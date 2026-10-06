# tdd

TDD bug-fix workflow: reproduce bugs as failing tests, determine root cause,
fix, and verify.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install tdd@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add tdd@skills
```

The skills below are written with Claude Code's leading slash. Codex uses
the same names without it, so `/tdd:…` there is `tdd:…`.

## Components

| Component | Description |
|-----------|-------------|
| `/tdd:fix` | Standard xfail-driven TDD bug-fix loop |
| `/tdd:xfail` | Hermetic xfail workflow with diff gates, mock contamination guards, and CI checkpoints |

## `/tdd:fix` Workflow

1. **Understand**: Parse bug report (symptom, expected behavior, triggers).
2. **Reproduce**: Create an xfail-marked test.
3. **Analyze**: Trace to the root cause.
4. **Fix**: Apply minimal fix; confirm xfail passes.
5. **Verify**: Remove xfail, run quality gates.
6. **Recover**: Retry on failure (up to 3 attempts).

*Produces atomic commits for: xfail test, fix, and xfail removal.*

## `/tdd:xfail` Protocol

A strict TDD variant enforcing proof at each boundary:

1. **Reproduce**: Write strict xfail test.
2. **Verify Reproduction**: Ensure test fails for the right reason (no mock contamination).
3. **Apply Fix**: Edit source code only (xfail now XPASSes).
4. **Verify Isolation**: Stash fix to confirm bug returns, pop to confirm resolution.
5. **Remove xfail**: Edit test file only.
6. **Final Verification**: Ensure full suite passes.

*Enforces separation via `git diff --stat` gates.*

## Cross-Dependency Bugs

For bugs spanning multiple projects:
1. Fix the dependency first.
2. Verify dependency tests pass.
3. Configure local dependency for development.
4. Fix and test in the main project.

## Quality Gates & Frameworks

Adapts dynamically based on `AGENTS.md` / `CLAUDE.md`:
- Discovers test runners, linters, formatters, and type checkers.
- Uses native expected-failure mechanisms (e.g., `pytest.mark.xfail`, `it.failing`, `#[should_panic]`, `t.Skip`).
- Language and framework agnostic.

## Prerequisites

- **git** for atomic commits.
- A supported test framework.
- Quality gate commands defined in conventions.
