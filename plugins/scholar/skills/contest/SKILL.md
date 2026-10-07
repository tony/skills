---
name: contest
description: "Adversarially judge a distilled ontology one candidate at a time — synonymy, polysemy, orphans, circular evidence, and coverage"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[--out=<dir>] [--rounds=<n>] [--panel]"
user-invocable: true
disable-model-invocation: true
---


# /scholar:contest

Stage 4. Attack the ontology. Four passes, serial by default: one judge, one
candidate at a time, every verdict traceable to the evidence that settled it.

Read `../../references/evidence-tiers.md` before recording any number, and
`../../references/citation.md` for the circularity rule that applies in every
pass. The analyzer
is `../../scripts/term_metrics.py`; `<analyzer>` below is its absolute path
resolved from this skill's directory.

User arguments: $ARGUMENTS

## Pass 1 — mechanical

Run the analyzer:

```console
$ python3 <analyzer> notes/ontology/<subject>/
```

It reports synonymy candidates, polysemy candidates, orphans, circular
evidence, and fan-out per type.

The analyzer proposes; it never decides. A high similarity score is a
question (*are these one concept?*), not an answer. Record the number in
`evidence/metrics.md`, per the evidence tiers, with a command a third party
can paste: the study-relative form, never the absolute `<analyzer>` path.

```console
$ python3 term_metrics.py notes/ontology/<subject>/
```

Open `metrics.md` with one line naming the analyzer: `term_metrics.py` from the
scholar plugin's `scripts/`, at the `version` in the plugin's `plugin.json`
(`../../.claude-plugin/plugin.json`).

## Pass 2 — serial judgment

One candidate at a time. For each, write to `evidence/contested.md`:

- **Claim** — what the ontology currently asserts.
- **Objection** — the strongest case against it, argued properly rather than
  noted.
- **Evidence** — what settles it, cited or measured.
- **Verdict** — upheld, revised, or killed.

Record kills; do not discard them. A kill often carries more than a survivor, because it names a boundary
the ontology drew in the wrong place. A candidate rejected for the wrong reason
tells you the type above it is mis-specified.

Judge one candidate fully before starting the next. Batching them produces
verdicts that argue with each other.

## Pass 3 — completeness

Read `sources.jsonl` and ask what the study does not know:

- Which sources were never opened, and whether the vocabulary plausibly lives
  in one of them.
- Which terms rest on a single citation.
- Which types have exactly one member. A one-member type is usually a
  description, not a type.
- Which terms have no citation that shows them in use, only in definition.

## Pass 4 — stop condition

A round is passes 1 to 3 rerun against the current table. Stop when a round
surfaces no new contested claim, or at `--rounds` (default 3). Stop when the design stops fighting back, not when a counter runs
out.

## Panels

`--panel` prints one contested claim, ready to paste, followed by this line
for the user to run when the `weave` plugin is installed:

```text
/weave:ask <the claim, stated as a question>
```

Do not run it, and do not read another plugin's files. Continue serially;
record any panel verdicts the user pastes back in `evidence/contested.md`
beside the serial one.

## Rules

- A verdict cites or measures. "On reflection this seems fine" is not a
  verdict.
- Do not edit `terms.jsonl` to make a finding go away. Revise the claim and
  record why.
- A claim raised and not settled goes in `evidence/contested.md` as open, not
  in the brief.

## Output

Per `../../references/output-contract.md`. Hero: `✓ <n> candidates judged, <n>
killed, <n> open` or `⚠ Blocked: <reason>`. With no distilled ontology on disk,
the reason names distill as the missing stage and the one sentence after it
says to run `/scholar:distill`, never `/scholar:ontology`. Nothing follows that
sentence: no paths searched, no "I wrote nothing", no offer to look elsewhere:

```text
⚠ Blocked: no study directory or distilled ontology to contest.

Run /scholar:distill on the study, then run contest again.
```

Sections:

1. `## Findings` — what the analyzer proposed, by kind.
2. `## Verdicts` — each candidate, its objection, and how it resolved.
3. `## Kills` — what was killed and what the kill revealed.
4. `## Coverage` — what the study does not know, from pass 3.

Next-step options: another round, run render, widen the corpus, stop here.

Write it per `../../references/prose-rules.md`.
