# Safety gates

A candidate that touches execution order (`-n auto`, `--dist`, `--ff`, random
order) must pass these gates in `01-benchmark` before `02-plan` scores it; a
failure drops it at the rubric's hard safety gate.

## Contents

- Gate 1: order independence
- Gate 2: collection determinism
- Gate 3: green run, same tests
- Parallelism decision tree
- Measurement hygiene

## Gate 1 — order independence (H17)

A suite is order-independent when every test passes regardless of what ran
before it. Run the project's own test command with `pytest-randomly` added to its
environment, so project dependencies are importable. With `uv`:

```console
$ uv run --with pytest-randomly \
    pytest \
    --randomly-seed=1 \
    -p no:cacheprovider
```

With another runner, install `pytest-randomly` into that environment. Never run
the suite through a bare `uvx`: it lacks the project's dependencies.

- Run **≥ 3 seeds** (change `--randomly-seed`). Reproduce a failure with
  `--randomly-seed=last`, then `--randomly-seed=<n>`.
- Run any suspect nodeid **in isolation**: failing alone but passing in the full
  run means it depends on another test's side effect.
- Without `pytest-randomly`, run a single test alone, a module in reverse
  (`pytest tests/test_x.py::test_b tests/test_x.py::test_a`), and subsets.

Fix the coupling, do not hide it: reset the mutated global in a fixture teardown
or make it function-scoped. Only then is a parallel or reorder speedup eligible.

## Gate 2 — collection determinism (H18)

xdist workers must collect the **same** set in the **same** order. Collect
twice, keeping collection order; sorting hides the order drift this gate exists
to catch.

```console
$ pytest --collect-only -q -p no:randomly -p no:cacheprovider > collection-a.txt
```

```console
$ pytest --collect-only -q -p no:randomly -p no:cacheprovider > collection-b.txt
```

Compare them with the script, which drops the timing footer and compares node
ids in order:

```console
$ python3 references/measure.py order collection-a.txt collection-b.txt
```

For a candidate that must not change order, compare its collection against the
baseline `collection.txt` the same way. `same: false` is a hard xdist blocker;
`first_difference` is the index of the first differing node id. Fixes:

- `parametrize` over a `set` or unordered dict → list-ify the values.
- Collection that branches on the clock, `random`, or environment → make it
  deterministic.

## Gate 3 — green run, same tests

Every candidate, not only order or scope changes, must pass a clean serial run
(cache disabled) before its delta is measured: every run exits 0 and the passed
and collected-test counts equal the baseline's. `measure.py compare` enforces
this and returns `valid: false` with the reason otherwise. A hypothesis that
deliberately removes tests passes `--expect-total` with the count it should
leave.

## Parallelism decision tree

Only after gates 1–3 pass:

1. **Is collection fast?** `time pytest --co -q`. If collection is a large
   fraction of wall-time (H22), do **not** xdist: each worker re-collects. Fix
   collection first (narrow `testpaths`, disable unused autoload plugins, reduce
   parametrize explosion, defer heavy imports).
2. **Enable parallelism** (H19): `-n auto`. Cap `--maxprocesses` when the suite
   is I/O-bound on one shared resource.
3. **Flaky under `-n auto`?** (H20) Run it 5-10 times; if failures move between
   workers, co-locate stateful tests with `--dist=loadscope` or `--dist=loadfile`,
   and/or `@pytest.mark.xdist_group`. Refactor the shared state only if grouping
   is insufficient.
4. **Session fixture per worker?** (H21) A session fixture runs once **per
   worker**. For a single shared resource use the `FileLock` single-exec pattern
   or a `testrun_uid`-keyed resource.

## Measurement hygiene

- Never compare a parallel run's wall-time to a serial baseline as the speedup:
  benchmark the change with the run mode fixed, then evaluate parallelism as its
  own candidate.
