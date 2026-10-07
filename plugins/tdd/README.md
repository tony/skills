# tdd

TDD bug-fix workflow: reproduce bugs as failing tests, determine root cause,
fix, and verify.

## Installation

In Claude Code, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install tdd@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add tdd@skills
```

Claude Code uses a leading slash (`/tdd:…`). Codex omits it (`tdd:…`).

## Components

`/tdd:fix` is the standard loop: xfail test, root-cause analysis, fix, xfail
removal. It makes three commits and checks that each stages only its own files: test
files, then source, then test files.

`/tdd:xfail` adds proof at every boundary: it removes the marker to confirm the
test fails for the bug's reason, then stashes the fix to confirm the bug
returns. Use it when the reproduction needs that proof or the project has CI;
it costs two extra runs and a stash round trip per bug.

Only `/tdd:fix` is slash-only; the model never routes to it, so "fix this
test-first" reaches `xfail` unless you type `/tdd:fix`.

Either skill stops after the committed failing test when that is all you asked
for. Both make three commits per bug and push nothing unless you ask.

## Cross-Dependency Bugs

When a bug spans a dependency, the skills fix the dependency first, then point
the project at the local fix and finish there.

## Quality Gates & Frameworks

Adapts dynamically based on `AGENTS.md` / `CLAUDE.md`:
- Discovers test runners, linters, formatters, and type checkers.
- Uses native expected-failure mechanisms (e.g., `pytest.mark.xfail`, `it.failing`, `#[should_panic]`, `t.Skip`).
- Language and framework agnostic.

## Prerequisites

- git, for the commits.
- A supported test framework.
- Quality gate commands listed in the project's AGENTS.md or CLAUDE.md.
