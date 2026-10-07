# Version matrix

The available toolbox depends on the installed pytest and plugins. `00-scan`
probes once and writes the resolved result to `capabilities.json`; later phases
use only what exists. Run every probe through the project's runner (for
example `uv run python -c ...`), so the project environment answers, not the
system Python.

## Detection procedure

1. Read the pytest version:

   ```console
   $ python -c "import pytest; print(pytest.__version__)"
   ```

2. Probe flags that may be absent (cheaper and more reliable than version math
   for CLI options):

   ```console
   $ pytest --help 2>/dev/null | rg -- '--durations-min|--import-mode|--dist|--sw-reset'
   ```

3. Probe plugin presence and version:

   ```console
   $ python -c "import importlib.metadata as m; [print(d, next((x.version for x in m.distributions() if x.metadata['Name'].lower() == d), 'missing')) for d in ('pytest-xdist', 'pytest-randomly', 'pytest-timeout')]"
   ```

4. For API features, import-probe:

   ```console
   $ python -c "import pytest; print(hasattr(pytest, 'StashKey'))"
   ```

5. Record each feature as `{available, version, flag, fallback}` in
   `capabilities.json`. When a feature is unavailable, the phase silently uses the
   listed fallback rather than failing.

## Feature gates

Each row links the changelog entry for its minimum version. A `probe only` row has no
source for a version: trust the probe, not a number.

| Feature | Min version | Detect | Fallback when absent | Source |
|---------|-------------|--------|----------------------|--------|
| `CallInfo.duration` from `perf_counter` | pytest 6.0 | `pytest --version` >= 6.0 | pre-6.0 duration is a `time.time()` delta (coarser); widen the noise band | [pytest 6.0.0](https://docs.pytest.org/en/stable/changelog.html#pytest-6-0-0-2020-07-28) |
| `--durations-min` | pytest 6.1 | `--durations-min` listed in `pytest --help` | threshold hard-coded at `0.005s`; post-filter rows yourself | [pytest 6.1.0](https://docs.pytest.org/en/stable/changelog.html#pytest-6-1-0-2020-09-26) |
| `--durations-min` respected under `-vv` | pytest 8.4 | `pytest --version` >= 8.4 | drop `-vv`, rely on explicit `--durations-min` | [pytest 8.4.0](https://docs.pytest.org/en/stable/changelog.html#pytest-8-4-0-2025-06-02) |
| In-core subtests (extra per-subtest `call` rows) | pytest 9.0 | `pytest.Subtests` exists, or `pytest-subtests` installed | one `call` row per item; de-dup nodeids when bucketing | [pytest 9.0.0](https://docs.pytest.org/en/stable/changelog.html#pytest-9-0-0-2025-11-05) |
| `junit_duration_report` ini (`call` vs total) | pytest 4.1 | `junit_duration_report` listed in `pytest --help` | older JUnit reports total (setup+call+teardown) only | [pytest 4.1.0](https://docs.pytest.org/en/stable/changelog.html#pytest-4-1-0-2019-01-05) |
| `--import-mode=importlib` | pytest 6.0 | `--import-mode` listed in `pytest --help` | default `prepend` mode (mutates `sys.path`; needs unique test filenames) | [pytest 6.0.0](https://docs.pytest.org/en/stable/changelog.html#pytest-6-0-0-2020-07-28) |
| `Stash` (typed per-run store) | pytest 7.0 | `pytest.Stash` exists | `config.cache` (JSON) cross-run; attach attrs to config/session within-run | [pytest 7.0.0](https://docs.pytest.org/en/stable/changelog.html#pytest-7-0-0-2022-02-03) |
| `--sw-reset` (stepwise reset) | pytest 8.4 | `--sw-reset` listed in `pytest --help` | `--sw` / `--sw-skip` | [pytest 8.4.0](https://docs.pytest.org/en/stable/changelog.html#pytest-8-4-0-2025-06-02) |
| Callable (dynamic) fixture `scope` | pytest 5.2 | `@pytest.fixture(scope=<callable>)` | hardcode the scope, or gate via a CLI flag read inside the fixture | [fixtures: Dynamic scope](https://docs.pytest.org/en/stable/how-to/fixtures.html#dynamic-scope) |
| A mark applied to a fixture warns | pytest 8.0 | `pytest --collect-only -q` reports the warning | where nothing is reported, the fix (skip in body) is identical | [pytest 8.0.0](https://docs.pytest.org/en/stable/changelog.html#pytest-8-0-0-2024-01-27) |
| `pytest.register_fixture` (imperative) | pytest 9.1 | `pytest.register_fixture` exists | `@pytest.fixture` decorator (declarative) | [pytest 9.1.0](https://docs.pytest.org/en/stable/changelog.html#pytest-9-1-0-2026-06-13) |
| `tmp_path` / `tmp_path_factory` | pytest 3.9.1 | `rg 'tmp_path' tests/` | `tmpdir`/`tmpdir_factory` (`py.path.local`) on older pytest | [pytest 3.9.1](https://docs.pytest.org/en/stable/changelog.html#pytest-3-9-1-2018-10-16) |
| `--strict-markers` | pytest 4.5 | `strict-markers` in `addopts` (`rg -e 'strict-markers' -e '--strict' pyproject.toml`) | `--strict` on older pytest | [pytest 4.5.0](https://docs.pytest.org/en/stable/changelog.html#pytest-4-5-0-2019-05-11) |
| `pytest11` entry point (ship fixtures as a plugin) | probe only | `[project.entry-points.pytest11]` in pyproject | `pytest_plugins = ('pkg.module',)` explicit import | probe only |
| `pytest-xdist` parallel (`-n auto`, `worker_id`) | probe only | `importlib.metadata.version('pytest-xdist')` | run serially | probe only |
| `-n logical` | xdist 2.3 | `pytest -n logical --co` | `-n auto` (physical cores) | [xdist 2.3.0](https://pytest-xdist.readthedocs.io/en/stable/changelog.html#pytest-xdist-2-3-0-2021-06-16) |
| `--dist=loadgroup` + `xdist_group` mark | xdist 2.5 | `--dist` listed in `pytest --help` | `loadscope` (group by module/class) or `loadfile` | [xdist 2.5.0](https://pytest-xdist.readthedocs.io/en/stable/changelog.html#pytest-xdist-2-5-0-2021-12-10) |
| `--dist=worksteal` | xdist 3.2 | `pytest -n2 --dist=worksteal --co` | `--dist=load` (default) | [xdist 3.2.0](https://pytest-xdist.readthedocs.io/en/stable/changelog.html#pytest-xdist-3-2-0-2023-02-07) |
| `pytest-randomly` (order-independence detector) | plugin install | `importlib.metadata.version('pytest-randomly')` | run subsets/single tests in isolation and reversed order manually | probe only |
| `pytest-deadfixtures` (`--dead-fixtures`/`--dup-fixtures`) | plugin install | `importlib.metadata.version('pytest-deadfixtures')` in the project environment | built-in `--fixtures` vs `--fixtures-per-test` diff (zero-dependency) | [PyPI README](https://pypi.org/project/pytest-deadfixtures/) |
| `pytest-timeout` (`--timeout-method=thread`) | probe only | `rg -e 'pytest-timeout' -e '^timeout =' -e '--timeout' pyproject.toml` | no global timeout; rely on the CI job timeout | [README](https://github.com/pytest-dev/pytest-timeout#readme) |
| Strict type checker covers `tests/` | tooling (not pytest) | `[tool.mypy] strict=true` incl. tests, or pyright config incl. tests | phrase the gate as "the project strict checker includes the test directory" | probe only |

## Notes

- Prefer **probing a flag** (`--help | rg`) over comparing version strings: it
  survives backports, vendored builds, and plugins that add or remove options.
