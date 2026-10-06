# Adopting the default rule set

## Contents

- Measure first
- Config shapes
- Curating what the defaults surface
- Landing it

An explicit `select` replaces the default set rather than extending it. A
repository with one gets no diagnostics from a newly curated default
set, and stays opted out at every future release. Nothing in the config
records the opt-out, so turn it into an explicit decision.

## Measure first

The blast radius decides whether adoption is a five-minute change or a
project. Measure it without editing anything. Take the default codes from
the binary, which is authoritative for the version in the lockfile. Run
this from any directory, with any Python file as the argument:

```console
$ DEFAULT_CODES=$(ruff check --isolated --show-settings <file.py> | awk '/^linter.rules.enabled/{f=1;next} /^\]/{f=0} f' | grep -oE '\([A-Z]+[0-9]+\)' | tr -d '()' | paste -sd, -)
```

Count findings per rule as configured:

```console
$ ruff check --statistics
```

Count them again with the default codes added:

```console
$ ruff check --statistics --extend-select "$DEFAULT_CODES"
```

The per-rule difference is the cost. Measure every repository in scope
before proposing anything; counts range from zero to hundreds from one
rule.

A local measurement is a lower bound. Rules that depend on the host
filesystem (executable bit, symlinks, case sensitivity, line endings) can
go silent where you measure and fire on the CI runner. Treat a CI failure
on a rule the measurement said would not fire as a platform gap first,
confirm it by reading the rule's implementation for a platform guard, and
say in the report that the measurement under-reported that class.

## Config shapes

Enumerating every default code in `select` freezes the enabled set at
hundreds of config lines that must be regenerated on every release. Use
it only under a change-control regime that requires a frozen rule list.

Expanding `select` to whole linter prefixes is wrong: the defaults take a
subset of each linter, so whole prefixes enable far more than the vendor
recommends. Reject it, and show the measured difference.

Default to leaving `select` unset and using `extend-select` for the
repository's own additions, with `ignore` and `per-file-ignores` for what
the project does not want. The config shrinks to about the length of the
old `select`. The trade-off to state: the enabled set tracks the vendor's
defaults, so a future release can surface findings without a config
change.

Before enumerating, check whether the selector accepts a token for the
default set by name. Read the selector type in the tool's source at the
release tag, not documentation.

## Curating what the defaults surface

Read the code at every site before deciding. Sort each rule's findings
into:

- Real findings: fix them. Typing rules, naive datetime construction,
  mechanical simplifications, and redundant syntax belong here.
- Deliberate idioms: add a per-file ignore scoped to where the idiom
  lives, never repo-wide, with the reason in the config. A rule that fires
  on a docs build script's dynamic execution is lacking context, not
  finding a bug.
- Load-bearing patterns that look redundant: an import aliased to its own
  name is the explicit re-export form, and removing the alias breaks
  downstream consumers under strict type checking with no local test
  failure. Check whether another tool depends on the shape before fixing
  anything that looks merely redundant.
- Vendored code: exclude the tree or scope an ignore to it, matching what
  the repository already does.

A rule that fires broadly with no real findings gets one documented
`ignore` entry, not inline suppressions and not contorted code.

Fixing a line no test exercises turns it into a patch line, and a
patch-coverage gate can go red from a one-token fix. Add a test that pins
the behavior the fix had to preserve.

## Landing it

The config change is one commit, alone, before any fix or ignore. Its
body reports the enabled-rule count before and after. Then one commit per
rule fixed and one per ignore added, each body carrying the rule's
documentation URL. Resolve the slug from the rule's name, not its code:

```console
$ ruff rule <CODE> --output-format json | jq -r .name
```

The URL is `https://docs.astral.sh/ruff/rules/<name>/`.
