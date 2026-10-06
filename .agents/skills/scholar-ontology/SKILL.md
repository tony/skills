---
name: scholar-ontology
description: >-
  Use when distilling an ontology, controlled vocabulary, or glossary of
  what a codebase, a repository set, or a written corpus calls things.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[<target>...] [--kind=code|prose|fleet] [--out=<dir>] [--resume=<stage>]"
  source: "plugins/scholar/skills/ontology/SKILL.md"
---

# this skill

Distil what a corpus calls things into a type hierarchy, a controlled
vocabulary, and an evidence layer. The product is a study directory, not a
document, and every claim in it either cites a pinned source or carries a
command that reproduces its number.

A study passes when a reader who was not present can disagree with a specific
claim, find what it rests on, and re-derive it. A summary cannot be checked,
does not compose, and rots without saying so.

Read `references/evidence-tiers.md` before starting; it decides what
each claim must carry. `references/citation.md` governs every pin.
`references/stage-gates.md` states each stage's exit condition.

User arguments: $ARGUMENTS

## Survey the workspace

1. Run `git remote get-url origin` to name the current repository. A failure
   means the working directory is not a git repository.
2. Run `ls notes/ontology/` to list existing studies. A failure means there
   are none.

## Stages

Five stages, run in order. Stage skills are invoked by name only, so the model
cannot call them. To run a stage, read `../<stage>/SKILL.md` (for example
the `scholar-gather` skill) and follow it. A user resumes a study by invoking a
stage directly.

1. `gather` — resolve and pin the corpus, inventory it, and record
   what was read and what was skipped, into `sources.jsonl`.
2. `extract` — harvest the terms the corpus uses, with a citation and
   a locator each, into `terms.jsonl`.
3. `distill` — build the three layers: types, members with
   discriminators, and the controlled vocabulary.
4. `contest` — judge the ontology adversarially, one candidate at a
   time, recording the kills.
5. `render` — write `brief.md` and the evidence documents, and gate
   the brief.

For prose, follow the `scholar-annotate` skill before `extract` to produce quotations
with stable locators.

`--resume=<stage>` starts at that stage against an existing study directory.

## Orchestration Plan

Enter plan mode before touching anything — `EnterPlanMode` in Claude Code,
`/plan` or Shift+Tab in Cursor, Codex, and Gemini. Where plan mode is
unavailable, present the same plan in chat and wait.

The plan states:

- The corpus: each target, its resolved ref, and how it was resolved.
- The kind — code, prose, or fleet — and what that changes about stages 1 and 2.
- The output directory, and confirmation that it is not inside the corpus.
- Which stages will run, and which are being skipped because a prior study
  already satisfies them.
- The coverage boundary: what will deliberately not be read, and why.

Present it, wait for approval, then exit plan mode and run stage 1. Where no
question tool exists (Codex, headless runs), print the plan and stop; do not
start stage 1 without approval.

## Rules

- Never write into the corpus being studied. Output lands under `--out`,
  defaulting to `notes/ontology/<subject>/` in the current repository.
- A pasted snippet is not a corpus. With no repository, directory, or document
  on disk to pin, report `⚠ Blocked` at stage 1 and say what to point the
  study at.

## Output

Per `references/output-contract.md`. Hero: `✓ <subject>: <n> terms, <n>
types, <n> contested` or `⚠ Blocked: <reason>`. Sections:

1. `## Corpus` — each source, its resolved ref, and what was deliberately not
   read, with the reason.
2. `## Ontology` — the type hierarchy in prose, each type with its
   discriminator, and the vocabulary's preferred terms.
3. `## Contested` — what was challenged and how it resolved, including what
   was killed and what the kill revealed.
4. `## Where it lives` — the study directory path and which stages ran.

Next-step options: contest another round, compare against another study,
publish the brief, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
