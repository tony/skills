# Altitude — what each kind of body carries

Which sections a body carries depends on its semantic role, not on which
provider hosts it. Resolve the role first with `hierarchy.md`, then look it
up here. The rules for what goes *inside* those sections are in
`contract.md`.

**The gradient:** as altitude rises, the future tense shrinks and the linking
grows. A strategic goal is mostly links and one outcome. A sub-item is mostly
specifics.

**When two roles both seem to fit, write the one that carries less.** A body
that under-specifies attracts a comment. A body that over-specifies gets
obeyed.

## Roles that are never authored

`scope_container`, `timebox`, `release_group`, `checkpoint`, and `view` are
associations, not bodies. A Cycle, a Sprint, a Version, a Board, and a
Project Milestone are things work is *assigned to*. They have names and
dates, not descriptions with acceptance criteria.

If someone asks for "a ticket for the Q3 milestone", they mean a
`strategic_goal` or a `delivery_group` that happens to be `released_in` or
`checkpoint_of` that thing. Write that instead, and say so.

## `strategic_goal`

Linear Initiative, Shortcut Objective, a Jira work item above Epic.

Carries: **Outcome** — one paragraph on what changes and for whom.
**Why now** — what makes this the moment, when there is an answer.
**Not doing** — the adjacent things it will be mistaken for.
**Delivery groups** — links to children.

Invariants only when genuinely existential. A strategic goal naming three
invariants has almost certainly encoded implementation votes as constraints.
Most name none.

No technical content. No dates as gates. No evidence section — a goal is not
a defect report.

## `strategic_measure`

Shortcut Key Result, GitLab Key Result.

Carries one measurable statement, how it is observed, and which goal it
measures. Nothing else. No work plan, no invariants, no children.

A measure is `measured_by` its goal. It is never a delivery parent, and it
never grows a task list.

## `delivery_group`

Jira Epic, Linear Project, GitLab Epic, Shortcut Epic, Azure DevOps Feature,
a GitHub parent issue used as an epic by convention.

Carries: **Outcome** — the user-visible result, in a paragraph.
**Evidence** — only when the group exists because something is broken, and
only enough to establish that it is.
**Invariants** — the few whose violation makes the whole group pointless.
**Intent** — the current direction, labelled non-binding.
**Not doing** — explicit non-goals.
**Children** — links, each with one line on why it belongs.

No implementation. No storage engines, no schemas, no file layouts, no CLI
surfaces. If that thinking exists, it belongs in a `document` and the group
links to it.

This is the altitude where over-specification does the most damage, because
everything below inherits it.

## `work_item`

GitHub Issue, GitLab Issue, Linear Issue, Jira Story or Bug, Shortcut Story,
Trello Card, Azure DevOps User Story.

The full contract shape, and where most of the work happens.

Carries: **Summary** — what happens and who it affects, in two or three
sentences. Always present.
**Motivation** — for proposals: what is awkward or impossible today, shown
concretely.
**Reproduction**, **Expected**, **Actual**, **Environment** — for defects.
Numbered steps, one command per fence, versions folded into a details block.
**Evidence** — logs and output, folded, read for secrets first.
**Invariants** — what would make the fix worthless or break a neighbour.
**Intent** — the suggested approach, labelled non-binding.
**Not doing** — non-goals, when there is a plausible misreading.
**References** — pinned links, per `contract.md` and the provider file.

Include only the sections you have content for. A one-line typo report does
not get nine headings. Match the shape to the finding.

## `sub_item`

GitHub Sub-issue, Jira Subtask, GitLab Task, Linear Sub-issue, Azure DevOps
Task, Shortcut Sub-task.

Short. What to do, and a link to the parent. Concrete and technical is
correct here — this is the altitude that specifics belong to.

Do not restate the parent's invariants. They are inherited, and restating
them creates a second copy to drift.

Often two or three sentences. A sub-item with its own evidence section and
its own intent section is a `work_item` that was filed in the wrong place.

## `document`

Linear Document, Shortcut Doc, ADR, RFC, Confluence page, a spec in the
repository.

Carries: **What this decides** — the decisions, each with what it chose
against. **What it leaves open** — named explicitly, so nobody reads silence
as settled. **References** — pinned.

No acceptance criteria. No schedule. No assignee. A document is not tracked
work; it is the thing tracked work points at.

This is the escape valve for `contract.md`'s rule that a body must never
contain the design. Depth that does not belong in a ticket belongs here, and
the ticket links to it. When a `delivery_group` starts growing a design,
that is the signal to write one of these and cut the group back to an
outcome.

## `review_artifact`

GitHub Pull Request, GitLab Merge Request, Azure Repos Pull Request.

Describes the net shipped result of the branch. **No future tense at all** —
this is the one role where the work is already done and the body is a report,
not a proposal.

Carries: **Summary** — bullets opening with an impact label.
**Changes by area** — grouped, for multi-module work.
**Design decisions** — the trade-offs made, with the alternative and why not.
**Verification** — copyable commands.
**Test plan** — what each item validates, not just the command.

Describe the branch's net result, not its internal evolution. Fixups,
reverts-then-re-adds, and intermediate states belong in the commits that made
them. Apply the published-release test: if users of the last release never
experienced the old behavior, describing the change from it is
branch-internal narrative.

When the `pr` plugin is installed, it owns this role in more depth. Hand off
rather than duplicating.
