# Durations parsing

How `00-scan` measures and ranks. pytest's profiler is `--durations`.

## Contents

- What pytest measures
- Three things the table does not do
- Measurement command
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

## Measurement command

Every timed run, in every phase, is the project's `test_command` plus these
flags, so baseline, candidates and verification measure the same thing:

- `-p no:cacheprovider -p no:randomly`: no cache writes, fixed order. A cache
  candidate (H24) drops `-p no:cacheprovider` in its benchmark, its
  verification and the final re-measure, and its saving applies from the second
  run onward.
- `-n 0` when the command, the project's configuration or `PYTEST_ADDOPTS` sets
  xdist workers (`-n`, `--dist`) and xdist is installed: inherited parallel
  options would otherwise defeat the serial measurement.
- No added `-q`. A project's own `-q` leaves the outcome summary, and a second
  one hides it, so the helper reports the counts as unavailable. When the
  summary is hidden (for example `-qq` in `addopts`), the phase stops and says
  so; never fill the counts from a separate collection.

The collection listing is `--collect-only -q` with the first two flags. When no
line holds `::` because the project's options already add `-q`, collect once
without the extra `-q`. A listing with no node ids stops the phase.

For a wrapper (`tox -e py`, `nox -s tests`, `make test`) pass the flags through
the wrapper's own separator (`tox -e py -- <flags>`); when it has none, run it
without them and record that in `baseline.json`.

The tests themselves can write files, and a project runner can update its own
environment (`uv run` syncs before it runs). `00-scan` therefore digests the
working tree before and after its timed runs and reports any change;
`01-benchmark` and `03-execute` run in scratch worktrees.

## Invocations

Rank slowest **test bodies** (H01):

```console
$ pytest --durations=25 --durations-min=0.005 -p no:randomly -p no:cacheprovider
```

Rank slowest **fixture setup/teardown** (H02): use `--durations=0` so no phase is
sliced away before you filter:

```console
$ pytest --durations=0 --durations-min=0.005 -p no:cacheprovider
```

Capture **everything** on a small suite (H04), including `0.00s` rows:

```console
$ pytest --durations=0 --durations-min=0 -p no:cacheprovider
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

```console
$ pytest --junit-xml=<runs-dir>/report.xml -o junit_duration_report=call
```

Read `testcase@time` for per-test `call` time (the default reports
setup+call+teardown). Store the structured result in `baseline.json`.

## Noise band

Fast rows are not benchmarks. To judge a later change:

1. Run one untimed warm-up, then the measurement command above **N ≥ 3** times. `measure.py run` times each run and counts outcomes:

   ```console
   $ python3 <measure.py> run \
       -- pytest -p no:cacheprovider -p no:randomly
   ```

   Append each JSON line to one `.jsonl` file in `<runs-dir>` (see `memory-schema.md`), deleted first.
2. `measure.py band <file>` prints the **median**, the **MAD**, and the noise
   band `max(k * 1.4826 * MAD, floor)` (`k = 3`; the **trust floor**, the larger
   of 50 ms and 1% of the median (125 ms at a 12.5 s median), keeps identical runs from producing a zero band). It reports `valid: false` when any run exits
   non-zero, a run times out, outcome counts are unavailable or empty, counts
   differ between runs, or fewer than three runs were recorded. Unavailable
   output is a measurement failure, not proof of failing tests.
3. `measure.py compare baseline.json <candidate .jsonl>` counts a candidate's
   saving (`baseline_median - candidate_median`) only when it exceeds the band
   (widened by the candidate's own MAD), at least three runs exit 0, and the
   test counts match. Matching counts do not prove the same tests ran: the
   phases also compare collected node ids (`measure.py ids`), which still does
   not show unchanged assertions.

Rank nothing below the trust floor. Never measure under xdist (H19 alone
compares a serial control against `-n auto`): per-worker re-collection and
contention distort totals and rows.
