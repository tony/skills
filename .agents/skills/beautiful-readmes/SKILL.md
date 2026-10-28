---
name: beautiful-readmes
description: >-
  Use when assessing, writing, or improving a README for reader usefulness,
  scannability, examples, compatibility, and preserving project voice.
metadata:
  source: "plugins/beautiful-readmes/skills/beautiful-readmes/SKILL.md"
---

# Beautiful READMEs

## Identify the reader's next action

Read the README, project instructions and enough source, metadata or linked docs
to identify its audience and role. A consumer introduction, reference manual,
contributor portal and asset collection need different routes.

Assess without editing when asked for a review. Writing or improving follows the
user's requested scope; infer ordinary choices from the project.

## Preserve before changing

- Identify working examples, useful navigation, constraints, warnings, attribution,
  licensing and project voice. Keep them; no edit is a successful result.
- Find the owning source before editing generated or shared documentation. Preserve
  incoming anchors and meaningful routes when moving material.
- Treat length, contents, badges, exact versions and installation alternatives as
  choices to assess by reader cost, not automatic defects or evidence of AI authorship.

## Plan an edit within the authorized scope

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

State the reader, smallest useful change, material to preserve and relevant checks.
Proceed under existing authorization; obtain approval if that scope is not authorized.

## Resolve concrete reader problems

- Prioritize wrong first-use instructions, misleading claims and hidden prerequisites
  over decoration. Separate confirmed defects, unverified concerns and preferences.
- Verify corrections against project evidence. An example needs its imports, inputs,
  setup and cleanup, or a clear label that it is a partial API preview. A named socket
  does not establish ownership; a test fixture does not establish consumer setup.
- Name the exact operation, error and version boundary the implementation supports.
  Refusing a requested command does not imply that no version probe or other I/O occurs.
- For structural ideas, read [patterns](references/patterns.md). For ecosystem,
  installation or lifecycle questions, read [context checks](references/contexts.md).
  Read only the relevant reference sections.
- Write per [prose rules](references/prose-rules.md). Remove generic promises
  and repetition when they add no instruction, distinction or evidence. Preserve
  useful personality and historical facts in their stated release context.

## Check and return the result

Check changed examples and links against the source; run relevant examples in an
owned environment when feasible. Recheck preserved warnings, anchors, versions and
license meaning. Report source inspection, execution and rendering separately.
For visual changes, inspect desktop rendering first and measure article width,
then narrow layouts and applicable themes. Source Markdown alone proves no visual defect.

For assessment, use `## Verdict`, `## Concerns`, then `## Checks`. Give a keep,
tune or rework verdict with the audience and what works. Each concern needs a
location, evidence status, reader consequence and smallest remedy; omit empty concerns.
For writing or improvement, deliver the requested artifact and a short check summary.
Keep uncertainties and editorial notes outside the README. Never invent missing facts
or claim checks not run. Commit, push or publish only when requested.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
