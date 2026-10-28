# Assess a README by the work it helps its reader do

Identify the primary reader, their likely knowledge, and the next useful action.
A visitor deciding whether to adopt a library, an operator upgrading a service,
and a contributor building its source need different information.

## What works already?

Record the useful features before proposing changes: a clear opening, a working
example, recognizable terminology, effective navigation, a meaningful demo,
honest limits, or a dependable reference. Keep these in the revised result.

## Where does the reader lose time or trust?

| Check | Look for | Passing condition |
| --- | --- | --- |
| Orientation | A generic pitch; undefined product category; audience confusion | The reader can identify what this repository offers and whether it fits their task. |
| First action | Missing prerequisites, undefined variables, mixed alternatives, unexplained credentials or foreground services | The reader can take the intended next step, locally or through a clear link, and recognize success. |
| Trust | Unsupported guarantees, inconsistent platform support, inaccurate examples, performance claims detached from conditions | Claims match evidence and important limits remain visible. |
| Navigation | Installation hidden behind promotion; contributor steps mixed into consumer use; unusable anchors | Headings and links let each intended audience reach its route. |
| Maintenance | Repeated version metadata, test counts, stale announcements, copied trees, transient paths, internal work diaries | Changing facts have a reason to be here and an identifiable source of truth. |
| Prose | Repeated promises, generic praise, unnecessary summaries, jargon before its meaning | Each passage adds an instruction, distinction, explanation, evidence, or necessary context. |
| Presentation | Competing banners, unreadable screenshots, dense tables, indiscriminate emphasis, required setup hidden in collapsed sections | The rendered page directs attention and remains useful with narrow widths or unavailable images. |
| Preservation | Lost warnings, altered guarantees, broken examples, removed attribution, flattened ecosystem choices | An improvement retains every still-relevant reader contract. |

## Grade the consequence

- **High:** an instruction is wrong, a significant adoption claim misleads, or a
  change could cause data loss, unsafe use, or a materially wrong decision.
- **Medium:** a reader must guess, take an unnecessary detour, or reconcile
  conflicting explanations; required information is difficult to locate.
- **Low:** localized wording or decoration distracts without obstructing the task.

Mark each concern as confirmed, unverified, or a preference. A plausible concern
is not a confirmed bug. Do not add the grades into a numerical slop score.

Words such as "robust", "seamless", and "powerful" invite a specificity check;
they are not proof of a defect or of AI authorship. Ask what the phrase tells the
reader that a concrete capability would not. A joke or personal voice can stay.

## Keep the exceptions visible

- Short portals may correctly delegate installation and reference material.
- Long manuals may serve returning users well when tasks and anchors are clear.
- Exact versions, image tags, dates, and hashes may define compatibility or
  reproducibility. Correct stale values rather than replacing them with "latest".
- Warnings, licensing distinctions, migration notices, and operational limits
  belong wherever they affect a decision, including above installation.
- Multiple installation paths may be necessary for distinct ecosystems. Label
  the choices and avoid making a copy button execute all of them.
- Screenshots, diagrams, benchmarks, sponsor credits, and tables can earn their
  space. Explain a specific reader cost before recommending their removal.
- A source repository, archived mirror, generated package page, or docs site
  needs a different assessment from a consumer-facing project introduction.

## Reusable review request

Review this README for its intended reader. Establish the repository's role and
the next useful action, then identify what already works. Assess orientation,
first use, factual support, navigation, maintenance burden, prose, presentation,
and preservation of reader-critical information.

Return a keep, tune, or rework verdict with prioritized concerns. For each, give
the location or a short excerpt, severity, evidence status, reader impact, and
smallest correction. Distinguish universal habits from contextual choices.
Preserve working examples, useful depth, warnings, version constraints, links,
attribution, and project voice. Do not infer AI authorship, impose a fixed length
or template, manufacture findings, or claim execution/rendering checks not run.
