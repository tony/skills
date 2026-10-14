---
name: scholar-contest
description: >-
  Adversarially judge a distilled ontology one candidate at a time:
  synonymy, polysemy, orphans, circular evidence, and coverage
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--out=<dir>] [--rounds=<n>] [--panel]"
  source: "plugins/scholar/skills/contest/SKILL.md"
---

# this skill

Stage 4. Attack the ontology. Four passes, serial by default: one judge, one
candidate at a time, every verdict traceable to the evidence that settled it.

Read `references/evidence-tiers.md` before recording any number, and
`references/citation.md` for the circularity rule that applies in every
pass. The analyzer
is `references/term_metrics.py`; `<analyzer>` below is its absolute path
resolved from this skill's directory.

User arguments: $ARGUMENTS

Read `references/output-contract.md` before writing study files.

## Pass 1: mechanical

Run the analyzer:

```console
$ python3 <analyzer> notes/ontology/<subject>/
```

It compares sibling definitions for synonymy (tf-idf cosine over the
`definition` text of rows sharing a parent), compares the definitions of rows
sharing one `term` for polysemy, walks `parent` links for orphans and
hierarchy cycles, tests whether a citation's quote contains the term it
supports for circular evidence, and counts children per parent for fan-out.
Similarity scores measure definition text, not identity or disjointness of
the things defined. An absent finding does not establish semantic separation.

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
(`references/plugin.json`). Retain the report's `analyzer-sha256:`
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

Check each structural assertion against its pinned source, not its repetition
in an earlier evidence document or in the quotations stored in `terms.jsonl`.
Read the cited text from the corpus at the recorded `commit`: a checkout read
in place once `python3 <pins> local <corpus> --expect <commit>` exits zero
(`<pins>` is `references/scholar_pins.py` resolved against this skill's directory),
or `git -C <corpus> show <commit>:<path>`. Record `upheld` only after that
read. Where the corpus
is not on disk, the verdict stays open and names the unread source as the
evidence needed. Withdrawing an unsupported disjointness
claim leaves overlap unknown; it does not establish the opposite. Keep the
verdict open if the unsupported claim remains in the ontology.

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
- Which types have few observed members and what supports their membership.
  A source-declared type can have no observed members in the scoped corpus.
- Which terms have no citation that shows them in use, only in definition.

## Pass 4: stop condition

A round is passes 1 to 3 rerun against the current table. Stop when a round
surfaces no new contested claim, or at `--rounds` (default 3). Run the ledger check in `references/stage-gates.md`
(`--check-verdicts`) at the end of each round: its `Unjudged` and `Open` lines
are the claims still to judge. A stop at `--rounds` with any of them leaves the
gate unmet; the hero says so (see Output).

## Panels

`--panel` prints one contested claim, ready to paste, followed by this line
for the user to run when the `weave` plugin is installed:

```text
weave-ask <the claim, stated as a question>
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

Per `references/output-contract.md`. Hero: `✓ <n> candidates judged, <n>
killed, 0 open` only when the gate in `references/stage-gates.md` passes;
`⚠ Gate unmet: <n> claims still open after <n> rounds` when a capped run has
open claims; or `⚠ Blocked: <reason>`. With no distilled ontology on disk,
the reason names distill as the missing stage and the one sentence after it
says to run the `scholar-distill` skill, never the `scholar-ontology` skill. The reply's first
line is the hero: never a sentence about what is or is not in the working
directory before it. Nothing follows that
sentence: no paths searched, no "I wrote nothing", no offer to look elsewhere:

```text
⚠ Blocked: no study directory or distilled ontology to contest.

Run scholar-distill on the study, then run contest again.
```

A capped run with open claims keeps all four sections below under the hero
(`## Kills` and `## Coverage` read `None.` when empty):

```text
⚠ Gate unmet: 3 claims still open after 3 rounds

## Findings

Synonymy: update-action / update-actions at 0.91. Circular evidence: ratchet.

## Verdicts

Open: update-action / update-actions, whether the two are one concept.

## Kills

None.

## Coverage

None.

Run another round, or widen the corpus to settle them.
```

The hero line is the template and nothing more: no second sentence. Sections:

1. `## Findings`: what the analyzer proposed, by kind.
2. `## Verdicts`: each candidate, its objection, and how it resolved.
3. `## Kills`: what was killed and what the kill revealed.
4. `## Coverage`: what the study does not know, from pass 3.

Next-step options: another round, widen the corpus, stop here. Offer run
render only when the contest gate passes.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
