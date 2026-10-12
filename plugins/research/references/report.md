# Report standard

How a research or assessment report is laid out, and the checks it passes before it ships. `topic.py lint-report` enforces the mechanical half; the rest is judgment against this file.

## Contents

- Writing it
- Shape
- A client cut
- Numbers
- Exhibits
- Audience
- Prose
- Before it ships
- Output

## Writing it

1. Read `index.md`, every card, and the prior run's report when there is one. With no topic named, use `recent` from `status`. Read `analysis.md`.
2. Decide the answer before writing. It becomes the title and the summary's first sentence.
3. Rank the findings by how much the answer depends on them; the first finding carries the most weight. Group by theme across sources, never one finding per source.
4. Draw each exhibit from `data/` with `python3 <topic.py> chart --csv <run_dir>/data/<name>.csv --out <run_dir>/charts/<name>.svg --title "<takeaway>"`, and embed it as `![<takeaway>](charts/<name>.svg)`.
5. Write `report.md` in today's run, ending with an empty `## Sources` heading. A rerun writes a new report in the new run; the earlier one stays where it is. A resumed run keeps the previous version under `history/`.
6. After the last `add` and the last edit, run `python3 <topic.py> prepare --run <run_dir>`: it verifies every source, then writes the report's `## Sources` section instead of you typing it. Add `--offline` when the request says there is no network.
7. Run `python3 <topic.py> claims <run_dir>/report.md`. It lists every line that cites a source with the quotes each cited source records, and every `[unverified]` line. Read each pair: the quote must say what the line claims. Read each unverified line and source it now if you can: find the passage with `python3 <topic.py> find --run <run_dir> "<words>"` and add it (`add` with `--quote`), cite a source that says it, or move the claim to Open questions. No script judges that a quote supports a claim. Once you have read every pair, run `claims --reviewed` on the same file: it logs your own read against this exact version of the report, and any edit means starting again at step 6.
8. Run `python3 <topic.py> check --run <run_dir>` and quote its result. When it fails, `first_failing` names the first prerequisite that failed (verify, sources, claims, lint, redact, or scan) and `next` lists the fixes in order; resume the pipeline at that step.

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
11. **`## Sources`.** What `topic.py sources --write` puts there: the sources table (id, linked title, author, kind, ref, retrieved, capture, and check), then the search log. The Check column folds verified and intact into `checked` and reachable into `unchecked`, so it reads the same after an offline check and a live one; `status` and `check` keep the finer states.

Assessments add a verdict line to the summary and a criteria table as the first finding. See `assessment.md`.

## A client cut

For a reader who decides and moves on, add `brief.md` beside the report: the title, the summary, the one number or options table that decides it, what would flip it, and a link to `report.md`. It adds no claim: it cites only sources the report cites, and `check` fails on a `[S#]` that `report.md` lacks (`brief-citation`) or on an uncited sentence of four or more words that does not appear in the report (`brief-new-claim`). Copy its sentences from the report. `claims` also lists the brief's cited lines, and `claims --reviewed` covers report and brief together, so edit neither after the review. Keep `## Since` and its retractions in the full report.

## Numbers

- Every figure has a unit, a denominator, and a date window: "41 of 52 PRs (79%), 2026-04-01..2026-06-30".
- A point estimate carries its range when one exists.
- A number you cannot source goes under Open questions, not into a finding.
- Put two figures side by side only when they share a build, a setting, and a date window, and name those in the finding.

## Exhibits

- Draw from a CSV under `data/` with `topic.py chart` (`--csv` and `--out` are required), so the chart can be redrawn and the numbers re-checked.
- Bars for comparisons, lines for change over time. No pie charts, no 3D, no dual axes.
- One unit per chart: pass `--value` for the column to draw, and split values in different units into separate charts.
- The title is the takeaway ("Review latency fell by two thirds after rollout"), not the metric name.

## Audience

`check` runs `scan` at the run's audience before a report ships. It reads the `.md`, `.txt`, `.csv`, and `.svg` files under the run line by line, with the `redact:` line of `index.md` blanked so the list does not flag itself. It skips `raw/` always, and skips source cards under `references/`, `history/`, and `releases/` unless `--include-references` is given; keep those out of anything you publish. It does not read `.log`, `.json`, or `.jsonl` files, so command logs and ledgers keep what was recorded. The Sources section `sources --write` generates is scrubbed for the audience.

A public run also needs its `redact` decision recorded: set `redact` in the `index.md` frontmatter yourself to a list of names to hide, or to `[]` when there are none. `check` reports `redact_decision` as `missing` and fails at `redact` until you do.

The audience is who can read the report where it ends up, not who it is addressed to. A report sent to one team but stored or forwarded where more people read it takes the wider audience; a narrow recipient never lowers it.

- **every audience**: scan flags home paths, emails, and secrets (GitHub `ghp_`, `gho_`, and `github_pat_` tokens, AWS `AKIA` keys, Slack `xox[abpr]-` tokens, private-key headers).
- **internal**: also the names on the run's `redact` list (`redact:` in `index.md`, or `scan --redact`). Use roles ("a senior engineer") for everyone else.
- **public**: also internal hosts (`.internal`, `.corp`, `.local`, `.lan`, `.intranet`, `.home.arpa`, `localhost`, and private, loopback, and link-local IPv4 addresses) and ticket ids outside code fences. Aggregates and ranges only.

Scan does not find organization, team, or repository names. Put each one in the `redact` list, or the scan is clean over a report that names them.

## Prose

Write for a reader who was not there and will judge the report by whether they can disagree with it.

- Keep tool vocabulary (warnings, flags, script and command names) out of the Summary and Findings; Method may name the commands that produced a number.

## Before it ships

- `python3 <topic.py> check --run <run_dir>` passes. It re-verifies every source, compares the Sources table with the manifest, runs `lint-report --strict`, and runs `scan` at the run's audience.
- `lint-report` checks the report's shape (answer title, Summary first, section order, no links or ids in the summary) and that every `[S#]` is in the manifest. `--strict` also fails its warnings: source, citation, pin, confidence, conflict, and claims-review gaps, label headings, and prose patterns. Its output names each failure.
- The summary, read alone, answers the question.
- Reread the report against the prose rules.

## Output

Open with a one-line hero, with `<n> findings` and `<n> sources` copied from `check`'s `counts`: `✓ <namespace>/<topic> <date>: <n> findings, <n> sources, check ok` (`check ok, offline` when `check` ran with `--offline`) or `⚠ Not ready: <failing checks>`. Then exactly these sections:

1. `## Answer`: the report's title and summary, verbatim.
2. `## Checks`: the `check` result from this session, each gate with its counts, and nothing else.
3. `## Open`: open questions and unresolved conflicts, one line each; omit when none.

Write the reply per `reply-contract.md`.

```text
✓ research/sqlite-wal 2026-07-14: 5 findings, 6 sources, check ok

## Answer

# WAL mode suits a single-host service with many readers

Readers do not block the writer, and checkpoints are the one stall to plan for. Confidence is medium.

## Checks

- Sources: 6 intact, 0 failed.
- Report: lint 0 warnings; scan clean at private; claims reviewed by the agent.

## Open

- Whether WAL holds up on network filesystems.
```

Panel options: verify sources, tighten the prose, stop.
