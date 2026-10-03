# Assessments

An assessment answers a decision question against stated criteria: adopt or not, ready or not, which of three. It runs on the same topic folder, sources, and lifecycle as research; this file adds what research does not need.

## Frame it before collecting

Fill the `## Question` list and the `## Criteria` table in `index.md` before the first source:

- The decision, as a question with its options: "Adopt uv for the monorepo: adopt, trial, hold, or reject?" For a choice between products, the options are the products.
- Who decides, and by when, if known.
- The criteria, each with what a strong and a weak result look like. Three to seven; more means some are sub-criteria.
- What would make the decision obvious either way.

Criteria fixed after the evidence is in get bent to fit it. If a criterion has to change mid-assessment, log the change and the reason under `## Log`.

## Collect evidence of more than one kind

Record each source's kind with `add --kind`:

- **vendor**: the assessed product's own docs, README, changelog, or marketing.
- **independent**: a third party with no stake: a benchmark, an issue tracker, a postmortem, a review.
- **measured**: your own test, timing, or reproduction: save its command and output under `data/` and add it with `--kind measured --file <log>`, no URL needed.

For each criterion that decides the verdict, find at least one independent or measured source, and look for the strongest case against the option you are leaning toward. A criterion resting only on vendor sources has at most medium confidence. So does one resting on a single outside source: one measurement or one third-party report is a sample of one, and high confidence needs two.

## Rate each criterion

Keep the ratings in `data/criteria.csv`, one rating column per option you compare:

```text
criterion,weight,uv,pip-tools,confidence,sources,note
Lockfile reproducibility,3,strong,adequate,high,S2;S5;S9,One universal lockfile against one file per platform
Migration effort,2,adequate,strong,medium,S7,Three CI images need rebuilding
```

- Ratings: strong, adequate, weak, or unknown. Unknown is a finding.
- `confidence`: high, medium, or low, from how direct the evidence is and what kind it is.
- `sources`: source ids from `<run>/references/sources.jsonl`, semicolon-separated. A rating with no source is unknown.
- `note`: why the ratings differ. A note that admits the evidence is missing contradicts any rating but unknown.
- `weight` is optional. Do not sum weighted ratings into a single score; the verdict is a judgment the criteria support, and a decimal invites false precision.

For an adopt, trial, hold, or reject question about one product, a single `rating` column for that product is enough.

## The verdict

- One of the options named in the question, stated in the summary's first sentence, with the tally of ratings ("strong on 3 of 5 criteria, unknown on 1").
- The two or three criteria that decided it, and one line on why each losing option lost.
- Sensitivity: whether the verdict survives any one rating moving one grade, and which rating it hinges on.
- What would flip it: the specific evidence or threshold that would change the answer.
- Confidence, and the open question that most limits it.

## In the report

The options table (criteria against options) is the first finding. Each decisive criterion gets its own finding. Draw the table with `topic.py chart --csv data/criteria.csv --value uv --value pip-tools`: rating words map to 3, 2, 1, and 0, each option gets its own bar, and an unknown rating draws none.

`lint-report` on an assessment also checks that the report states its sensitivity and what would flip it, and that each rating in `data/criteria.csv` has a known source, no vendor-only high confidence, and no note contradicting it.

## On a rerun

`open` carries `data/criteria.csv` into the new run with the prior ratings. Re-rate from re-verified sources, and record each rating change under `## Since <prior date>` with the source that moved it.

## Output

Open with a one-line hero (`✓ <topic>: <verdict>, <confidence> confidence` or `⚠ Blocked: <reason>`), then exactly these sections, each copied from the run's files, never stated beyond them:

1. `## Verdict`: the option chosen, the criteria that decided it, why each losing option lost, the sensitivity, and what would flip it.
2. `## Criteria`: one line per criterion: the rating for each option, confidence, source ids and their kinds.
3. `## Open`: unknown ratings and open questions.
4. `## Run`: run directory and report path.

End with an `AskUserQuestion` panel (for example: fill the unknowns, verify sources, stop). Skip it in plan mode; without an interactive host, print the options as a numbered list.
