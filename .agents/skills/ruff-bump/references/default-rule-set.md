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

Measure the blast radius without editing anything, through the project's own
runner (for example `uv run ruff`) so the binary is the version the lockfile
resolves; confirm with `<runner> ruff --version`.

Count findings per rule as configured:

```console
$ uv run ruff check --statistics
```

Count them again with the binary's default codes added. One command computes
and uses them, because shell variables do not survive between Bash calls; use
any Python file as `<file.py>`:

```bash
uv run ruff check --statistics \
  --extend-select "$(uv run ruff check --isolated --show-settings <file.py> \
    | awk '/^linter.rules.enabled/{f=1;next} /^\]/{f=0} f' \
    | grep -oE '\([A-Z]+[0-9]+\)' \
    | tr -d '()' \
    | paste -sd, -)"
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
vendor recommends. Show the measured difference. Before enumerating, check
whether the selector accepts a token for the default set by name, reading the
selector type in the tool's source at the release tag.

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
`https://docs.astral.sh/ruff/rules/<name>/`. Resolve the slug from the rule's
name, not its code:

```console
$ uv run ruff rule <CODE> --output-format json | jq -r .name
```
