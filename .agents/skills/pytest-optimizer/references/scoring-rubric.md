# Scoring rubric

How `02-plan` ranks benchmarked speedup candidates, safety first: which
changes are worth the risk, not which are fastest.

## Dimensions and weights

Each dimension is scored `0.0`–`1.0`. The total is their weighted sum. The weights are defaults.

| Dimension | Weight | `1.0` means | `0.0` means |
|-----------|-------:|-------------|-------------|
| `safety` | 0.35 | Behavior-preserving: pure config/selection, or widening the scope of read-only setup that passed the order-independence (H17) and collection-determinism (H18) gates. | Parallelizing across known shared mutable state, or deleting a fixture reachable only via `getfixturevalue`. |
| `impact` | 0.30 | **Measured** in `01-benchmark`: recovers > 40% of suite wall-time, or removes the single dominant test/fixture. | Saving within the noise band — indistinguishable from jitter. |
| `effort` | 0.15 | Trivial: `addopts`/marker/flag, or a one-line scope change. | Restructuring shared global state across modules. |
| `confidence` | 0.12 | Serial, cache-disabled, repeated runs; delta many multiples of the noise floor. | Collection-bound or xdist-contended numbers known to be distorted, or sub-50ms rows. |
| `reversibility` | 0.08 | A single isolated commit, config-only revert. | An entangled multi-file refactor. |

`measure.py score` computes the total and applies the hard gates below; do not
sum by hand.

```
total = 0.35*safety + 0.30*impact + 0.15*effort
      + 0.12*confidence + 0.08*reversibility
```

Mid-scale anchors keep scoring consistent:

- `safety = 0.5` — scope change on a possibly-mutated resource, autouse removal,
  or xdist with grouping.
- `impact` anchors (defaults, like the weights), from the measured saving as a share of baseline wall-time:
  `0` within the noise band, `0.25` clears the band but under 5%, `0.5` for
  5–15%, `0.75` for 15–40%, `1.0` above 40%. `measure.py impact` applies them.
- `effort = 0.6` — hoist a build into a fixture and add a reset; `0.3` — introduce
  a factory fixture or a filelock single-exec pattern.

## Hard gates (applied before ranking)

A candidate is **dropped from the plan, never auto-applied**, when either holds:

1. **Safety gate:** `safety < 0.4`.
2. **Noise gate:** `impact == 0`: the measured delta did not clear the noise band
   in `01-benchmark`. Hygiene items (H26-H32: typing and parametrize convention)
   are exempt: they save no time by design, so `measure.py score --hygiene`
   skips this gate and rescales the other four weights to sum to 1.

Surviving candidates are ordered by `total` descending, then by the ordering
constraints below.

## Ordering constraints

Score sets the priority, but some changes must precede others regardless of score:

1. **Safety-gate fixes first**: make collection deterministic (H18) and prove
   order independence (H17) before any parallel or reorder speedup.
2. **Typing and parametrize migrations early** (H26-H32): low-risk hygiene items,
   and they make later diffs readable.
3. **Scope and consolidation before parallelism**: fix fixture scope (H10) and
   merge duplicates (H11) before `-n auto` (H19).
4. **One speedup per commit**, so a failed verify discards exactly one change
   in the scratch worktree.

## Worked examples

**Widen a read-only `make_config` fixture from `function` to `session`** (H10):

| Dimension | Score | Reason |
|-----------|------:|--------|
| safety | 0.9 | Setup is read-only; passed H17 across 3 seeds and H18. |
| impact | 0.75 | Measured 22% suite reduction (setup ran 40×, now once). |
| effort | 1.0 | One-line `scope=` change. |
| confidence | 0.9 | Serial, 5 runs, delta ≫ noise floor. |
| reversibility | 0.9 | Single fixture line. |

`total = 0.87` → top of the plan.

**Enable `-n auto` over a suite sharing one on-disk SQLite file** (H19/H16):

| Dimension | Score | Reason |
|-----------|------:|--------|
| safety | 0.1 | Parallel writes to one shared mutable DB file. |

`safety < 0.4` → **dropped at the gate**. The plan surfaces the prerequisite
refactor (isolate the DB per worker via `tmp_path_factory` + `worker_id`, or a
transaction-rollback fixture) as a separate hypothesis, not an auto-applied
speedup.

## Tunable knobs

A project may override these defaults in the orchestration plan:

- **Noise-band multiplier `k`** (default `3`): lower credits smaller deltas as
  real, higher demands a surer win.
- **Safety-gate cutoff** (default `0.4`): raise it to be stricter.
- **Trust floor** (default the larger of `50ms` and 1% of the median): rows below it are too noisy to rank, and
  `confidence` is penalized for candidates resting on them.
