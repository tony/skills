# Report standard

How a research or assessment report is laid out, and the checks it passes before it ships. `topic.py lint-report` enforces the mechanical half; the rest is judgment against this file. `<topic.py>` is the script path from the skill that sent you here.

## Writing it

1. Read `index.md`, every card, and the prior run's report when there is one. With no topic named, use the most recently updated topic from `status.md`.
2. Decide the answer before writing. It becomes the title and the summary's first sentence.
3. Rank the findings by how much the answer depends on them; the first finding carries the most weight.
4. Draw each exhibit from `data/` with `python3 <topic.py> chart`, and embed it as `` ![<takeaway>](charts/<name>.svg) ``.
5. Run `python3 <topic.py> verify --run <run_dir>` after the last `add`, then write the Sources table instead of typing it: `python3 <topic.py> sources --write --run <run_dir>` replaces the report's `## Sources` section.
6. Write `report.md` in today's run. When the newest run is dated before today, open today's run per `continue.md` step 2; only `--resume` keeps writing in the earlier run. A rerun writes a new report in the new run; the earlier one stays where it is. A resumed run keeps the previous version under `history/`.
7. After the last edit, run `python3 <topic.py> claims --reviewed <run_dir>/report.md` and check every cited line against its quotes, per `verify.md` step 3. `--reviewed` logs the check against this exact version of the report; editing it again means checking again.

## Shape

Fixed order. The reader gets the answer in the first screen and the evidence after it.

1. **Title states the answer, and no more than the findings support.** `# WAL suits our read-heavy service`, not `# SQLite research`, and not "the problem is solved" over an adequate rating.
2. **Meta line.** Date, `<namespace>/<topic>`, mode, audience. One line.
3. **`## Summary`.** At most 150 words. The answer, the two to four numbers that carry it, the recommendation or verdict, and how confident you are. An assessment states the tally of ratings. No links and no source ids: the summary is read, the findings are checked.
4. **`## Findings`.** One `###` per finding, each heading a full-sentence takeaway without a closing period. Prose first, a table when the data is tabular. Every claim cites a source id (`[S3]`) whose recorded quote says it. Research findings end with what to do: the setting, size, or step, with the number when the sources give one.
5. **`## Since <prior date>`.** Carried runs only: what changed, what was re-verified, what went stale.
6. **`## Open questions`.** Each with the data or source that would settle it.
7. **`## Method`.** Scope, what was read and what was skipped and why, how each number was computed (command plus output, or formula plus inputs).
8. **`## Exhibits`.** Charts, one message each, titled with the takeaway, each with its data file and source ids beneath. Omit the section when there are no numbers to draw; do not chart a table of words.
9. **`## Sources`.** The table `topic.py sources --write` puts there: id, linked title, author, kind, ref, retrieved, capture, and state.

Assessments add a verdict line to the summary and a criteria table as the first finding. See `assessment.md`.

## A client cut

For a reader who decides and moves on, add `brief.md` beside the report: the title, the summary, the one number or options table that decides it, what would flip it, and a link to `report.md`. It carries no new claims, so it needs no citations of its own. Keep `## Since` and its retractions in the full report.

## Numbers

- Every figure has a unit, a denominator, and a date window: "41 of 52 PRs (79%), 2026-04-01..2026-06-30".
- A point estimate carries its range when one exists.
- A number you cannot source goes under Open questions, not into a finding.

## Exhibits

- Draw from a CSV under `data/` with `topic.py chart`, so the chart can be redrawn and the numbers re-checked.
- Bars for comparisons, lines for change over time. No pie charts, no 3D, no dual axes.
- One unit per chart: pass `--value` for the column to draw, and split values in different units into separate charts.
- The title is the takeaway ("Review latency fell by two thirds after rollout"), not the metric name.

## Audience

`scan` runs at the run's audience before a report ships. It covers what ships: the report, `index.md`, and other authored markdown, CSV, SVG, and text files. Source cards under `<run>/references/` and report snapshots under `history/` are working notes, skipped unless `--include-references` is given; keep them out of anything you publish.

- **private**: no local paths or emails in authored files.
- **internal**: also no personal names; roles instead ("a senior engineer").
- **public**: also no organization, repository, team, or ticket identifiers and no internal URLs. Aggregates and ranges only.

## Prose

Write for a reader who was not there and will judge the report by whether they can disagree with it.

- Lead with the point. Active voice, concrete nouns, direct verbs.
- Name the source or cut the claim. "Studies show" and "experts agree" do not survive.
- Cut: delve, leverage, utilize, robust, seamless, comprehensive, cutting-edge, transformative, game changer, paradigm shift, tapestry, realm, pivotal, testament, it's worth noting, in today's world, in conclusion, ultimately.
- Cut patterns: binary contrasts ("not X, it's Y"), colon reveals ("The best part: it learns"), faux-insight setups ("what most people miss"), importance puffery ("marks a pivotal moment"), trailing `-ing` analysis ("highlighting its commitment"), summary-recap endings, em-dash clusters, emoji in headings, decorative bold.
- End on the last concrete point or the next action.
- Keep tool vocabulary (warnings, flags, script and command names) out of the Summary and Findings; Method may name the commands that produced a number.

Patterns adapted from AGENTS.md § AI Slop Prevention and [no-ai-slop v1.0.6](https://github.com/petergyang/no-ai-slop/blob/v1.0.6/SKILL.md).

## Before it ships

- `python3 <topic.py> lint-report --strict <run_dir>/report.md` exits zero. It checks the answer title, Summary first, standard section order, no links or ids in the summary, and every `[S#]` in the manifest; `--strict` also fails on absolute titles, uncited, unquoted, uncaptured, unpinned, or placeholder-address sources, a Findings line that shares no words with its source's quotes, a missing claims review, label headings, and the prose patterns above.
- `python3 <topic.py> scan --run <run_dir>` exits zero at the run's audience.
- The summary, read alone, answers the question.
- Invoke the `lean:lean-writing` skill on the report when it is installed; otherwise reread it against the Prose rules above.

## Output

Open with a one-line hero (`✓ <report path>: <n> findings, <n> sources` or `⚠ Not shippable: <n> lint errors`), then exactly these sections:

1. `## Answer`: the report's title and summary, verbatim.
2. `## Checks`: lint-report and scan results.

End with an `ask-user-choice` panel (for example: verify sources, tighten the prose, stop). Skip it in plan mode; without an interactive host, print the options as a numbered list.
