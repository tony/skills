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

Every phase resolves the memory directory the same way, from the repo root
(`git rev-parse --show-toplevel`), and never reads its location from a file
inside it. The first match wins:

1. `--memory-dir=<path>`, for example in CI.
2. `.pytest-optimizer/` at the repo root, if it exists.
3. The per-user cache, if it exists: `$XDG_CACHE_HOME/pytest-optimizer/<repo-id>/`
   (default `~/.cache/...`) on Linux and macOS, `%LOCALAPPDATA%\pytest-optimizer\<repo-id>\`
   on Windows. `<repo-id>` hashes the repo path plus the `origin` URL.
4. None exists: `00-scan` creates one (below); every other phase stops and tells
   the user to run `00-scan`.

The script resolves it and prints the path to use literally afterwards:

```console
$ python3 references/measure.py memory-dir \
    --repo-root "$(git rev-parse --show-toplevel)"
```

The JSON has `path`, `source` (`explicit`, `in-tree`, `cache`, `new`), `exists`,
and `cache_path`. Run it by its absolute path; the relative `scripts/` path is from the
file that names it, not from the repo.

`00-scan` creates the in-tree directory and keeps it out of `git status` by
appending `.pytest-optimizer/` to the local exclude file (not `.gitignore`) when
that line is absent:

```console
$ git rev-parse --git-path info/exclude
```

It creates `cache_path` instead when the tree is read-only or the user declines
an in-tree directory.

Helpers generated from `templates/` are untracked files too. Append their paths
to the same exclude file unless the user chooses to commit them.

## Idempotency token

```
token = hash(git HEAD
             + sorted collection node-ids
             + pytest version + plugin versions
             + environment fingerprint)
```

`measure.py token` computes it; the script sorts the node ids itself.

A phase is a no-op on re-run when `state.json` marks it `completed`, the token
is unchanged, and its output file exists. `--force` overrides all three.

The environment fingerprint (Python version, OS, machine architecture) is included because
timings are machine-specific. `git HEAD` is included so the commits
`03-execute` makes change the token, and the next `00-scan` re-baselines.

## Baseline-diff rule

The noise band is `max(k * MAD, trust floor)` (`k = 3`, floor `0.05` s), measured
per project in `00-scan` from N serial, cache-disabled runs. A candidate is a real
speedup only when every run exits 0, its passed and collected-test counts match
the baseline, and its median saving exceeds the band:

```
real_speedup  <=>  baseline_median - candidate_median > band
```

`measure.py band` and `measure.py compare` apply this; never do the arithmetic by
hand or quote the band as a fixed number.

## Files and shapes

Paths are relative to the memory directory. Every skill writes exactly these
fields.

- `state.json` (all phases): phase cursor, tokens, plan hash.
- `baseline.json` (`00-scan`): environment, noise band, per-phase timings.
- `collection.txt` (`00-scan`): baseline `--collect-only -q` output, in collection
  order.
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
  "collection_hash": "string",
  "env_token": "string",
  "completed": { "scan": true, "benchmark": false, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
```

`plan_hash` stays `null` until the user approves `plan.json`; then it holds the
`measure.py hash` of that file, and `03-execute` refuses a plan whose hash differs.

### `baseline.json`

```json
{
  "captured_at": "ISO-8601",
  "python": "3.13.x",
  "pytest_version": "<version>",
  "plugins": { "pytest-xdist": "3.x", "pytest-randomly": "3.x" },
  "test_command": "<project test command>",
  "capabilities": { "durations_min": true, "stash": true },
  "runs": [ { "wall_seconds": 12.4 }, { "wall_seconds": 12.6 } ],
  "noise": { "median": 12.5, "mad": 0.15, "floor": 0.05, "k": 3, "band": 0.45 },
  "tests": { "passed": 240, "total": 242 },
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
    "score": { "safety": 0.9, "impact": 0.75, "effort": 1.0, "confidence": 0.9, "reversibility": 0.9, "total": 0.87 },
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
