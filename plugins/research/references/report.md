# Report standard

How a research or assessment report is laid out, and the checks it passes before it ships. `topic.py lint-report` enforces the mechanical half; the rest is judgment against this file.

## Writing it

1. Read `index.md`, every card, and the prior run's report when there is one. With no topic named, use the most recently updated topic from `status.md`. Read `analysis.md`.
2. Decide the answer before writing. It becomes the title and the summary's first sentence.
3. Rank the findings by how much the answer depends on them; the first finding carries the most weight. Group by theme across sources, never one finding per source.
4. Draw each exhibit from `data/` with `python3 <topic.py> chart --csv <run_dir>/data/<name>.csv --out <run_dir>/charts/<name>.svg`, and embed it as `![<takeaway>](charts/<name>.svg)`.
5. Write `report.md` in today's run, ending with an empty `## Sources` heading. When the newest run is dated before today, open today's run per `continue.md` step 2; only `--resume` keeps writing in the earlier run. A rerun writes a new report in the new run; the earlier one stays where it is. A resumed run keeps the previous version under `history/`.
6. Run `python3 <topic.py> verify --run <run_dir>` after the last `add`, then write the Sources table instead of typing it: `python3 <topic.py> sources --write --run <run_dir>` fills the report's `## Sources` section.
7. After the last edit, run `python3 <topic.py> claims --reviewed <run_dir>/report.md` and check every cited line against its quotes, per `verify.md` step 3. `--reviewed` logs the check against this exact version of the report; editing it again means checking again.
8. Run `python3 <topic.py> check --run <run_dir>` and quote its result.

## Shape

Fixed order. The reader gets the answer in the first screen and the evidence after it.

1. **Title states the answer, and no more than the findings support.** `# WAL suits our read-heavy service`, not `# SQLite research`, and not "the problem is solved" over an adequate rating.
2. **Meta line.** Date, `<namespace>/<topic>`, mode, audience. One line.
3. **`## Summary`.** At most 150 words. The answer, the two to four numbers that carry it, the recommendation or verdict, and how confident you are. An assessment states the tally of ratings. When findings carry `[unverified]` claims, say so. No links and no source ids: the summary is read, the findings are checked.
4. **`## Findings`.** One `###` per finding, each heading a full-sentence takeaway without a closing period. Prose first, a table when the data is tabular. Every claim cites a source id (`[S3]`) whose recorded quote says it, or carries `[unverified]`. Each finding ends with its confidence and why (`Confidence: medium, one independent benchmark.`), graded per `analysis.md`.
5. **`## Recommendations`.** When the question calls for action: a numbered list in priority order, each with the action, the source ids of the findings behind it, its confidence, and what would change it.
6. **`## Conflicts`.** When sources disagree: each recorded conflict as one line citing every side, then each reading with its id, which carries more weight and why, and what would settle it.
7. **`## Since <prior date>`.** Carried runs only: what changed, what was re-verified, what went stale.
8. **`## Open questions`.** Each with the data or source that would settle it.
9. **`## Method`.** Scope, what was read and what was skipped and why, the sources that could not be retrieved, the assumptions the answer rests on, and how each number was computed (the `run` that produced it, or formula plus inputs).
10. **`## Exhibits`.** Charts, one message each, titled with the takeaway, each with its data file and source ids beneath. Omit the section when there are no numbers to draw; do not chart a table of words.
11. **`## Sources`.** What `topic.py sources --write` puts there: the sources table (id, linked title, author, kind, ref, retrieved, capture, and state), then the search log.

Assessments add a verdict line to the summary and a criteria table as the first finding. See `assessment.md`.

## A client cut

For a reader who decides and moves on, add `brief.md` beside the report: the title, the summary, the one number or options table that decides it, what would flip it, and a link to `report.md`. It carries no new claims, so it needs no citations of its own. Keep `## Since` and its retractions in the full report.

## Numbers

- Every figure has a unit, a denominator, and a date window: "41 of 52 PRs (79%), 2026-04-01..2026-06-30".
- A point estimate carries its range when one exists.
- A number you cannot source goes under Open questions, not into a finding.

## Exhibits

- Draw from a CSV under `data/` with `topic.py chart` (`--csv` and `--out` are required), so the chart can be redrawn and the numbers re-checked.
- Bars for comparisons, lines for change over time. No pie charts, no 3D, no dual axes.
- One unit per chart: pass `--value` for the column to draw, and split values in different units into separate charts.
- The title is the takeaway ("Review latency fell by two thirds after rollout"), not the metric name.

## Audience

`scan` runs at the run's audience before a report ships. It covers what ships: the report, `index.md`, and other authored markdown, CSV, SVG, and text files. The Sources section `sources --write` generates is scrubbed for the audience; the ledgers keep what was recorded. Source cards under `<run>/references/` and report snapshots under `history/` are working notes, skipped unless `--include-references` is given; keep them out of anything you publish.

The audience is who can read the report where it ends up, not who it is addressed to. A report sent to one team but stored or forwarded where more people read it takes the wider audience; a narrow recipient never lowers it.

- **private**: no local paths or emails in authored files.
- **internal**: also no personal names; roles instead ("a senior engineer").
- **public**: also no organization, repository, team, or ticket identifiers and no internal URLs. Aggregates and ranges only.

## Prose

Write for a reader who was not there and will judge the report by whether they can disagree with it.

- Keep tool vocabulary (warnings, flags, script and command names) out of the Summary and Findings; Method may name the commands that produced a number.

## Before it ships

- `python3 <topic.py> check --run <run_dir>` returns `ok: true` in this session. It re-verifies every source, compares the Sources table with the manifest, runs `lint-report --strict`, and runs `scan` at the run's audience.
- `lint-report` checks the report's shape (answer title, Summary first, section order, no links or ids in the summary) and that every `[S#]` is in the manifest. `--strict` also fails its warnings: source, citation, pin, confidence, conflict, and claims-review gaps, label headings, and prose patterns. Its output names each failure.
- The summary, read alone, answers the question.
- Reread the report against the prose rules.

## Output

Open with a one-line hero (`✓ <report path>: <n> findings, <n> sources, check ok` (`check ok, offline` when `check` ran with `--offline`) or `⚠ Not shippable: <failing checks>`), then exactly these sections:

1. `## Answer`: the report's title and summary, verbatim.
2. `## Checks`: the `check` result from this session, each gate with its counts.

Panel options: verify sources, tighten the prose, stop.
