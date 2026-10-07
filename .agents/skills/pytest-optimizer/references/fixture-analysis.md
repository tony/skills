# Fixture analysis

Recipes for slowest fixtures, unused fixtures, and proper scope. Backs
heuristics `H03`, `H08`–`H13`, `H16`, `H21`, `H41`–`H43`.

## Contents

- Scope and caching model
- Slowest fixtures and root cause
- Mis-scoped fixture
- Unused fixtures
- Duplicate fixtures
- Autouse audit
- Shared mutable state

## Scope and caching model

A fixture's `scope` decides how often its setup runs and how long its value is
cached:

| Scope | Setup runs | Value cached for |
|-------|-----------|------------------|
| `function` (default) | once per test that requests it | one test |
| `class` | once per test class | the class |
| `module` | once per test module | the module |
| `package` | once per package | the package |
| `session` | once per test run | the whole run |

The core mis-scope smell: an **expensive `function`-scoped fixture whose value
is shared and not mutated** re-runs N times when one setup would do. Widening
the scope is often the highest-impact, lowest-risk speedup, *if* the value is
read-only across tests (otherwise see "Shared mutable state").

## Slowest fixtures and root cause

The `--durations` table cannot name the costly fixture (a `setup` row is the
whole chain). `--setup-show` runs the suite and prints each fixture as it is set
up and torn down, with a scope letter (`F`/`C`/`M`/`P`/`S`):

```console
$ pytest --setup-show -q
```

`--setup-plan` shows the same plan **without running tests**, which suits
counting setups:

```console
$ pytest --setup-plan
```

For true per-fixture timing, generate the opt-in plugin
(`templates/pytest_optimizer_plugin.py`), which records each fixture's own setup
seconds.

## Mis-scoped fixture (H10/H13)

```console
$ pytest --setup-plan | rg 'SETUP +F '
```

Count `SETUP` rows per `F` (function) fixture. A count > 1 on a fixture whose body
does real work (network/db/docker/subprocess/sleep/build) is a scope candidate:

1. Confirm the value is **not mutated** by tests (read the body and consumers).
2. Raise `scope` to `module`/`session` (or `class`/`package`).
3. Verify the `SETUP` count drops with `--setup-plan` again.
4. Run the order-independence gate before trusting it.

For indirect/parametrized fixtures that pay setup once per param per test (H13),
move the param to a higher-scoped fixture or cache the per-param resource at
module/session scope and select from it.

## Unused fixtures (H08/H09/H41)

Diff **defined** fixtures against **used** fixtures:

```console
$ pytest --fixtures -v 2>/dev/null | rg -v 'site-packages|_pytest'
```

```console
$ pytest -o addopts='' --fixtures-per-test 2>/dev/null
```

The first command lists project-defined fixtures; the second lists what each test
actually requests. **Gotcha:** if the project's `addopts` enables
`--doctest-modules`, `--fixtures-per-test` raises `INTERNALERROR` (a `DoctestItem`
has no `.function`) and `2>/dev/null` does not hide it — so override addopts with
`-o addopts=''` as above. Fixture introspection does not run the suite, so
clearing addopts here is safe.

A fixture in the first set but not the second, and not `autouse`, is a
candidate. Cross-check with the `pytest-deadfixtures` plugin when installed. It has no
executable of its own; it adds `--dead-fixtures` to pytest, so run it in the
project environment. With `uv`:

```console
$ uv run --with pytest-deadfixtures \
    pytest \
    --dead-fixtures
```

With another runner, install the plugin into that environment first. Never run it
through a bare `uvx`: it lacks the project's dependencies, so collection fails.

**Mandatory guard (H09).** Static analysis cannot see dynamic requests. Before
deleting, search for dynamic references:

```console
$ rg "getfixturevalue\([\"']<name>" tests/ ; rg "\b<name>\b" tests/
```

A `getfixturevalue('name')` call or a string-based mark reference keeps the
fixture alive. When any exists, **keep the fixture** and have a human confirm.

A parameter a test or fixture never uses (H41) is a dead dependency (drop it)
or an intended side-effect fixture (make it `autouse`/`usefixtures` and document
why).

## Duplicate fixtures (H11/H42)

With the plugin installed as above (`--dup-fixtures` runs the tests, unlike
`--dead-fixtures`, and skips fixtures without a truthy return value):

```console
$ uv run --with pytest-deadfixtures \
    pytest \
    --dup-fixtures
```

Or find name collisions across conftests with the built-ins:

```console
$ pytest --fixtures -v 2>/dev/null | rg '^\w' | awk '{print $1}' | sort | uniq -d
```

Consolidate duplicates into one fixture in the nearest shared conftest; a child
conftest deliberately shadowing a parent fixture is legitimate, so document it.
Delete an empty conftest (H42).

## Autouse audit (H12/H15/H43)

```console
$ rg 'autouse\s*=\s*True' tests/
```

For each autouse fixture, count its setups:

```console
$ pytest --setup-plan | rg '<name>' | rg -c SETUP
```

When the count is about the total tests **and** the body is expensive or
side-effecting, drop `autouse` and opt the real consumers in via
`@pytest.mark.usefixtures`. Keep autouse only for universal, cheap setup (env
reset, time freezing, global state reset). If it does unguarded network I/O
(H15), gate it behind a registered marker or env var with `pytest.skip`.

A `@pytest.mark.*` stacked on a `@pytest.fixture` (H43) is a silent no-op before
pytest 8.0, which warns about it and plans to make it an error later. Remove it
and move the condition into the body (`pytest.skip()`).

## Shared mutable state (H16, H21)

Before widening scope or parallelizing, check whether the shared resource is
mutated:

```console
$ rg 'scope="session"|scope="module"' tests/ ; rg 'create_all|metadata|\.add\(|writestr|bootstrap' tests/
```

If a session or module-scoped resource is written in more than one module, keep
it read-only and isolate writes behind a function-scoped transaction-rollback
fixture, or drop it to function scope. Under xdist a session fixture runs **once
per worker** (H21): for a single shared resource use the
`tmp_path_factory.getbasetemp().parent` + `FileLock` single-exec pattern, or a
`testrun_uid`-keyed resource.
