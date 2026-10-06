# Safety gates

Parallelism and reordering are the biggest speedups and the biggest correctness
risks. A candidate that touches execution order (`-n auto`, `--dist`, `--ff`,
random order) must pass these gates in `01-benchmark` before `02-plan` will score
it — and a failure drops it at the rubric's hard safety gate.

## Contents

- Gate 1: order independence
- Gate 2: collection determinism
- Gate 3: green run, same tests
- Parallelism decision tree
- Measurement hygiene

## Gate 1 — order independence (H17)

A suite is order-independent when every test passes regardless of what ran before
it. Hidden coupling (a module-global mutated by one test and read by another) is
invisible until the order changes.

Run the project's own test command with `pytest-randomly` added to its
environment, so project dependencies are importable. With `uv`:

```console
$ uv run --with pytest-randomly \
    pytest \
    --randomly-seed=1 \
    -p no:cacheprovider
```

If the project uses another runner, install `pytest-randomly` into that
environment instead. Never run the suite through a bare `uvx`: it lacks the
project's dependencies and breaks the gate.

- Run **≥ 3 seeds** (change `--randomly-seed`). Reproduce a failure with `--randomly-seed=last`, then
  `--randomly-seed=<n>`.
- Run any suspect nodeid **in isolation**: if it fails alone but passes in the
  full run, it depends on another test's side effect.
- Without `pytest-randomly`, approximate: run a single test alone, run a module in
  reverse (`pytest tests/test_x.py::test_b tests/test_x.py::test_a`), and run
  subsets.

**Fix the coupling, do not hide it:** reset the mutated global in a fixture
teardown (or make it function-scoped). Only then is a parallel/reorder speedup
eligible.

## Gate 2 — collection determinism (H18)

xdist distributes tests by collection order; workers must collect the **same** set
in the **same** order.

Collect twice, keeping the output in collection order. Do not sort it: sorting
hides order drift, which is the failure this gate exists to catch.

```console
$ pytest --collect-only -q -p no:randomly -p no:cacheprovider > collection-a.txt
```

```console
$ pytest --collect-only -q -p no:randomly -p no:cacheprovider > collection-b.txt
```

Compare them with the script. It drops the `N tests collected in 0.02s` footer,
whose timing differs on every run, and compares node ids in order:

```console
$ python3 ../scripts/measure.py order collection-a.txt collection-b.txt
```

For a candidate that must not change order, compare its collection against the
baseline `collection.txt` the same way.

`same: false` is a hard xdist blocker; `first_difference` is the index of the first differing node id. Causes and fixes:

- `parametrize` over a `set` or unordered dict → list-ify the values.
- Collection that branches on the clock, `random`, or environment → make it
  deterministic.

## Gate 3 — green run, same tests

Every candidate, not only order or scope changes, must pass on a clean serial run
(cache disabled) before its delta is measured: every run exits 0, and the passed
and collected-test counts equal the baseline's. `measure.py compare` enforces
this and returns `valid: false` with the reason otherwise. A change that "speeds
up" by skipping, deselecting, or breaking tests scores nothing. A hypothesis that
deliberately removes tests (a duplicate-test merge) passes `--expect-total` with
the count it should leave.

## Parallelism decision tree

Only after gates 1–3 pass:

1. **Is collection fast?** `time pytest --co -q`. If collection is a large fraction
   of wall-time (H22), do **not** xdist — each worker re-collects. Fix collection
   first (narrow `testpaths`, disable unused autoload plugins, reduce parametrize
   explosion, defer heavy imports).
2. **Enable parallelism** (H19): `-n auto`. Cap `--maxprocesses` when the suite is
   I/O-bound on one shared resource.
3. **Flaky under `-n auto`?** (H20) Run it 5–10×; if failures move between workers,
   co-locate stateful tests with `--dist=loadscope` (group by module/class) or
   `--dist=loadfile`, and/or mark groups with `@pytest.mark.xdist_group`. Refactor
   the shared state only if grouping is insufficient.
4. **Session fixture per worker?** (H21) A session fixture runs once **per worker**.
   For a single shared resource use the `FileLock` single-exec pattern or a
   `testrun_uid`-keyed resource.

## Measurement hygiene

- Never compare a parallel run's wall-time to a serial baseline as "the speedup" —
  benchmark the *change*, holding the run mode fixed, then evaluate parallelism as
  its own separate candidate.
