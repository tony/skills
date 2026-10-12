# Verify a topic

Three checks, in this order: the references still say what you cite them for, no source you should have used is missing, and the report reads cleanly. `<run_dir>` is the newest run that `python3 <topic.py> prior --topic <topic>` lists. When `topic.py` refuses a write because the run was last opened before today (`layout.md`, Reruns), run only the read-only checks (`verify`, `links`, `claims` without `--reviewed`, `lint-report`, `check`), list every fix they call for, and offer `continue` to make the fixes in today's run. Steps below that add sources, log searches, edit the report, or pass `--reviewed` apply only to a run open for writing today. With no topic named, run `status.md` and verify the topic with failed or unverified sources.

## 1. References

```console
$ python3 <topic.py> verify --run <run_dir>
```

`--offline` checks only the captures on disk: present, unaltered, quotes still inside. Without it, each URL is also fetched. Results append to `<run>/references/checks.jsonl`; the command exits 1 when any check fails. Each result leaves the source in a state that `layout.md` (Source states) defines; only a live pass that compared content makes it verified.

Handle each failure by its status:

- **moved**: add the source at its new URL with `--replaces <old id>`, then update the report's citations.
- **vanished**: find the same material at a pinned location (an archive, a release tag) and add it with `--replaces <old id>`, or retract the claims that rested on it.
- **changed**: read the new version and re-capture it (`add --fetch` with the same URL and ref). Keep the id; revise claims it no longer supports, and pass `--set-quotes` with a `--fields` file holding passages from the new capture.
- **misquoted**: the quote is not where you said it is. Re-add with `--set-quotes` and a `--fields` file holding the passage as it appears, or revise the claim.
- **unverifiable**: the capture is a PDF and a quote rests on it. `topic.py` does not extract PDF text, so no quote can be matched. Paste the text you read into a `.txt` file and add it with `--file`, saying in its card that it is your extraction of the PDF, or find the same material in an HTML or text source; until then the claim carries `[unverified]`.
- **unreachable**: an auth wall or server error. Report it as unchecked, not as passing.
- **reachable**: not a failure, and not evidence for a claim. Re-add the source with `--fetch` or with a quote so a later pass compares content.

A re-add of the same URL with a quote (`add --fields <file>`, per `start.md` step 4) adds that passage to the ones recorded, as a new version under the same id. Name a retired id in `## Since` as history (`S11 became [S20]`); everywhere else, cite the id that replaced it.

Never swap in a different source that happens to support the same claim without saying so. Record every replacement and retraction under `## Since <prior date>`, or under `## Log` in a first run, with the old and new source ids.

## 2. Missed sources

- `python3 <topic.py> links --run <run_dir>` lists URLs your captures cite that the manifest lacks. Open the frequent ones, and record one with `add --link S<n>:<k>` from its `from` field, never by pasting the URL into a command.
- Every claim in the report's findings cites a source id; a claim without one is either sourced now or moved to open questions.
- Trace secondary sources to their primaries: a blog citing a benchmark means the benchmark is the source.
- Search once more for the strongest disagreeing source (the host may ask approval for the search tool), and log the search with `topic.py searched`. An analysis that met no counter-evidence has not looked.
- In an assessment, each criterion that decides the verdict needs at least one independent or measured source.

Add what you find with `topic.py add`. Where it disagrees with a source you already cite, record the conflict and set it out per `analysis.md`.

## 3. Claims and readability

Run the report pipeline in `report.md` steps 6 to 8 (`prepare`, review the claims, `claims --reviewed`, `check`), starting again at `prepare` after any edit. On a run that is read-only today, run `claims` without `--reviewed` and list the fixes.

```console
$ python3 <topic.py> lint-report --strict <run_dir>/report.md
```

Then read the summary alone, as the reader will. It should answer the question and stand without the findings, and its title should claim no more than its findings and ratings support. Check the report against the prose rules.

Finish with `check` per `release.md` step 1 and quote its result. In its output, `brief` lists what `brief.md` adds to the report, and `search_gaps` lists failed searches not since rerun: rerun each, or list it under Open questions.

## 4. Keep it fresh

`status` names each released report a failed check touches, and the decisions taken on it; continue the topic to correct it.

## Output

Open with a one-line hero. After the final `check`: `✓ <n> sources checked, all ok` (`✓ <n> sources checked offline, all ok` when `--offline`) only when `check` returned `ok: true`; otherwise `⚠ Not ready: <n> sources failed (<counts by status>)` or, when every source passed but the report check failed, `⚠ Not ready: <failing checks>`. Then exactly these sections:

1. `## References`: each failure: source id, status, what was done about it.
2. `## Missed`: sources found and added, conflicts recorded, and leads not yet followed.
3. `## Report`: the final `check` result from this session, unsupported claims and overreaching titles with what was done, and the fixes still needed.

Write the reply per `reply-contract.md`.

```text
⚠ Not ready: 2 sources failed (1 changed, 1 vanished)

## References

- S2 changed: replaced by S9 at the new tag.
- S4 vanished: marked unretrieved; the claim it supported moved to Open questions.

## Missed

- Added S10, a third-party benchmark; recorded its disagreement with S2 as a conflict.

## Report

- Check failing: 1 unsupported claim in Findings, 1 stale Sources row.
- Fix: source or drop the claim, then run `sources --write`.
```

Report only what changed in the sources and report; do not describe what this pass left untouched. Panel options: fix the failures, continue the topic, stop.
