---
name: beautiful-readmes
description: Use when writing, assessing, or improving a repository README for reader usefulness, scannability, stale detail, or AI slop.
---

# Beautiful READMEs

## Identify the reader and the requested change

1. Read the requested README, repository instructions, and enough manifests,
   examples, and linked documentation to establish its actual role.
2. Identify the primary reader, their likely knowledge, their next useful action,
   and whether the README also serves returning users or contributors. Infer
   from the project when possible; ask only when a missing decision changes the work.
3. Choose the requested mode: **assess** reports without edits; **write** creates
   a README from verified project facts; **improve** changes an existing README.
   A request to improve authorizes the relevant edits without another approval loop.
4. Read [the assessment](references/assessment.md). For writing or editing, also
   read [writing guidance](references/writing.md). Consult
   [patterns](references/patterns.md) for structure or creative inspiration and
   [niche guidance](references/niches.md) only for applicable ecosystems and project types.

## Preserve what already works

- Before editing, identify useful reader routes, working examples, constraints,
  compatibility pins, warnings, meaningful visuals, attribution, and recognizable voice.
- Preserve link destinations and heading anchors used by other docs. When moving
  material, retain a useful route to it; check incoming links before renaming anchors.
- Check whether the README is generated, symlinked, shared with a registry, or
  maintained in another source. Edit the owning source through its existing workflow.
- Tie each proposed change to a concrete reader benefit. Leave sound sections alone;
  no change is a successful outcome. Honor an explicitly requested redesign without
  discarding information the reader still needs.
- Treat length, badges, tables, emoji, first-person voice, exact numbers, and
  transcripts as contextual choices. They do not establish authorship or a defect.

## Assess or write for the reader's task

- Rank factual contradictions, broken first-use instructions, and misleading
  compatibility claims ahead of decorative concerns. Cite the passage and explain
  the consequence; separate confirmed defects, unverified claims, and preferences.
- Make the next action clear. It may be running an example, downloading an asset,
  viewing a demo, choosing a package, or opening maintained documentation.
- Match the form to the project. Preserve a useful reference manual or contributor
  portal instead of imposing a generic installation-and-quickstart template.
- Derive commands, APIs, platform support, versions, and claims from project evidence.
  Keep unknowns out of published prose and report missing facts separately.
- For creative work, borrow a pattern's function: a comparison that explains fit,
  a demo that reveals behavior, a clear route for several audiences. Adapt it to
  this project instead of copying another project's branding, claims, or voice.
- Cut repeated promises, unsupported promotion, temporary work logs, and obsolete
  details when they add no reader value. Preserve evidence and conditions behind
  claims that remain. A stale fact usually needs correction, not silent deletion.
- Keep required setup and operational caveats near the step they affect. Distinguish
  consumer installation from contributor builds and examples from schematic excerpts.

## Verify the proposed result

1. Recheck the intended reader's path through the opening, headings, first action,
   and next reference. Check internal links and anchors affected by the change.
2. Follow project conventions for commands and code fences. Keep alternative
   commands separate; label transcripts and output rather than treating them as
   copy-and-run instructions. Account for working directory and foreground processes.
3. Check changed examples against source and, when feasible, run them in an isolated
   environment. Do not execute untrusted or consequential README commands merely
   to review prose. State exactly what was and was not executed.
4. For visual changes, inspect the rendered target at the requested desktop width
   first, measuring content width as well as viewport size; then check narrow widths
   and applicable light/dark modes. If unavailable, label rendering unverified; source
   Markdown alone does not establish a visual defect or an improvement.
5. Compare the result with the preservation list. Check warnings, license meaning,
   example behavior, versions, accessibility, and navigation for regressions.
   Fix regressions before handing it back. Do not commit or publish unless requested.

## Return a useful result

- **Assessment:** identify the reader and README role, what works, and prioritized
  concerns with location, severity, evidence status, impact, and smallest remedy.
  Use a short verdict: keep, tune, or rework. Do not manufacture findings.
- **Writing or improvement:** deliver the requested README or scoped edit, then
  briefly state the reader benefit, validation performed, and unresolved facts.
  Keep editorial commentary outside the README.
- **Missing input:** name the missing project facts or inaccessible file, explain
  what they prevent, and complete independent work without inventing replacements.
