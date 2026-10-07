---
name: render
description: "Write a study's brief and evidence documents, then enforce the brief's citation prohibition with the analyzer"
allowed-tools: ["Bash", "Read", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[--out=<dir>]"
user-invocable: true
disable-model-invocation: true
---


# /scholar:render

Stage 5. Write the two layers a reader actually meets: a brief they read start
to finish, and the evidence they check it against.

The analyzer is `../../scripts/term_metrics.py`; `<analyzer>` below is its
absolute path resolved from this skill's directory. `../../references/stage-gates.md` states the brief gate's exit
condition.

User arguments: $ARGUMENTS

## The prohibition

The brief carries no citation, no permalink, and no bare number. Where it
wants one, it links into `evidence/`. A brief with its appendices inlined is a
report, and nobody reads it start to finish.

Backticked code spans (`OAuth2`, `v2`) and evidence links are exempt;
a version or identifier with a digit outside backticks fails. Spelled-out
counts ("twelve plugins") are numbers too; the analyzer cannot see them, so
write none.

The analyzer enforces the rule. Run it before reporting success. A missing
`brief.md` exits 2: write the brief first. A brief the user asked to keep
unchanged is gated as is; report its findings and leave it.

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-brief
```

## What the brief says

Four movements, in prose, each linking to the evidence file that holds its
support:

1. What the corpus is about, and where its vocabulary lives.
2. The type hierarchy, with each type's discriminator stated plainly.
3. The controlled vocabulary: the preferred terms, and the collisions that
   made them necessary.
4. What `contest` overturned, and what the kills revealed.

Write it per `../../references/prose-rules.md`, for a reader who was not
present. They do not have the corpus open, they do not know the analyst, and
they will judge the study by whether they can disagree with it.

## What the evidence documents hold

`evidence/hierarchy.md`: the is-a claims, one citation each, with the
discriminators.

`evidence/vocabulary.md`: preferred and deprecated terms, and the
disjointness constraints.

`evidence/metrics.md`: every distributional claim with the command that
produced it and the output it produced.

`evidence/contested.md`: what `contest` judged, including the kills.

`evidence/corrections.md`: created empty, written by `/scholar:revise`.

## Rules

- Refresh the evidence documents rather than appending; they describe the
  current state of the study, and `corrections.md` is where history lives.
- Do not restate an evidence document in the brief. If a paragraph would
  survive being replaced by a link, replace it.

## Output

Per `../../references/output-contract.md`. Hero: `✓ rendered <subject>: brief +
<n> evidence docs` or `⚠ Brief gate failed: <n> findings`. Sections:

1. `## Brief`: the path, and the four movements in one line each.
2. `## Evidence`: each document written and what it holds.
3. `## Gate`: the brief check's output, verbatim, with absolute paths
   stripped.

On a failed gate, print the hero, `## Gate`, and the fix: edit the brief, or
leave it and stop. Say only that each flagged URL or number moves into the
matching `evidence/` file and is linked; never claim a command produced a
number the brief's author wrote by hand. Omit `## Brief` and `## Evidence` for anything not
written, and offer no other next step. Never say what was left alone ("I left the brief as you wrote it"); report the gate result. A missing study follows the halted-run
shape in the output contract.

Next-step options: compare against another study, stop here.

Write it per `../../references/prose-rules.md`.
