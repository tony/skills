# Write for the reader's next useful action

## Establish the job before choosing a layout

Use repository evidence to distinguish a product introduction, package entry,
reference manual, contributor guide, collection, source mirror, or documentation
website. Identify the primary reader and any secondary route worth preserving.
Language alone does not determine the layout.

Universal habits are truthful orientation, recognizable signposts, an actionable
next step, consistent terms, and visible constraints that affect decisions.
These habits do not require identical headings, lengths, or installation sections.

The opening should explain what is here and expose a useful route. It need not
fit an arbitrary word count or contain every prerequisite before a reader can
decide whether to continue. A compatibility or migration notice may deserve
the first position when it changes that decision.

## Choose a form that matches the project

- A small library can lead with its purpose and a representative call, followed
  by dependency setup, an observable result, constraints, and reference links.
- A CLI manual can introduce the basic operation and then organize tasks for
  returning users. Preserve its lookup value and stable section anchors.
- A visual product can lead with a demonstration, provided the reader can still
  identify the product and reach installation or a live demo without the image.
- A multi-package project can start with a short chooser linking to package docs.
  Put enough distinction in each row to support a real choice.
- A source or docs repository can direct users to the maintained product docs
  and spend its own space on contributor setup.
- A mirror or retired project can consist mainly of its status and destination.
- A dataset, font, model, or asset library can foreground format, examples,
  download, compatibility, license, and provenance instead of code installation.

These are starting points. Combine them only when the project has those readers.

## Make examples earn their space

Choose a representative task that reveals the project. Include the imports,
input, context, and lifecycle steps required for the behavior being demonstrated.
Do not turn a quickstart into an API census or hide essential setup for brevity.

Distinguish package installation from building the checkout. State the working
directory when it matters. Identify credentials, optional dependencies, local
services, and terminal/session boundaries only when the example requires them.
Explain meaningful side effects next to the command that causes them.

Give one route per set of prerequisites; separate alternatives. Follow repository
command conventions. A transcript showing a failure and its remedy may contain
several commands and outputs, but it should not masquerade as one paste-and-run
block. Output should help the reader recognize success or diagnose a problem.

Link to larger examples when they have a maintained home. Keep necessary error
handling, resource cleanup, cancellation, terminal restoration, and data-loss
warnings even if they make the example longer.

## Make claims specific and maintainable

Describe behavior instead of announcing quality. Replace a vague claim only with
a fact the project supports; otherwise remove the claim or flag the missing evidence.
Explain jargon before relying on it when the intended reader would not know it.
Use the same term for the same concept throughout.

Retain exact numbers when they define compatibility, reproducibility, a format,
or bounded evidence. Check their source of truth. Avoid duplicating changing
release metadata and internal progress totals. If a benchmark remains, preserve
its workload, environment, conditions, and caveats, or link to those details.

Move history, implementation diaries, and announcements when they no longer help
the current reader. Migration history, license changes, and upgrade boundaries
can remain necessary. Preserve their meaning and destination when relocating them.

## Use visual design to guide attention

Use headings to name reader questions or tasks. Keep related instructions together
and give long references a clear index. Add an explicit contents list when it
improves discovery; GitHub's built-in outline does not serve every route equally.

Use tables for choices or aligned properties. Use prose for explanations. Keep
labels meaningful, link text descriptive, and emphasis selective. A logo, badge,
screenshot, animation, or diagram should contribute identity, evidence, or a useful
demonstration. Preserve useful branding and sponsorship; assess placement and scale.

Inspect the actual desktop rendering first, at the user's requested width or a
normal wide viewport. Then check narrower layouts and applicable light/dark modes.
Measure the README content area as well as the viewport. A desktop table that
works well may simply need horizontal scrolling on a phone. Do not flatten it
based only on a narrow screenshot.

Check image loading, readable screenshot text, alternative text, heading hierarchy,
code overflow, and collapsible labels. Keep necessary facts available in text.
External assets and badges can change independently of a pinned README, so record
what was actually observed and avoid blaming the source for an unproven fetch failure.

## Improve existing text conservatively

Preserve the reader routes and contracts identified before editing. Make the
smallest coherent change that resolves the actual concern. Do not replace working
prose merely to make it sound more like the skill's examples.

Keep useful personality and domain language. A distinctive explanation can teach
more than a shorter generic sentence. Creative inspiration should offer a better
way to show this project's behavior, not a decorative makeover detached from it.

Before delivery, compare examples, links, anchors, warnings, compatibility facts,
license meaning, generated sources, and supported audiences against the original.
Report execution and rendering checks separately from source inspection. Keep
review notes and uncertainties outside the finished README.
