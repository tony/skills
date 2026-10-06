# Memory schema

The four phases communicate only through durable JSON files. That makes the
pipeline idempotent (re-running a completed phase is a no-op while inputs are
unchanged) and resumable (a crash mid-execute picks up at the next item). JSON
is diffable and language-agnostic.

## Contents

- Location resolution
- Idempotency token
- Baseline-diff rule
- Files and shapes

## Location resolution

Resolve the memory directory once and record it in `state.json` so all phases
agree.

1. **Preferred: in-tree, untracked.** `.pytest-optimizer/` at the repo root.
   Keep it out of `git status` by appending the line to the repo's local
   exclude file, not `.gitignore`, so the working tree stays clean and no
   tracked file changes. Add the line only if absent:

   ```bash
   git rev-parse --git-path info/exclude
   ```

   Append `.pytest-optimizer/` to the file that prints.
2. **Fallback: per-user cache**, when the tree is read-only or the user
   declines any in-tree directory:
   - `$XDG_CACHE_HOME/pytest-optimizer/<repo-id>/` on Linux and macOS (default
     `~/.cache/...` when unset), or
   - `%LOCALAPPDATA%\pytest-optimizer\<repo-id>\` on Windows.
   - `<repo-id>` is a short hash of the repo's absolute path plus git remote.
3. **Override.** `--memory-dir=<path>` forces a location, for example in CI.

Helpers generated from `templates/` are untracked files too. Append their paths
to the same exclude file unless the user chooses to commit them.

## Idempotency token

```
token = hash(git HEAD
             + sorted collection node-ids
             + pytest version + plugin versions
             + environment fingerprint)
```

A phase is a no-op on re-run when `state.json` marks it `completed`, the token
is unchanged, and its output file exists. `--force` overrides all three.

The environment fingerprint (Python version, OS, CPU model) is included because
timings are machine-specific. `git HEAD` is included so the commits
`03-execute` makes change the token, and the next `00-scan` re-baselines.

## Baseline-diff rule

The noise band is `k * MAD`, measured per project in `00-scan` from N serial,
cache-disabled runs. A candidate is a real speedup only when its median saving
exceeds the band:

```
real_speedup  <=>  baseline_median - candidate_median > k * MAD    (default k = 3)
```

Never quote the band as a fixed number.

## Files and shapes

Paths are relative to the memory directory. Every skill writes exactly these
fields.

- `state.json` (all phases): phase cursor, tokens, memory path.
- `baseline.json` (`00-scan`): environment, noise band, per-phase timings.
- `capabilities.json` (`00-scan`): resolved version-matrix probes.
- `hypotheses.json` (`00-scan`): candidate speedups with heuristic id and
  evidence.
- `benchmarks.json` (`01-benchmark`): measured delta and gate outcomes per
  hypothesis.
- `plan.json` (`02-plan`): ranked commit plan.
- `execution-log.json` (`03-execute`): per-item checkpoint.

### `state.json`

```json
{
  "phase": "benchmark",
  "run_id": "string",
  "memory_dir": ".pytest-optimizer",
  "collection_hash": "string",
  "env_token": "string",
  "completed": { "scan": true, "benchmark": false, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
```

### `baseline.json`

```json
{
  "captured_at": "ISO-8601",
  "python": "3.13.x",
  "pytest_version": "9.1.1",
  "plugins": { "pytest-xdist": "3.x", "pytest-randomly": "3.x" },
  "test_command": "<project test command>",
  "capabilities": { "durations_min": true, "stash": true },
  "runs": [ { "wall_seconds": 12.4 }, { "wall_seconds": 12.6 } ],
  "noise": { "median": 12.5, "mad": 0.15, "floor": 0.05, "k": 3 },
  "timings": [ { "nodeid": "tests/test_x.py::test_a", "phase": "setup", "seconds": 0.42 } ]
}
```

### `hypotheses.json`

Each `id` derives from content, `<heuristic>-<sorted target files>-<short
evidence digest>`, not a counter. An unchanged candidate keeps its id across
re-scans, so `01-benchmark` skips it; a new candidate gets a new id. A
re-baseline after `03-execute` re-opens all candidates.

```json
[
  {
    "id": "H10-conftest-make_config",
    "heuristic": "H10",
    "evidence": "make_config SETUP runs 40x at function scope, body ~0.3s",
    "est_risk": "medium",
    "est_effort": "small",
    "status": "open"
  }
]
```

### `benchmarks.json`

```json
[
  {
    "id": "H10-conftest-make_config",
    "diff_summary": "scope=\"function\" -> scope=\"session\" on make_config",
    "runs": 5,
    "median_delta": 2.7,
    "clears_noise": true,
    "gates": { "order_indep": true, "collection_det": true, "green": true },
    "confidence": 0.9,
    "observed_risk": "low",
    "verdict": "validated",
    "reason": null
  }
]
```

### `plan.json`

```json
[
  {
    "order": 1,
    "id": "H10-conftest-make_config",
    "score": { "safety": 0.9, "impact": 0.7, "effort": 1.0, "confidence": 0.9, "reversibility": 0.9, "total": 0.855 },
    "files": ["tests/conftest.py"],
    "commit": { "subject": "test(fixtures) widen make_config to session scope", "body": "why: ...\n\nwhat:\n- ..." },
    "verify": "<project test command>",
    "depends_on": []
  }
]
```

### `execution-log.json`

```json
[
  {
    "order": 1,
    "id": "H10-conftest-make_config",
    "applied": true,
    "verify": { "passed": true, "output_ref": "checkpoint-1.txt" },
    "commit_sha": "abc1234",
    "skip_reason": null,
    "ts": "ISO-8601"
  }
]
```
