# Memory schema

The four phases communicate only through durable JSON files, so a completed
phase is a no-op while its inputs are unchanged and a crash mid-execute resumes
at the next item.

## Contents

- Location resolution
- Idempotency token
- Baseline-diff rule
- Files and shapes

## Location resolution

Every phase resolves the memory directory from the repo root
(`git rev-parse --show-toplevel`), never from a file inside it. The first match
wins:

1. `--memory-dir=<path>`, for example in CI.
2. `.pytest-optimizer/` at the repo root, if it exists.
3. The per-user cache, if it exists: `$XDG_CACHE_HOME/pytest-optimizer/<repo-id>/`
   (default `~/.cache/...`) on Linux and macOS, `%LOCALAPPDATA%\pytest-optimizer\<repo-id>\`
   on Windows. `<repo-id>` hashes the repo path plus the `origin` URL.
4. None exists: `00-scan` creates one (below); every other phase stops and tells
   the user to run `00-scan`.

The script resolves it and prints the path to use literally afterwards. Run it
by the absolute path of `scripts/measure.py` (`<measure.py>`), which the calling
skill resolves from its own directory.

```console
$ python3 <measure.py> memory-dir \
    --repo-root "$(git rev-parse --show-toplevel)"
```

The JSON has `path`, `source` (`explicit`, `in-tree`, `cache`, `new`), `exists`,
and `cache_path`.

`00-scan` creates the in-tree directory and keeps it out of `git status` by
appending `.pytest-optimizer/` to the local exclude file (not `.gitignore`) when
that line is absent:

```console
$ git rev-parse --git-path info/exclude
```

It creates `cache_path` instead when the tree is read-only or the user declines
an in-tree directory. Append the paths of helpers generated from `templates/` to
the same exclude file unless the user chooses to commit them.

## Idempotency token

```
token = hash(git HEAD
             + sorted collection node-ids
             + pytest version + plugin versions
             + environment fingerprint)
```

`measure.py token` computes it and sorts the node ids itself. The environment
fingerprint is Python version, OS, and machine architecture. A phase is a no-op
on re-run when `state.json` marks it `completed`, the token is unchanged, and its
output file exists; `--force` overrides all three. `01-benchmark` and a fresh
`03-execute` run recompute the token before reading `baseline.json` and halt on
a mismatch with `state.json`'s `env_token`, naming `00-scan --force` as the fix.
`03-execute`'s own commits change `HEAD` and the collected node ids, so a resumed
run skips the token and checks instead that `HEAD` is `base_head` plus exactly
the commits in `execution-log.json` (`measure.py chain`). The next `00-scan`
re-baselines.

## Baseline-diff rule

The noise band is `max(k * MAD, trust floor)` (`k = 3`, floor `0.05` s), measured
per project in `00-scan` from N serial, cache-disabled runs. A candidate is a real
speedup only when every run exits 0, its passed and collected-test counts match
the baseline, and its median saving exceeds the band:

```
real_speedup  <=>  baseline_median - candidate_median > band
```

`measure.py band` and `measure.py compare` apply this; never do the arithmetic
by hand or quote the band as a fixed number.

## Files and shapes

Paths are relative to the memory directory. Besides `state.json` (every phase),
`collection.txt` (baseline `--collect-only -q` output in collection order), and
`capabilities.json` (resolved version-matrix probes), the JSONL run files
(`baseline-runs.jsonl`, `control-runs.jsonl`, `<hypothesis-id>-runs.jsonl`, one
`measure.py run` line each) and `control.json` (the unmodified-worktree summary
from `measure.py band`, the reference candidates are judged against), each
file's shape follows:

### `state.json`

```json
{
  "phase": "benchmark",
  "run_id": "string",
  "collection_hash": "string",
  "env_token": "string",
  "base_head": "git sha of HEAD when 00-scan ran",
  "completed": { "scan": true, "benchmark": false, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
```

`plan_hash` stays `null` until the user approves `plan.json`; then it holds the
`measure.py hash` of that file.

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
evidence digest>`, not a counter, so an unchanged candidate keeps its id across
re-scans. A re-baseline after `03-execute` re-opens all candidates.

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

`kind` is `"hygiene"` for a typing or parametrize item (H26-H32): no timing,
`median_delta` and `clears_noise` null, `verdict` `validated` when the suite and
type checker pass. Every other entry is `"speedup"` (the default when absent).

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
    "expected_total": 40,
    "depends_on": []
  }
]
```

`expected_total` is the collected-test count after the item applies: the
baseline `tests.total`, or another number only for an item that removes or adds
tests on purpose.

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
