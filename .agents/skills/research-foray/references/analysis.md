# Analytic standard

How a finding earns its place, its confidence, and its wording. `lint-report` enforces the mechanical half; the rest is judgment against this file.

## Evidence before judgment

- Separate what a source says from what you conclude. A line reporting a source cites it; a judgment names the findings it rests on.
- One source reports; two independent sources corroborate. A vendor's own docs establish what the vendor claims, not that the claim holds.
- Trace a secondary source to its primary: cite the benchmark, not the post about it.
- When a claim can be tested cheaply, test it with `python3 <topic.py> run` instead of citing someone who asserted it.

## Confidence

Every finding and recommendation states one, with its reason:

- **High**: two or more independent or measured sources agree, and no recorded conflict stands against them.
- **Medium**: one outside source, vendor sources only, or a conflict weighed but not settled.
- **Low**: inference from indirect evidence, a single report, or a claim marked `[unverified]`.

Confidence grades the evidence. When a finding forecasts, also give its likelihood in words (almost certain, likely, roughly even, unlikely, remote), and keep the two apart.

## Conflicting evidence

When sources disagree:

1. Record it: `python3 <topic.py> conflict --run <run_dir> --source S3 --source S7 --about "<what they dispute>"`.
2. Under `## Conflicts`, open with one line citing every side (`1000 pages [S1] against 100 pages [S2]`), then set out each reading with its own id. Never drop the reading you lean against.
3. Weigh them by directness, independence, method, recency, and pin, and record the weight: `conflict --run <run_dir> --id C1 --weight S7 --why "<reason>"`.
4. Say what would settle it (`--settle`). An unweighed conflict is an open question and caps the findings it touches at medium.

## Alternatives and assumptions

- For the main judgment, name the strongest alternative explanation and the evidence against it.
- List the assumptions the answer rests on in Method. A finding that rests on one says so.

## Gaps and limits

- Log each search as you run it (`searched`): the log is how a reader reproduces the search and judges its coverage.
- Record what you could not retrieve, and why (`add --unretrieved`). Such a source is a gap, never a citation.
- Report an absence only when the search that would have found it is logged.

## Unverified claims

A load-bearing claim that no captured source supports moves to Open questions, or, when the report needs it, carries `[unverified]` in place of a source id. It is never high confidence, and a summary over unverified claims says so. Many markers mean the work needs more retrieval, not more markers.

## Synthesis

- Organize findings by theme, never source by source. Each finding draws on every source that bears on it.
- Count agreement: "3 of 4 sources", "both measurements".
- Quote figures, dates, and names as the source states them.

## Recommendations

`## Recommendations` lists actions in priority order. Each names the action, cites the sources of the findings it follows from, states its confidence, and says what would change it. A recommendation never carries more confidence than the findings it rests on.
