# Durations parsing

How `00-scan` measures and ranks. pytest's profiler is `--durations`.

## Contents

- What pytest measures
- Three things the table does not do
- Invocations
- Bucketing by phase
- Machine-readable timings
- Noise band

## What pytest measures

Every test item runs **three independently timed phases** — `setup`, `call`,
`teardown` — each wrapped by `CallInfo.from_call`:

- `setup` — the full fixture/collector setup chain for that item, plus every
  active plugin's setup hook work.
- `call` — `item.runtest()`, the test body.
- `teardown` — finalizers for that item.

The ranked `duration` is a single `perf_counter()` delta (pytest ≥ 6.0); it is
**not** warmed or averaged, so fast rows are high-variance.

## Three things the table does *not* do

1. **It does not group by phase.** `pytest_terminal_summary` collects every report
   carrying a `duration`, sorts them all together descending, and prints
   `{duration:02.2f}s {when:<8} {nodeid}`. A `setup` row and a `call` row are
   interleaved purely by magnitude. The only phase discriminator is the middle
   `when` token.
2. **It does not attribute fixture cost per fixture.** A `setup` row is the whole
   setup chain for one item. A shared higher-scope fixture pays its cost once,
   billed to the **first** item that triggers it — so an expensive
   session-scoped fixture appears as one big `setup` row on one nodeid, not spread
   across its consumers. Per-fixture attribution needs the opt-in timing plugin
   (`templates/pytest_optimizer_plugin.py`).
3. **It does not include collection.** `CollectReport` has no `duration`, so
   collection never appears. Profile collection separately with `time pytest --co -q`
   (see H22).

## Invocations

Rank slowest **test bodies** (H01):

```bash
pytest --durations=25 --durations-min=0.005 -p no:randomly -p no:cacheprovider
```

Rank slowest **fixture setup/teardown** (H02) — use `--durations=0` so no phase is
sliced away before you filter:

```bash
pytest --durations=0 --durations-min=0.005 -p no:cacheprovider
```

Capture **everything** on a small suite (H04), including `0.00s` rows:

```bash
pytest --durations=0 --durations-min=0 -p no:cacheprovider
```

`--durations=0` means "no N-slice" (header reads `slowest durations`), but the
`--durations-min` filter still applies — so `--durations=0` alone still hides
sub-5ms phases. Use `--durations-min=0` (or `-vv`) to truly show all.

## Bucketing by phase

Each row is `<float>s <when> <nodeid>`. Split on the **second** token:

- `when == "call"` → test-body ranking.
- `when == "setup"` → fixture/setup-chain ranking.
- `when == "teardown"` → finalizer ranking.

The same nodeid appears up to three times (once per phase), and parametrized
in-core subtests add extra `call` rows under one nodeid — **de-duplicate by
`(nodeid, when)`** when aggregating.

## Machine-readable timings (H07)

When the output must be parsed reliably, prefer JUnit XML over scraping the table:

```bash
pytest --junit-xml=report.xml -o junit_duration_report=call
```

Read `testcase@time` for per-test `call` time (`junit_duration_report=call`
isolates the body; the default reports setup+call+teardown). Store the structured
result in `baseline.json`.

## Noise band

Fast rows are not benchmarks. To know whether a later change is a real speedup:

1. Run one untimed warm-up, then the same command serially (no `-n`), cache
   disabled, **N ≥ 3** times. `measure.py run` times each run and counts outcomes:

   ```console
   $ python3 references/measure.py run \
       -- pytest -p no:cacheprovider -p no:randomly -q
   ```

   Append each JSON line to one `.jsonl` file in the memory directory.
2. `measure.py band <file>` prints the **median**, the **MAD** (median absolute
   deviation), and the noise band `max(k * MAD, floor)` (`k = 3`; the **trust
   floor**, 50 ms, keeps identical runs from producing a zero band). It reports
   `valid: false` when any run exits non-zero or the counts differ between runs.
3. `measure.py compare baseline.json <candidate .jsonl>` counts a candidate's
   saving (`baseline_median - candidate_median`) only when it exceeds the band,
   every run exits 0, and the test counts match.

Rank nothing below the trust floor.

Why disable cacheprovider while measuring: its `.pytest_cache` writes happen at
session start/finish (outside any item phase), so they do **not** change the
duration rows — but disabling it gives reproducible total wall-time and one fewer
timed hook in each phase. Never measure under xdist: per-worker re-collection and
contention distort both totals and rows.
