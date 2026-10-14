---
name: scholar-render
description: >-
  Write a study's brief and evidence documents, then enforce the brief's
  citation prohibition with the analyzer
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--out=<dir>]"
  source: "plugins/scholar/skills/render/SKILL.md"
---

# this skill

Stage 5. Write the two layers a reader actually meets: a brief they read start
to finish, and the evidence they check it against.

The analyzer is `references/term_metrics.py`; `<analyzer>` below is its
absolute path resolved from this skill's directory. `references/stage-gates.md` states the brief gate's exit
condition.

User arguments: $ARGUMENTS

Read `references/output-contract.md` before writing study files.
Read `references/evidence-tiers.md` before choosing the brief's claims.

## The prohibition

The brief carries no citation, no permalink, and no bare number. Where it
wants one, it links into `evidence/`. A brief with its appendices inlined is a
report, and nobody reads it start to finish.

Backticked code spans (`OAuth2`, `v2`) and evidence links are exempt;
a version or identifier with a digit outside backticks fails. Spelled-out
counts ("twelve plugins") are numbers too; the analyzer cannot see them, so
write none.

The analyzer checks URLs, digits, common inline Markdown links, and that each
link into `evidence/` names an existing file. Other citation forms and claim
support require review.
Run it before reporting success. A missing
`brief.md` exits 2: write the brief first. A brief the user asked to keep
unchanged is gated as is; report its findings and leave it.

```console
$ python3 <analyzer> notes/ontology/<subject>/ --check-brief
```

## What the brief says

Four movements, in prose, each linking to the evidence file that holds its
support:

1. What the corpus is about, and where its vocabulary lives.
2. The type hierarchy and its supported memberships, distinguishing declared
   types from their documented roles.
3. The controlled vocabulary: the preferred terms, and the collisions that
   made them necessary.
4. What `contest` overturned, and what the kills revealed.

Trace each assertion to support in the existing evidence documents. Remove
unsupported assertions from the brief; name `contest` as the stage needed
to resolve them without rewriting its evidence or declaring them settled.

Write it per `references/prose-rules.md`, for a reader who was not
present. They do not have the corpus open, they do not know the analyst, and
they will judge the study by whether they can disagree with it.

## What the evidence documents hold

`evidence/hierarchy.md`: type declarations and is-a claims, each with its
source-supported membership basis and citation.

`evidence/vocabulary.md`: preferred terms, aliases and senses, and the
relations the source supports or leaves unknown.

`evidence/metrics.md`: every distributional claim with the command that
produced it and the output it produced.

`evidence/contested.md`: what `contest` judged, including the kills.

`evidence/corrections.md`: created empty (Write with empty content) when
missing, written by the `scholar-revise` skill.

## Rules

- Create an evidence document only when it is missing, and never rewrite one
  that exists. `distill`, `contest` and `revise` own `hierarchy.md`,
  `vocabulary.md`, `metrics.md`, `contested.md` and `corrections.md`: their
  verbatim command output and recorded kills stay as written. Render
  regenerates only `brief.md`; where an owned document is stale, name the
  stage that owns it.
- Do not restate an evidence document in the brief. If a paragraph would
  survive being replaced by a link, replace it.

## Output

Per `references/output-contract.md`. Hero: `✓ rendered <subject>: brief +
<n> evidence docs` or `⚠ Brief gate failed: <n> findings`. Sections:

1. `## Brief`: the path, and the four movements in one line each.
2. `## Evidence`: each document created, and what it holds.
3. `## Gate`: the brief check's output, verbatim, with absolute paths
   stripped.

A failed gate is the contract's failed-gate reply with the hero and `## Gate`:
name each flagged URL and number, and say only that each moves into the
matching `evidence/` file and is linked, or that the brief stays as is. Never
add a lead-in or explain how a finding was counted (that `v1.0.0` or `#L12`
"counts as a bare number"). Never claim a command produced a number the
brief's author wrote by hand:

```text
⚠ Brief gate failed: 2 findings

## Gate

line 5: URL belongs in evidence/, not the brief
line 6: bare number belongs in evidence/, not the brief

Move the URL (github.com/example/sample-lib/.../ports.py) and the numbers 14 and 0.62 into the matching evidence/ file and link them from the brief, or leave the brief as is and stop.
```

Omit `## Brief` and `## Evidence` for anything not
written. A missing study follows the halted-run shape in the output contract.

Next-step options: compare against another study, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
