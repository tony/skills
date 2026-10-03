# Verify a topic

Three checks, in this order: the references still say what you cite them for, no source you should have used is missing, and the report reads cleanly. `<topic.py>` is the script path from the skill that sent you here; `<run_dir>` is the newest run that `python3 <topic.py> prior --topic <topic>` lists. When that run is dated before today, open today's run per `continue.md` step 2 and check there; only `--resume` keeps writing in the earlier run. With no topic named, run `status.md` and verify the topic with failed or unverified sources.

## 1. References

```console
$ python3 <topic.py> verify --run <run_dir>
```

`--offline` checks only the captures on disk: present, unaltered, quotes still inside. Without it, each URL is also fetched. Results append to `<run>/references/checks.jsonl`; the command exits 1 when any check fails. A live pass makes a source verified; an offline pass leaves it intact; a source with no capture stays unchecked offline, because there is nothing to compare its claim against.

Handle each failure by its status:

- **moved**: add the source at its new URL with `--replaces <old id>`, then update the report's citations.
- **vanished**: find the same material at a pinned location (an archive, a release tag) and add it with `--replaces <old id>`, or retract the claims that rested on it.
- **changed**: read the new version and re-capture it (`add --fetch` with the same URL and ref). Keep the id; revise claims it no longer supports, and pass `--set-quotes` with passages from the new capture.
- **misquoted**: the quote is not where you said it is. Re-add with `--set-quotes` and the passage as it appears, or revise the claim.

A re-add of the same URL with `--quote` adds that passage to the ones recorded, as a new version under the same id. Name a retired id in `## Since` as history (`S11 became [S20]`); everywhere else, cite the id that replaced it.
- **unreachable**: an auth wall or server error. Report it as unchecked, not as passing.

Never swap in a different source that happens to support the same claim without saying so. Record every replacement and retraction under `## Since <prior date>`, or under `## Log` in a first run, with the old and new source ids.

For a scholar study (a `terms.jsonl` beside the run), run the `scholar-verify` skill for its term citations.

## 2. Missed sources

- `python3 <topic.py> links --run <run_dir>` lists URLs your captures cite that the manifest lacks. Open the frequent ones.
- Every claim in the report's findings cites a source id; a claim without one is either sourced now or moved to open questions.
- Trace secondary sources to their primaries: a blog citing a benchmark means the benchmark is the source.
- Search once more for the strongest disagreeing source. An analysis that met no counter-evidence has not looked.
- In an assessment, each criterion that decides the verdict needs at least one independent or measured source.

Add what you find with `topic.py add`.

## 3. Claims and readability

```console
$ python3 <topic.py> claims --reviewed <run_dir>/report.md
```

Run it last: after `verify`, after `sources --write` refreshes the Sources table, and after your final edit, since `--reviewed` covers one version of the report. `claims` lists every line that cites a source and the quotes each cited source records. Read each pair: the quote must say what the line claims. Where it does not, find the passage that does with `python3 <topic.py> find --run <run_dir> "<words>"` and add it (`add` with `--quote`), cite a source that says it, or move the claim to Open questions. No script can judge that a quote supports a claim; `--reviewed` records that you did, for this exact version of the report.

```console
$ python3 <topic.py> lint-report --strict <run_dir>/report.md
```

Then read the summary alone, as the reader will. It should answer the question and stand without the findings, and its title should claim no more than its findings and ratings support. Check the report against `report.md`'s prose rules, and invoke the `lean:lean-writing` skill on it when installed.

## 4. Keep it fresh

A delivered report goes stale as its sources move. Rerun `verify` on a schedule (a cron job or the host's scheduler), and continue the topic when a check fails.

## Output

Open with a one-line hero (`✓ <n> sources checked, all ok` or `⚠ <n> failed: <counts by status>`), then exactly these sections:

1. `## References`: each failure: source id, status, what was done about it.
2. `## Missed`: sources found and added, and leads not yet followed.
3. `## Report`: lint-report findings and fixes.

End with an `ask-user-choice` panel (for example: fix the failures, continue the topic, stop). Skip it in plan mode; without an interactive host, print the options as a numbered list.
