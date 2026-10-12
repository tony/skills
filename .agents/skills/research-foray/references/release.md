# Check, release, decide, export

## Contents

- 1. Check, fresh
- 2. Release
- 3. Decide
- 4. Watch it
- 5. Export
- Output

What happens between a finished report and the people who act on it. `<run_dir>` is the run that holds the report, usually the newest. These steps record what became of that run's own report, so they write into it even when it was last opened before today (`layout.md`, Reruns); they never change its report, sources, or captures.

## 1. Check, fresh

```console
$ python3 <topic.py> check --run <run_dir>
```

`check` reruns every ship check in one call: each source against its capture and live URL, the report's Sources table against the manifest, `lint-report --strict`, what `brief.md` adds beyond the report (a citation or an uncited sentence), the `redact` decision on a public run, and the leak scan.

When it fails, `first_failing` names the first prerequisite that failed (verify, sources, claims, lint, redact, or scan) and `next` lists the fixes in order. The usual loop: fix, run the pipeline from that step per `report.md` steps 6 to 8, then `check` again. On a public run, `redact_decision: missing` means the `redact` key is not set in `index.md`: `release` refuses until it is a list or `[]` (`report.md`, Audience). `counts` holds the numbers a hero quotes. When `<run_dir>` was last opened before today, do not fix its report in place: continue the topic per `continue.md` and release from today's run. `--offline` checks the captures only and makes no request; use it when the request says there is no network. `live: false` in the result says so, and a hero that reports it names the check as offline. Without `--offline`, `check` fetches every URL and writes `unreachable` rows to `checks.jsonl` when it cannot reach one.

## 2. Release

```console
$ python3 <topic.py> release \
    --run <run_dir> \
    --to "<who receives it, as a role or group>" \
    --audience <the reader's audience: private, internal, or public>
```

`release` refuses when `--audience` differs from the run's audience. It runs the same checks and refuses on any failure. It also refuses `--offline`: a report a client reads needs a live check. When no network is reachable, pass `--offline --allow-offline` only after the user says the readers accept captures-only evidence; otherwise stop and offer it as a choice (without an interactive host, stop and say so). The release row records `live: false`. On a pass it keeps the exact report (and `brief.md`, when there is one) under `releases/`, named by its hash, and appends to `<run_dir>/references/releases.jsonl`: when, to whom, at which audience, the report's sha256, and which version of each cited source it rested on. Name recipients by role at internal and public audiences.

## 3. Decide

Runs under `release`, as does `export` (step 5).

When the reader acts on the report, record it:

```console
$ python3 <topic.py> decide \
    --run <run_dir> \
    --decision "<what was decided>" \
    --by "<who decided, as a role>" \
    --revisit "<what evidence would reopen it>"
```

The decision traces to the latest release in `<run_dir>`, or to `--release <hash prefix>`; pass the run that holds that release, even after a newer run exists. A decision with no release is refused: a decision must trace to the exact report its maker read.

## 4. Watch it

`status` lists the latest release to each reader whose cited sources have since changed, failed a check, or been retired, with the decisions taken on it. When one appears, name the release and its readers to the user and offer `continue`. A corrected report goes to the same readers only when the user names `release` again, with what changed in `--note`; that release clears the flag. Revisit each listed decision against its `revisit` condition.

## 5. Export

```console
$ python3 <topic.py> export --run <run_dir>
```

`export` packs the whole run into a zipped [BagIt](https://www.rfc-editor.org/rfc/rfc8493) bag beside it: every capture, card, ledger, report, and release, with a SHA-256 manifest. It refuses a bag name that exists (pass `--out` with another name), re-opens the bag it wrote, and prints the zip's SHA-256, which it also records in `exports.jsonl`. Hand the bag over, or archive it, and keep the digest apart from the zip.

Both manifests sit inside the zip. Checking the bag alone catches a missing, altered, or extra file, but not a rewrite of files together with both manifests:

```console
$ python3 <topic.py> export --check <bag.zip>
```

The digest catches that rewrite, because any change to the zip changes it:

```console
$ python3 <topic.py> export \
    --check <bag.zip> \
    --sha256 <digest>
```

The bag holds evidence and working material the scan does not cover (cards, raw captures, command logs, history), so treat it as private to the team that did the work.

## Output

Open with a one-line hero (`✓ Released <hash> to <who>` or `✓ Released <hash> to <who> on an offline check`, `✓ Bag <file>: <n> files, sha256 <digest>`, `⚠ Not released: <failing checks>`, `⚠ Not released: a release needs a live check and none ran; releasing on the captures alone is your call`, or for a check alone `✓ Ready: check ok` and `⚠ Not ready: <failing checks>`), then exactly these sections:

1. `## Check`: each check's result from this call, counts only; reasons and consequences go under `## Next`.
2. `## Trail`: the release, decision, or bag written, with its hash, or for a bag its SHA-256.
3. `## Next`: affected releases and decisions to revisit, or the fix `check` listed; at most three bullets.

Write the reply per `reply-contract.md`. A check-only run has no `## Trail`. When the check passed offline only, the panel offers release on the captures alone (`--offline --allow-offline`, the user's call), wait for network access and check again, and stop; `## Next` carries no options. Panel options otherwise: fix and check again, record the decision, export, stop.

```text
⚠ Not released: scan found 2 internal hosts at public audience

## Check

- Sources: 6 intact, 0 failed.
- Report: lint 0 warnings.
- Scan: 2 internal hosts at public audience.

## Trail

- Nothing written.

## Next

- Remove the hosts, then check again.
```
