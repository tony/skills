---
name: contest
description: "Adversarially judge a distilled ontology one candidate at a time: synonymy, polysemy, orphans, circular evidence, and coverage"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[--out=<dir>] [--rounds=<n>] [--panel]"
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

Read `../../references/output-contract.md` before writing study files.

## Pass 1: mechanical

Run the analyzer:

```console
$ python3 <analyzer> notes/ontology/<subject>/
```

It compares sibling definitions for synonymy (tf-idf cosine over the
`definition` text of rows sharing a parent), compares the definitions of rows
sharing one `term` for polysemy, walks `parent` links for orphans and
hierarchy cycles, tests whether a citation's quote contains the term it
supports for circular evidence, and counts children per parent for fan-out. It
reads definitions and parents, never the names, so a high synonymy score means
two definitions say the same thing.

The analyzer proposes; it never decides. A high similarity score is a
question (*are these one concept?*), not an answer. Record the number in
`evidence/metrics.md`, per the evidence tiers, with the output verbatim.
Record this reproduction command with the actual study path. Tell the reader
to run it from the directory containing that study path and paste their
installed analyzer's absolute path at the prompt. Do not assume the script
exists beside the study or copy it there.

```console
$ printf 'Installed Scholar analyzer path: ' \
    && read -r scholar_analyzer \
    && python3 "$scholar_analyzer" notes/ontology/<subject>/
```

Open `metrics.md` with a header naming the analyzer: `term_metrics.py` from the
scholar plugin's `scripts/`, at the `version` in the plugin's `plugin.json`
(`../../.claude-plugin/plugin.json`). Retain the report's `analyzer-sha256:`
and `thresholds:` lines so a reader can compare exact analyzer bytes and
scoring conditions without recording an account-specific installation path.

## Pass 2: serial judgment

One candidate at a time. For each, write to `evidence/contested.md`:

- Claim: what the ontology currently asserts.
- Objection: the strongest case against it, argued properly rather than
  noted.
- Evidence: what settles it, cited or measured.
- Verdict: upheld, revised, killed, or open. An open claim states the
  objection and what evidence would settle it.

Record kills; do not discard them. A kill often carries more than a survivor, because it names a boundary
the ontology drew in the wrong place. A candidate rejected for the wrong reason
tells you the type above it is mis-specified.

Judge one candidate fully before starting the next. Batching them produces
verdicts that argue with each other.

## Pass 3: completeness

Read `sources.jsonl` and ask what the study does not know:

- Which sources were never opened, and whether the vocabulary plausibly lives
  in one of them.
- Which terms rest on a single citation.
- Which types have exactly one member. A one-member type is usually a
  description, not a type.
- Which terms have no citation that shows them in use, only in definition.

## Pass 4: stop condition

A round is passes 1 to 3 rerun against the current table. Stop when a round
surfaces no new contested claim, or at `--rounds` (default 3). A stop at `--rounds` with any claim still open leaves the gate unmet; the
hero says so (see Output).

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
  record why. A definition edit that removes a phrase the corpus does not
  contain is a recorded revision, not hiding a finding.
- A claim raised and not settled goes in `evidence/contested.md` as open, not
  in the brief.

## Output

Never mention a file left unchanged ("terms.jsonl is unchanged").

Per `../../references/output-contract.md`. Hero: `✓ <n> candidates judged, <n>
killed, 0 open` only when the gate in `../../references/stage-gates.md` passes;
`⚠ Gate unmet: <n> claims still open after <n> rounds` when a capped run has
open claims; or `⚠ Blocked: <reason>`. With no distilled ontology on disk,
the reason names distill as the missing stage and the one sentence after it
says to run `/scholar:distill`, never `/scholar:ontology`. The reply's first
line is the hero: never a sentence about what is or is not in the working
directory before it. Nothing follows that
sentence: no paths searched, no "I wrote nothing", no offer to look elsewhere:

```text
⚠ Blocked: no study directory or distilled ontology to contest.

Run /scholar:distill on the study, then run contest again.
```

A capped run with open claims replies in this shape, as plain text outside any
code fence, with the sections below under the hero (shown here with one):

```text
⚠ Gate unmet: 3 claims still open after 3 rounds.

## Findings

Synonymy: update-action / update-actions at 0.91. Circular evidence: ratchet.

## Verdicts

Open: update-action / update-actions, whether the two are one concept.

Run another round, or widen the corpus to settle them.
```

The hero line is the template and nothing more: no second sentence. Sections:

1. `## Findings`: what the analyzer proposed, by kind.
2. `## Verdicts`: each candidate, its objection, and how it resolved.
3. `## Kills`: what was killed and what the kill revealed.
4. `## Coverage`: what the study does not know, from pass 3.

Next-step options: another round, run render, widen the corpus, stop here.

Write it per `../../references/prose-rules.md`.
