# tdd

TDD bug-fix workflow: reproduce bugs as failing tests, determine root cause,
fix, and verify.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install tdd --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

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
removal. It makes three commits and checks that the working tree holds only its own
files before each: test files, then source, then test files.

`/tdd:xfail` adds proof at every boundary: it removes the marker to confirm the
test fails for the bug's reason, then stashes the fix to confirm the bug
returns. Use it when the reproduction needs that proof or the project has CI;
it costs two extra runs and a stash round trip per bug.

Only `/tdd:fix` is slash-only; the model never routes to it, so "fix this
test-first" reaches `xfail` unless you type `/tdd:fix`.

Either skill stops after the committed failing test when that is all you asked
for. Both make three commits per bug and push nothing unless you ask. Both
show a plan and stop for approval; a "go ahead" in the request skips that
stop. A regression found mid-run adds a commit, and the report lists every
commit made.

## Cross-Dependency Bugs

When a bug spans a dependency, the skills ask for the dependency's checkout,
fix it there (never an installed or vendored copy), then point the project at
the local fix with an override that stays uncommitted, and finish there.

## Quality Gates & Frameworks

Adapts dynamically based on `AGENTS.md` / `CLAUDE.md`:
- Discovers test runners, linters, formatters, and type checkers.
- Uses native expected-failure mechanisms (e.g., `pytest.mark.xfail`, `it.failing`, `#[should_panic]`, `t.Skip`).
- Language and framework agnostic.

## Prerequisites

- git, for the commits.
- python3 (3.14 or newer), for the diff-gate script.
- A supported test framework.
- Quality gate commands listed in the project's AGENTS.md or CLAUDE.md.
