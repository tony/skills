---
name: ontology
description: "Use when distilling an ontology, controlled vocabulary, or glossary of what a codebase, a repository set, or a written corpus calls things."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[<target>...] [--kind=code|prose] [--out=<dir>] [--resume=<stage>]"
---


# /scholar:ontology

Distil what a corpus calls things into a type hierarchy, a controlled
vocabulary, and an evidence layer. The product is a study directory, not a
document, and every claim in it either cites a pinned source or carries a
command that reproduces its number.

A study passes when a reader who was not present can disagree with a specific
claim, find what it rests on, and re-derive it. A summary cannot be checked,
does not compose, and rots without saying so.

Read `../../references/evidence-tiers.md` before starting; it decides what
each claim must carry. `../../references/citation.md` governs every pin.
`../../references/stage-gates.md` states each stage's exit condition.

User arguments: $ARGUMENTS

## Survey the workspace

Run `ls notes/ontology/` to list existing studies. A failure means there are
none.

## Stages

Five stages, run in order. Stage skills are invoked by name only, so the model
cannot call them. To run a stage, read `../<stage>/SKILL.md` (for example
`../gather/SKILL.md`) and follow it. A user resumes a study by invoking a
stage directly.

1. `gather`: resolve and pin the corpus, inventory it, and record
   what was read and what was skipped, into `sources.jsonl`.
2. `extract`: harvest the terms the corpus uses, with a citation and
   a locator each, into `terms.jsonl`.
3. `distill`: build the three layers: types, members with
   discriminators, and the controlled vocabulary.
4. `contest`: judge the ontology adversarially, one candidate at a
   time, recording the kills.
5. `render`: write `brief.md` and the evidence documents, and gate
   the brief.

For prose, follow `../annotate/SKILL.md` before `extract` to produce quotations
with stable locators.

Run the stages silently: no stage's own `## Output` report or next-step panel.
Report once, at the end, in the shape under Output.

`--resume=<stage>` starts at that stage against an existing study directory.

## Orchestration Plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

The plan states:

- The corpus: each target, its resolved ref, and how it was resolved.
- The kind, code or prose, and what that changes about stages 1 and 2.
- The output directory, and for a corpus that is the current repository, that
  the study directory is excluded from the dirty-tree check.
- Which stages will run, and which are being skipped because a prior study
  already satisfies them.
- The coverage boundary: what will deliberately not be read, and why.

Present it, wait for approval, then exit plan mode and run stage 1. Where no
question tool exists (Codex, headless runs), print the plan and stop; do not
start stage 1 without approval. A request that already approves the plan
("I approve the plan") counts as that approval.

## Rules

- Never write into the corpus being studied. Output lands under `--out`,
  defaulting to `notes/ontology/<subject>/` in the current repository. When
  the current repository is the corpus, that default stands: `extract`'s
  dirty-tree check leaves the study directory out.
- A pasted snippet is not a corpus. With no repository, directory, or document
  on disk to pin, report `⚠ Blocked` at stage 1 and say what to point the
  study at. A pasted prose excerpt can only be pinned by running `gather`
  directly, which saves it under the study directory.

## Output

Per `../../references/output-contract.md`. Hero: `✓ <subject>: <n> terms, <n>
types, <n> contested` or `⚠ Blocked: <reason>`. Sections:

1. `## Corpus`: each source, its resolved ref, and what was deliberately not
   read, with the reason. Never write that a checkout was clean or left
   unchanged, that nothing was left unread, or a claim about the sandbox; an
   unpushed commit reads "commit not on a remote; recorded without URL".
2. `## Ontology`: the type hierarchy in prose, each type with its
   discriminator, and the vocabulary's preferred terms.
3. `## Contested`: what was challenged and how it resolved, including what
   was killed and what the kill revealed.
4. `## Where it lives`: the study directory path and which stages ran.

A blocked run follows the halted-run shape in the output contract: hero, one
sentence naming the missing corpus, and one line saying what to point the study
at (a repository URL, a local directory, or a document on disk). No bold, no
options list, no plan for what happens next, no sections, no guesses from a
pasted snippet, no local paths:

```text
⚠ Blocked: no corpus on disk to study, only a pasted snippet.

Point me at a repository URL, a local directory, or a document on disk.
```

Next-step options: contest another round, compare against another study,
stop here.

Write it per `../../references/prose-rules.md`.
