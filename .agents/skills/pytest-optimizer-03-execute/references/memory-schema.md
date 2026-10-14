# Memory schema

The four phases communicate only through durable JSON files, so a completed
phase is a no-op while its inputs are unchanged and a crash mid-execute resumes
at the next item.

## Contents

- Location resolution
- Idempotency token
- Run files
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
appending `.pytest-optimizer/` to the local exclude file (not `.gitignore`):

```console
$ python3 <measure.py> exclude \
    .pytest-optimizer/
```

The command adds only the lines that are missing and exits 1 with a reason when
the file is not writable (some sandboxed hosts refuse writes under `.git/`).
`00-scan` then creates `cache_path` instead, as it does when the tree is
read-only or the user declines an in-tree directory: an unexcluded in-tree
directory would dirty `git status`. Pass the paths of helpers generated from
`templates/` to the same command unless the user chooses to commit them; when it
exits 1, tell the user to add those paths.

## Idempotency token

```
token = hash(git HEAD
             + sorted collection node-ids
             + pytest version + plugin versions
             + environment fingerprint
             + digest of dirty and untracked inputs
             + resolved test command)
```

`measure.py token` computes it and sorts the node ids itself; `isolate.py inputs`
supplies the digest of tracked edits and untracked files (gitignored files are
outside it). The environment fingerprint is Python version, OS, and machine
architecture. A phase is a no-op on re-run when `state.json` marks it
`completed`, the token is unchanged, and its output file exists; `--force`
overrides all three. A scan of a dirty tree is for inspection only: every later phase refuses its
evidence until the tree is clean and the scan is re-run.
`isolate.py stale --phase benchmark|plan|execute` applies the bindings below
and prints the first failure with the phase that repairs it (`rerun`).
`01-benchmark` runs no collection: it halts on a missing
`env_token`, a true `dirty`, or a `HEAD`, inputs digest, test command or pytest
version that differs from the scan's, naming `00-scan --force` as the fix.
`02-plan` and `03-execute` run no tests: they require `HEAD` to equal
`base_head` and every entry or plan item to carry `state.json`'s `env_token`
and a patch hash.
`03-execute` commits to its own branch, so a resumed run checks that the branch
is `base_head` plus exactly the commits in `execution-log.json`
(`measure.py chain --head`). The next `00-scan` re-baselines.

## Run files

`measure.py run` output is appended to JSONL files that live outside the
working tree. The command creates the directory and prints its `path` and
`source`; write that literal path as `<runs-dir>` in later commands:

```console
$ python3 <measure.py> runs-dir \
    --memory-dir <memory-dir>
```

The `source` is the per-worktree git directory (`git rev-parse --git-path`,
which every git version supports), else `<memory-dir>/runs` (the memory
directory is already outside `git status`), else a temporary directory. A
temporary directory does not outlive the session; a later session re-creates its
run files, since each is deleted before its first timed run. Say which location
was used only when the user must act on the files. Delete a run file before its first timed run, so a re-run, `--force`,
or a post-execute re-scan never mixes old samples into a band. Nothing here
shows in `git status`.

`run` exits 0 when it records a command; its `exit` field holds the command's
status. An unavailable outcome summary produces null `passed` and `total`
fields with a `reason`. `band` and `compare` reject these records, empty
outcomes and invalid counts. Never substitute a separate collection count.

## Baseline-diff rule

The noise band is `max(k * 1.4826 * MAD, trust floor)` (`k = 3`; the trust floor is
the larger of `0.05` s and 1% of the median, so a 12.5 s median gives `0.125` s), measured per project in `00-scan`
from N serial, cache-disabled runs. `compare` widens the dispersion with the
candidate's own MAD, `hypot(baseline MAD, candidate MAD)`. A candidate is a real
speedup only when at least three runs exit 0, its reported outcome counts match
the baseline, its collected node ids match the scan's, and its median saving
exceeds that band:

```
real_speedup  <=>  baseline_median - candidate_median > band
```

`measure.py band` and `measure.py compare` apply this; never do the arithmetic
by hand or quote the band as a fixed number.

An approved `--expect-total` can reduce passing outcomes while preserving
`total - passed`. Report that result as time saved by deselection. These counts
do not prove test identity or preserved assertions.

## Files and shapes

Paths are relative to the memory directory. Besides `state.json` (every phase),
`collection.txt` (baseline `--collect-only -q` output in collection order),
`capabilities.json` (resolved version-matrix probes, written with `measure.py
state update <memory-dir>/capabilities.json --set KEY=JSON`), and `control.json` (the
unmodified-worktree summary from `measure.py band`, the reference candidates are
judged against), each file's shape follows. The JSONL run files
(`baseline-runs.jsonl`, `control-runs.jsonl`, `<hypothesis-id>-runs.jsonl`,
`post-runs.jsonl`, one `measure.py run` line each) live in `<runs-dir>`, not here.

### `state.json`

```json
{
  "phase": "benchmark",
  "run_id": "from measure.py run-id, set when 03-execute starts",
  "env_token": "string",
  "hygiene": false,
  "base_head": "git sha of HEAD when 00-scan ran",
  "inputs_digest": "isolate.py inputs digest when 00-scan ran",
  "dirty": false,
  "exec_branch": "pytest-optimizer/<run_id>, set when 03-execute starts",
  "exec_dir": "owned scratch directory of that run",
  "completed": { "scan": true, "benchmark": false, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
```

`hygiene` records whether `00-scan` ran with `--hygiene`; a later `00-scan` whose
flag differs re-scans even when the token is unchanged.

Each phase sets its own `completed` flag when it finishes: `00-scan`,
`01-benchmark`, `02-plan` (on approval), `03-execute` (plan exhausted). The
script owns the flags, so a re-run of an earlier phase clears the later ones and
a resume reads the first open phase:

```console
$ python3 <measure.py> state \
    complete <memory-dir>/state.json \
    --phase scan \
    --set 'env_token="<token>"'
```

```console
$ python3 <measure.py> state \
    resume <memory-dir>/state.json
```

`--set` takes `KEY=JSON` and repeats. `state update` merges `--set` fields
(`exec_branch`, `last_applied_index`) without touching the flags. `resume` prints `next` (`null` when all
four phases are complete) and the four flags. A missing file resumes at `scan`.

`plan_hash` stays `null` until the user approves `plan.json`; then it holds the
`measure.py hash` of that file.

### `baseline.json`

`measure.py baseline` writes it from the timed runs, keeping fields it does not
own (the `timings` of `00-scan` Step 5) and writing nothing when the runs are
invalid:

```console
$ python3 <measure.py> baseline \
    <runs-dir>/baseline-runs.jsonl \
    --out <memory-dir>/baseline.json \
    --test-command "<test_command>" \
    --pytest-version <version> \
    --plugin pytest-xdist=<version> \
    --flag=-p \
    --flag=no:cacheprovider
```

`--plugin` and `--flag` repeat; `--capabilities <file>` embeds
`capabilities.json`. The output below is its shape.

```json
{
  "captured_at": "ISO-8601",
  "python": "3.13.x",
  "pytest_version": "<version>",
  "plugins": { "pytest-xdist": "3.x", "pytest-randomly": "3.x" },
  "test_command": "<project test command>",
  "measurement_flags": ["-p", "no:cacheprovider", "-p", "no:randomly"],
  "capabilities": { "durations_min": true, "stash": true },
  "runs": [ { "wall_seconds": 12.4 }, { "wall_seconds": 12.6 } ],
  "noise": { "median": 12.5, "mad": 0.1, "floor": 0.125, "k": 3, "band": 0.44478 },
  "tests": { "passed": 240, "total": 242 },
  "timings": [ { "nodeid": "tests/test_x.py::test_a", "phase": "setup", "seconds": 0.42 } ]
}
```

### `hypotheses.json`

Each `id` derives from content, `<heuristic>-<sorted target files>-<short
evidence digest>`, not a counter, so an unchanged candidate keeps its id across
re-scans. A re-baseline after `03-execute` re-opens all candidates.
`measure.py hyp-id --heuristic <id> --file <path> --evidence <text>` computes it,
and `measure.py record <memory-dir>/hypotheses.json --id <id> --set KEY=JSON ...`
(no `--state`, so nothing is stamped) writes the entry.

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

`measure.py record <memory-dir>/benchmarks.json --state <memory-dir>/state.json
--id <id> --set KEY=JSON ...` (or `--entry <file>`) upserts one entry by `id` and
stamps `env_token` and `base_head` from `state.json`; it exits 1 when the entry
has no `id` or the state has no token. `measure.py pending --memory-dir
<memory-dir> [--only <id or heuristic>] [--force]` lists the open hypotheses
whose entry does not already carry the current token.

```json
[
  {
    "id": "H10-conftest-make_config",
    "env_token": "string",
    "diff_summary": "scope=\"function\" -> scope=\"session\" on make_config",
    "runs": 5,
    "base_head": "git sha the candidate was cut from",
    "patch": "patches/H10-conftest-make_config.patch",
    "patch_sha256": "string",
    "files": ["tests/conftest.py"],
    "cache": "disabled",
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

`env_token` is `state.json`'s `env_token` when the entry was recorded: an entry
whose token differs from the current one, or has none, is stale and is
re-benchmarked. `patch` is the change `isolate.py capture` wrote in the scratch
worktree and `patch_sha256` binds its bytes; `03-execute` applies that patch,
never a re-described change. `cache` is `enabled` for a cross-run cache
candidate (H24), measured and verified with the cache provider on.
`removes_tests` is the number of tests a deselecting change (H15, H37) drops from
the default run and `removed_ids` lists their node ids; both are absent
otherwise. `kind` is `"hygiene"` for a typing or parametrize item (H26-H32): no timing,
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
    "env_token": "string",
    "patch": "patches/H10-conftest-make_config.patch",
    "patch_sha256": "string",
    "cache": "disabled",
    "removed_ids": [],
    "verify": "<project test command>",
    "expected_total": 40,
    "depends_on": []
  }
]
```

`measure.py plan-build` writes this file from the drafted judgment (`order`,
`id`, `commit`, `verify`, `depends_on` and the four judged dimensions in
`score`) and `benchmarks.json`: it derives `impact` and the total, copies the
patch binding, and computes `expected_total`. `measure.py totals <baseline.json>
<draft.json>` prints the totals alone from a JSON list of `{order,
removes_tests}`. `expected_total` is cumulative: the collected-test count after this item and
every earlier item apply. It starts at the baseline `tests.total` and drops by
the tests each deselecting item removes, so a later item inherits the reduced
count.

### `execution-log.json`

```json
[
  {
    "order": 1,
    "id": "H10-conftest-make_config",
    "applied": true,
    "verify": { "passed": true, "seconds": 7.9, "output_ref": "verify-1.jsonl" },
    "commit_sha": "abc1234",
    "skip_reason": null,
    "ts": "ISO-8601"
  }
]
```

`measure.py log --memory-dir <memory-dir> begin|commit|skip --order <n> --set
KEY=JSON ...` writes every transition and updates `last_applied_index` in
`state.json`; `skip` also marks each item that depends on the skipped one (by
`id` or `order`, transitively) as not applied. `--log-file <path>` redirects a
dry run's log and leaves `state.json` alone.

An entry is written with `pending_subject`, `pending_parent` (the branch tip)
and `pending_tree` (the tree `isolate.py gate` printed) before the commit is
made, then completed with `commit_sha`. A resume that finds an entry with
`pending_tree` and no `commit_sha` adopts the branch tip only when
`isolate.py landed` confirms it is one commit on `pending_parent` holding
exactly `pending_tree`; a matching subject proves nothing.

`patches/` under the memory directory holds one patch per benchmarked
hypothesis, and the scratch worktree and result branch of a run are owned by
`isolate.py` (`owner.json` beside the worktree).
