# Verify a topic

Three checks, in this order: the references still say what you cite them for, no source you should have used is missing, and the report reads cleanly. `<run_dir>` is the newest run that `python3 <topic.py> prior --topic <topic>` lists. When it is dated before today, verify never rewrites it: run the read-only checks (`verify`, `links`, `claims` without `--reviewed`, `lint-report`, `check`), which append only to `<run_dir>/references/checks.jsonl`, list every fix they call for, and offer `continue` to make the fixes in today's run. Steps below that add sources, log searches, edit the report, or pass `--reviewed` apply only to a run dated today. With no topic named, run `status.md` and verify the topic with failed or unverified sources.

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

- **unverifiable**: the capture is a PDF and a quote rests on it. `topic.py` does not extract PDF text, so no quote can be matched. Paste the text you read into a `.txt` file and add it with `--file`, saying in its card that it is your extraction of the PDF, or find the same material in an HTML or text source; until then the claim carries `[unverified]`.
- **unreachable**: an auth wall or server error. Report it as unchecked, not as passing.

A re-add of the same URL with `--quote` adds that passage to the ones recorded, as a new version under the same id. Name a retired id in `## Since` as history (`S11 became [S20]`); everywhere else, cite the id that replaced it.

Never swap in a different source that happens to support the same claim without saying so. Record every replacement and retraction under `## Since <prior date>`, or under `## Log` in a first run, with the old and new source ids.

## 2. Missed sources

- `python3 <topic.py> links --run <run_dir>` lists URLs your captures cite that the manifest lacks. Open the frequent ones.
- Every claim in the report's findings cites a source id; a claim without one is either sourced now or moved to open questions.
- Trace secondary sources to their primaries: a blog citing a benchmark means the benchmark is the source.
- Search once more for the strongest disagreeing source (the host may ask approval for the search tool), and log the search with `topic.py searched`. An analysis that met no counter-evidence has not looked.
- In an assessment, each criterion that decides the verdict needs at least one independent or measured source.

Add what you find with `topic.py add`. Where it disagrees with a source you already cite, record the conflict and set it out per `analysis.md`.

## 3. Claims and readability

```console
$ python3 <topic.py> claims --reviewed <run_dir>/report.md
```

Run it last: after `verify`, after `sources --write` refreshes the Sources table, and after your final edit, since `--reviewed` covers one version of the report. `claims` lists every line that cites a source with the quotes each cited source records, and every `[unverified]` line. Read each pair: the quote must say what the line claims. Read each unverified line: source it now if you can. Where it does not, find the passage that does with `python3 <topic.py> find --run <run_dir> "<words>"` and add it (`add` with `--quote`), cite a source that says it, or move the claim to Open questions. No script can judge that a quote supports a claim; `--reviewed` records that you did, for this exact version of the report.

```console
$ python3 <topic.py> lint-report --strict <run_dir>/report.md
```

Then read the summary alone, as the reader will. It should answer the question and stand without the findings, and its title should claim no more than its findings and ratings support. Check the report against the prose rules.

Finish with `python3 <topic.py> check --run <run_dir>` and quote its result. Add `--offline` when the request did: a check without it fetches every URL and writes `unreachable` rows to `checks.jsonl`.

## 4. Keep it fresh

`status` names each released report a failed check touches, and the decisions taken on it; continue the topic to correct it.

## Output

Open with a one-line hero. After the final `check`: `✓ <n> sources checked, all ok` (`✓ <n> sources checked offline, all ok` when `--offline`) only when `check` returned `ok: true`; otherwise `⚠ <n> failed: <counts by status>` or, when every source passed but the report check failed, `⚠ Not ready: <failing checks>`. Then exactly these sections:

1. `## References`: each failure: source id, status, what was done about it.
2. `## Missed`: sources found and added, conflicts recorded, and leads not yet followed.
3. `## Report`: the final `check` result from this session, unsupported claims and overreaching titles with what was done, and the fixes still needed.

Write per `prose-rules.md`: plain bullets, no bold labels, no sentence between the hero and the first section, no sentence narrating your own edits ("I added…"), no finding recaps.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
⚠ 2 failed: 1 changed, 1 vanished

## References

- S2 changed: replaced by S9 at the new tag.
- S4 vanished: marked unretrieved; the claim it supported moved to Open questions.

## Missed

- Added S10, a third-party benchmark; recorded its disagreement with S2 as a conflict.

## Report

- Check failing: 1 unsupported claim in Findings, 1 stale Sources row.
- Fix: source or drop the claim, then run `sources --write`.
```

Report only what changed in the sources and report; do not describe what this pass left untouched. Panel options: fix the failures, continue the topic, stop. The panel never repeats `## Report`; without an interactive host, print the options as a numbered list.
