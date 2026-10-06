# Check, release, decide, export

What happens between a finished report and the people who act on it. `<run_dir>` is the run that holds the report, usually the newest. These steps record what became of that run's own report, so they write into it even when it is dated before today; they never change its report, sources, or captures.

## 1. Check, fresh

```console
$ python3 <topic.py> check --run <run_dir>
```

`check` reruns every ship check in one call: each source against its capture and live URL, the report's Sources table against the manifest, `lint-report --strict`, and the leak scan. `ok: true` is the only evidence that a report is ready.

When it fails, `next` lists the fixes in order. The usual loop: fix, `sources --write`, `claims --reviewed`, then `check` again. When `<run_dir>` is dated before today, do not fix its report in place: continue the topic per `continue.md` and release from today's run. Without network, `--offline` checks the captures only and says so in its output.

## 2. Release

```console
$ python3 <topic.py> release \
    --run <run_dir> \
    --to "<who receives it, as a role or group>"
```

`release` runs the same checks and refuses on any failure. On a pass it keeps the exact report (and `brief.md`, when there is one) under `releases/`, named by its hash, and appends to `<run_dir>/references/releases.jsonl`: when, to whom, at which audience, the report's sha256, and which version of each cited source it rested on. Name recipients by role at internal and public audiences.

## 3. Decide

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

`status` lists the latest release to each reader whose cited sources have since changed, failed a check, or been retired, with the decisions taken on it. When one appears: continue the topic, re-verify, and release a corrected report to the same readers, naming what changed; that release clears the flag. Then revisit each listed decision against its `revisit` condition.

## 5. Export

```console
$ python3 <topic.py> export --run <run_dir>
```

`export` packs the whole run into a zipped [BagIt](https://www.rfc-editor.org/rfc/rfc8493) bag beside it: every capture, card, ledger, report, and release, with a SHA-256 manifest. Hand the bag over, or archive it. Anyone can check that nothing in it changed since:

```console
$ python3 <topic.py> export --check <bag.zip>
```

The bag holds evidence and working material the scan does not cover (cards, raw captures, command logs, history), so treat it as private to the team that did the work.

## Output

Open with a one-line hero (`✓ Released <hash> to <who>`, `✓ Bag <file>: <n> files`, or `⚠ Not released: <failing checks>`), then exactly these sections:

1. `## Check`: each check's result from this call, verbatim counts.
2. `## Trail`: the release, decision, or bag written, with its hash.
3. `## Next`: affected releases and decisions to revisit, or the fix `check` listed.

Panel options: fix and check again, record the decision, export, stop.
