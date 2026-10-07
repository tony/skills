# Adopting the default rule set

## Contents

- Measure first
- Config shapes
- Curating what the defaults surface
- Landing it

An explicit `select` replaces the default set, so a repository with one gets
no diagnostics from a newly curated default set and stays opted out at every
future release. Nothing in the config records the opt-out; make it an explicit
decision.

## Measure first

Measure the blast radius without editing anything. Run the bundled script
from the repository to measure. Resolve `references/default_delta.py` against
this file's directory (the path it was read from) and write that absolute
path literally in the command; shell variables do not persist between Bash
calls. Never show that path in the reply.

The script counts findings per rule as configured, counts them again with the
binary's own default codes added, and prints `code`, configured, with-defaults,
and delta, tab-separated, ending in a `total` line. It reads the default codes
from `--isolated --show-settings` and exits 2 when that output lists none, so
a format change in ruff fails loudly. It passes `--no-cache`, so it writes
nothing to the repository.

In an audit, pass the ephemeral runner (`uv run` would create `.venv` and a
lockfile):

```console
$ python3 references/default_delta.py -- \
    uv run --no-sync --isolated --with ruff==<target> ruff
```

Otherwise pass the project's own runner, so the binary is the version the
lockfile resolves; confirm it with `<runner> --version`:

```console
$ python3 references/default_delta.py -- uv run ruff
```

The per-rule difference is the cost; measure every repository in scope before
proposing anything. A local measurement is a lower bound: rules that depend on
the host filesystem (executable bit, symlinks, case, line endings) can fire only
on the CI runner. Treat such a CI failure as a platform gap, confirm it by
reading the rule's implementation for a platform guard, and say the measurement
under-reported that class.

## Config shapes

Default to leaving `select` unset and using `extend-select` for the
repository's own additions, with `ignore` and `per-file-ignores` for what the
project does not want. The trade-off to state: the enabled set tracks the
vendor's defaults, so a future release can surface findings without a config
change.

Enumerating every default code in `select` freezes the set at hundreds of
config lines to regenerate each release; use it only under change control that
requires a frozen list. Never expand `select` to whole linter prefixes: the
defaults take a subset of each linter, so prefixes enable far more than the
vendor recommends. Show the measured difference. Before enumerating, try a
default-set token on a scratch file (`<runner> ruff check --isolated --select <token> <file.py>`)
and read the error, which lists what the selector accepts.

## Curating what the defaults surface

Read the code at every site, then sort each rule's findings:

- Real findings (typing rules, naive datetimes, mechanical simplifications,
  redundant syntax): fix them.
- Deliberate idioms: a per-file ignore scoped to where the idiom lives, never
  repo-wide, with the reason in the config.
- Load-bearing patterns that look redundant: an import aliased to its own name
  is the explicit re-export form, and removing the alias breaks downstream
  strict type checking with no local test failure. Check whether another tool
  depends on the shape first.
- Vendored code: exclude the tree or scope an ignore to it, as the repository
  already does.

A rule that fires broadly with no real findings gets one documented `ignore`
entry, not inline suppressions. Fixing a line no test exercises can turn a
patch-coverage gate red from a one-token fix; add a test that pins the behavior
the fix preserves.

## Landing it

The config change is one commit, alone, before any fix or ignore, with the
enabled-rule count before and after in its body. Then one commit per rule fixed
and one per ignore added, each body carrying the rule's documentation URL,
`https://docs.astral.sh/ruff/rules/<name>/`; that site tracks the latest
release, so read `<runner> ruff rule <CODE>` for the pinned version's text.
Resolve the slug from the rule's name, not its code:

```console
$ uv run ruff rule <CODE> --output-format json | jq -r .name
```
