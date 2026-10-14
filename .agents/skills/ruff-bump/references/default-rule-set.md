# Adopting the default rule set

## Contents

- Measure first
- Config shapes
- Curating what the defaults surface
- Landing it

An explicit `select` replaces the default set, so the repository takes a rule
added to the defaults only where its own prefixes already cover it. Nothing in
the config records the opt-out; make it an explicit decision.

## Measure first

Measure the blast radius without editing the repository. Resolve
`./default_delta.py` against this file's directory (the path it was
read from) and write that absolute path literally in the command; shell
variables do not persist between Bash calls. Never show that path in the
reply. Pass `--cwd` with the repository or worktree measured.

The script counts findings per rule as configured, then again under the
recommended shape: a scratch copy of the repository in which every `select`
becomes `extend-select` (merged into an existing `extend-select`), so the
vendor defaults apply and the repository's `ignore` and `per-file-ignores`
stay in force. It prints `code`, configured, proposed, and delta,
tab-separated, ending in a `total` line, and names the files it rewrote on
stderr. It exits 2 for a configuration it cannot rewrite (an inline-table
`select`, or an `extend` file outside the repository): report the delta as
unmeasured with that reason. It disables fix modes, clears
`RUFF_OUTPUT_FILE`, and measures with `--no-cache`; the runner must itself
leave the checkout unchanged.

In an audit, pass the ephemeral runner (the skill's runner rule):

```console
$ python3 ./default_delta.py \
    --cwd <repo> \
    -- uv run --no-sync --isolated --with ruff==<target> ruff
```

Otherwise pass the project's own runner, so the binary is the version the
lockfile resolves; confirm it with `<runner> --version`:

```console
$ python3 ./default_delta.py \
    --cwd <worktree> \
    -- uv run ruff
```

The per-rule difference is the cost; measure every repository in scope before
proposing anything. A local measurement can under-report rules that depend on
the host filesystem (executable bit, symlinks, case, line endings), which can fire only
on the CI runner. When a CI failure fits that class, read the rule's
implementation for a platform guard to confirm it, and say the measurement
under-reported it.

## Config shapes

Default to leaving `select` unset and using `extend-select` for the
repository's own additions (the shape the script measures), with `ignore` and `per-file-ignores` for what the
project does not want. The trade-off to state: the enabled set tracks the
vendor's defaults, so a future release can surface findings without a config
change.

Enumerating every default code in `select` freezes the set as a long list to
regenerate each release; use it only under change control that
requires a frozen list. Never expand `select` to whole linter prefixes: the
defaults take a subset of each linter, so prefixes enable far more than the
vendor recommends. Show the measured difference.

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

Write the config change with `default_delta.py --cwd <worktree> --apply`, so
the committed shape is the measured one; it lands alone, with the
enabled-rule count before and after in its body. Rule and ignore commits
follow as the skill's one-rule-one-commit step describes. The documentation
URL is `https://docs.astral.sh/ruff/rules/<name>/`; that site tracks the latest
release, so read `<runner> rule <CODE>` for the pinned version's text.
Resolve the slug from the rule's name, not its code:

```console
$ uv run ruff rule <CODE> --output-format json | jq -r .name
```
