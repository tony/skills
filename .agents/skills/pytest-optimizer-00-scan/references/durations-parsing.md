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

Every test item runs three independently timed phases: `setup` (the full
fixture and collector chain plus every active plugin's setup hook), `call` (the
test body), and `teardown` (finalizers). The ranked `duration` is a single
`perf_counter()` delta (pytest ≥ 6.0), not warmed or averaged, so fast rows are
high-variance.

## Three things the table does *not* do

1. **It does not group by phase.** Rows print as `{duration:02.2f}s {when:<8}
   {nodeid}`, sorted together by magnitude; the `when` token is the only phase
   discriminator.
2. **It does not attribute cost per fixture.** A `setup` row is the whole chain
   for one item, and a shared higher-scope fixture is billed to the **first**
   item that triggers it. Per-fixture attribution needs the opt-in timing plugin
   (`templates/pytest_optimizer_plugin.py`).
3. **It does not include collection.** Profile collection separately with
   `time pytest --co -q` (H22).

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

`--durations=0` means no N-slice, but `--durations-min` still applies, so it
alone still hides sub-5ms phases. Use `--durations-min=0` (or `-vv`) to show all.

## Bucketing by phase

Each row is `<float>s <when> <nodeid>`. Split on the **second** token:

- `when == "call"` → test-body ranking.
- `when == "setup"` → fixture/setup-chain ranking.
- `when == "teardown"` → finalizer ranking.

A nodeid appears up to three times (once per phase), and subtests add extra
`call` rows under one nodeid: **de-duplicate by `(nodeid, when)`** when
aggregating.

## Machine-readable timings (H07)

When the output must be parsed reliably, prefer JUnit XML over scraping the table:

```bash
pytest --junit-xml=report.xml -o junit_duration_report=call
```

Read `testcase@time` for per-test `call` time (the default reports
setup+call+teardown). Store the structured result in `baseline.json`.

## Noise band

Fast rows are not benchmarks. To judge a later change:

1. Run one untimed warm-up, then the same command serially (no `-n`), cache
   disabled, **N ≥ 3** times. `measure.py run` times each run and counts outcomes:

   ```console
   $ python3 references/measure.py run \
       -- pytest -p no:cacheprovider -p no:randomly -q
   ```

   Append each JSON line to one `.jsonl` file in the memory directory.
2. `measure.py band <file>` prints the **median**, the **MAD**, and the noise
   band `max(k * MAD, floor)` (`k = 3`; the 50 ms **trust floor** keeps identical
   runs from producing a zero band). It reports `valid: false` when any run exits
   non-zero or the counts differ between runs.
3. `measure.py compare baseline.json <candidate .jsonl>` counts a candidate's
   saving (`baseline_median - candidate_median`) only when it exceeds the band,
   every run exits 0, and the test counts match.

Rank nothing below the trust floor. Disable cacheprovider while measuring for
reproducible wall-time, and never measure under xdist: per-worker re-collection
and contention distort totals and rows.
