# Python

How this repository writes Python: the scripts plugins ship, the modules
`shared/` vendors into them, and the tooling under `scripts/`. Docstrings and
comments follow [WRITING.md](WRITING.md). The commands that check all of it
are the gates in [AGENTS.md](../AGENTS.md#quality-gates).

## Two floors

Plugin scripts (`plugins/*/scripts/`, `plugins/*/evals/`) and `shared/*.py`
run under the user's own `python3`, whose version this repository does not
control:

- They require Python 3.14 and import only the standard library.
- They start with `#!/usr/bin/env python3`, never a uv shebang or a PEP 723
  header.
- ruff checks them at `py314` (`per-file-target-version` in
  `pyproject.toml`), ty with `--python-version 3.14`, and CI runs their tests
  on 3.14 with nothing installed but pytest.
- A README, skill, or reference that names a Python floor names 3.14.

Repository tooling under `scripts/` runs through uv:

- It requires Python 3.15 and may import the dev group's packages.
- Each script declares its `requires-python` and dependencies in a PEP 723
  header under `#!/usr/bin/env -S uv run --script`.

## Idioms

Write for the floor, not below it:

- Drop `from __future__ import annotations`; Python 3.14 evaluates
  annotations lazily (PEP 649, PEP 749). An import only annotations need goes
  under `if TYPE_CHECKING:`.
- Write `except OSError, ValueError:` without parentheses (PEP 758). A clause
  with `as` keeps them.
- Declare aliases with `type` and generics with type parameters (PEP 695):
  `type Row = tuple[str, int]`, `def gather[T](...)`. typer rejects a `type`
  alias, so a type typer reads stays a plain assignment.
- Mark a method that overrides its base class's with `@typing.override`.
- Defer a module most commands never use with `lazy import` (PEP 810), in
  `scripts/` only: the syntax is new in 3.15, so a plugin cannot parse it.
- Use `tomllib`, `datetime.UTC`, and `itertools.pairwise` directly, with no
  fallback for an older Python.
- Choose each `zip()`'s `strict=` from that call's length invariant.

## Records

A value with several fields that crosses a function boundary is a
`NamedTuple` or a dataclass, not a bare tuple. `heading.level` reads where
`h[1]` does not, and ty checks the name.

## Concurrency

Use asyncio only where a script waits on two or more independent
subprocesses or network calls. Local git loops, ordered steps, and anything
that mutates stay synchronous.

- Run the waits in an `asyncio.TaskGroup`, capped by an `asyncio.Semaphore`.
- Start a subprocess with `asyncio.create_subprocess_exec`, never through a
  shell, and bound it with `asyncio.timeout`. A child that starts processes
  of its own gets `start_new_session=True`, so a timeout kills its group.
- Hand a blocking call, such as `urllib` or a synchronous helper, to
  `asyncio.to_thread`.
- Return results in input order, not completion order.
- Raise a failed task's own exception, not the `ExceptionGroup` around it, so
  callers' `except` clauses and the script's exit status stay the same.
- Keep the functions a CLI calls synchronous; one `asyncio.run` inside them
  drives the concurrent part.

## Command-line contract

Skills parse a script's arguments, stdout, and exit status, so those three
are its API:

- Change one only together with every skill and reference that calls it.
- Parse arguments with `argparse` in plugins and typer in `scripts/`.
- Keep logic in functions that take and return values. `main(argv)` parses,
  calls them, prints, and returns the exit status, which the
  `if __name__ == "__main__":` block exits with, so tests call `main`
  directly.
- Write diagnostics to stderr; stdout carries what the skill parses.

## Tests

- A script `name.py` keeps its tests in `test_name.py` beside it. pytest also
  runs every docstring example (`--doctest-modules`).
- Plugin tests import only the standard library and pytest, so they pass on
  3.14 with nothing else installed.
- Mark a test that builds a real Git repository or drives a CLI through
  subprocesses with `@pytest.mark.integration`; the mid loop skips it.
- A test of concurrent code proves the overlap, the cap, and the result
  order, not only the result.
- A vendored module's copies share a basename, so `pyproject.toml` keeps
  pytest from collecting them; the owning plugin's test runs the doctests
  through `importlib`.

## Types

- Annotate every signature; ruff's `ANN` rules enforce it.
- ty treats every rule as an error. Narrow a regex match, a JSON payload, or
  an optional value before use instead of casting it.
- A `# ty: ignore[rule]` names its rule and marks code ty cannot follow, never
  code that is wrong. Write no `# pyright:` or `# type: ignore` comments.

## Files

- Set a new script's executable bit before its first commit. CI's ruff fails
  `EXE001` on a shebang in a file Git records as non-executable, and a local
  run may not catch it; `git ls-files -s` shows `100755` once it is set.
- A module two plugins need lives once in `shared/`, per
  [Shared Files](../AGENTS.md#shared-files). Edit that copy, never a
  vendored one.
