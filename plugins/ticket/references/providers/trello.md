# Trello

## Scope

Enterprise (Enterprise plan only) > Workspace > Board > List > Card > Checklist >
Checklist item.

This chain is physical containment, nothing more. A Card lives in exactly one List on
exactly one Board in exactly one Workspace. Collections (Premium) group Boards inside a
Workspace for navigation; they do not re-parent anything.

## Native hierarchy

Trello's only native work-decomposition chain is Card > Checklist > Checklist item.
That is the whole ladder.

List is **not** a decomposition level. A List physically contains Cards but usually
encodes workflow state, phase, queue, or category. A Card sitting in "In Progress" has
no deliverable relationship to that List.

Trello has **no** native Initiative, Epic, Project, Feature, Milestone, Sprint, release,
or timebox object. Do not invent one. Above the Card there is only the Board, and a
Board is a container, not a deliverable. Anything resembling a higher level is
convention built from generic materials: a Card titled "Epic: Authentication", a Board
card (native card type that "is a link to another board"), a Label, a Custom Field
(native, Standard plan and up), a card-to-card attachment, or a Power-Up. Record each
with `mapping_basis: convention` and keep `native_type: card` (or `label`,
`custom_field`).

Checklist items are not tickets. A checklist item has no description, no comments, and
no URL you can hand to someone. Promote it to a Card before treating it as work_item.

## Semantic roles

- **Workspace** — scope_container. native, required.
- **Board** — scope_container (the Card container). native, required. Reading it as a
  project or workflow is `mapping_basis: convention`.
- **List** — no canonical role; default meaning is workflow state. native, required (a
  Card must be in one). Never map a List to delivery_group or strategic_goal, and never
  emit `parent_of` from a List to its Cards.
- **Card** — work_item. native, required.
- **Checklist** — a named group of sub_items, `grouped_by` from the item's side. native,
  optional.
- **Checklist item** — sub_item, `child_of` its Card. native, optional.
- **Card description and attachments** — document (contextual). native, optional,
  `documented_by`. Linked external files or pages are external documents.
- **Label / Custom Field** — the practical carrier for delivery_group, strategic_goal,
  or release_group when a Workspace actually uses one. Label is native; Custom Field is
  native_tier_gated (Standard and up). Both optional. Emit `grouped_by`, never
  `parent_of`.
- **Board view** — view. native_tier_gated (Timeline, Calendar, Table, Dashboard, Map
  need Premium or Enterprise). optional.
- **delivery_group, strategic_goal, strategic_measure, release_group, timebox,
  checkpoint, review_artifact** — absent natively; convention at best, and only on
  Workspace evidence. Trello has comments, not reviews.

## Orthogonal objects

None of these are parents of a Card, and none may be converted to `parent_of`:

- **Due date and start date** — per-Card scheduling fields, not a timebox object. There
  is no Sprint, so `scheduled_in` has no native target to point at.
- **Board views and Workspace views** — `visualized_by` only. A Card on a Timeline is
  not contained by it. **Labels, Custom Fields, Collections** — `grouped_by` only.
- **Mirror card** (paid Workspaces) — the same Card surfaced on another Board, not a
  child. **Board card** and **Link card** are pointers, not parents.
- **Attachments and comments** — `documented_by`. A checked checklist item is the
  nearest thing to a checkpoint and is still a sub_item, not a `checkpoint_of`.

## References and autolinks

**What the renderer detects.** Trello renders most of Markdown in descriptions,
comments, and checklist items, but
["Trello's web version doesn't support the complete Markdown syntax"](https://support.atlassian.com/trello/docs/how-to-format-your-text-in-trello/).
A URL becomes a smart link whose display you pick from "URL", "Inline", "Card", or
"Embed". There is **no** `#N` autolink, **no** issue-key sigil, **no** commit-SHA
autolink, and no cross-container shorthand of any kind. The only mention syntax is
`@username`, `@card`, and `@board`, documented for
[comments](https://support.atlassian.com/trello/docs/commenting-on-cards/) and checklist
items.

**What creates a backreference.** One documented mechanism: attaching a Card.
["Trello card attachments create a link between both cards."](https://support.atlassian.com/trello/docs/adding-attachments-to-cards/)
An `@mention` notifies the person named. Nothing else is documented as producing a
visible event on a target.

**Applying the two-axis rule.**

- Referring to another Card, same Board or any other, with no backreference wanted:
  write an explicit titled Markdown link to the target's `shortUrl`. There is no bare
  form to prefer — Trello has no shorthand to leave bare, and a raw URL renders only as
  an unlabeled smart link.
- Wanting the backreference: attach the Card, do not do it in the description. `desc` is
  a plain string field and attachments are a separate resource, so writing `desc` cannot
  mint an attachment record on the target. **Unverified:** whether pasting a Card URL
  into the description in the web UI offers a prompt that converts it into an
  attachment. Community reports describe a "Connect cards" affordance; no official doc
  confirms it. Do not rely on it and do not tell the user it happened.
- Cross-container is identical. A Card URL is globally addressable
  (`https://trello.com/c/<shortLink>`), so another Board or another Workspace uses the
  same form. There is no `board/card#N` equivalent. Access is the constraint, not
  syntax: ["If you are linking to a private item then the person you are sharing the
  link with must be a member of that board."](https://support.atlassian.com/trello/docs/sharing-links-to-cards-boards-comments-and-actions/)
- Never write `#12` for a Card. The per-Board number is
  [`idShort`](https://developer.atlassian.com/cloud/trello/guides/rest-api/object-definitions/):
  "Numeric ID for the card on this board. Only unique to the board, and subject to
  change as the card moves." Not globally unique, and Trello does not linkify it.
- Never put a bare URL in a Card **name**. A URL as a card title creates a Link card, or
  a Mirror card in a paid Workspace — a different object that cannot hold a description
  or comments.
- Use `@` only when the notification is wanted. **Unverified:** whether `@mention` in a
  card *description* notifies; official docs cover comments and checklist items only.

**Markdown deltas.** Nested blockquotes are unsupported. Tables, images, and task-list
checkboxes are not documented as supported — do not emit them. A single newline does not
break a line; Trello
["requires an empty line to separate lines"](https://support.atlassian.com/trello/docs/special-characters/).
Emoji use `:shortcode:`. Wrap a URL in backticks to show it raw inside a checklist item.

## Reading and writing

A local agent has two real backends. The
[REST API](https://developer.atlassian.com/cloud/trello/rest/) is at
`https://api.trello.com/1/`, authenticated with an API key plus token. Create with
`POST /cards` (requires `idList`), update with `PUT /cards/{id}`, comment with
`POST /cards/{id}/actions/comments`, attach with `POST /cards/{id}/attachments`. The body
field is `desc`, capped at 16384 characters — check length before writing a long draft.

```
curl -s "https://api.trello.com/1/cards/$CARD_ID?key=$TRELLO_KEY&token=$TRELLO_TOKEN"
```

The [official Trello MCP server](https://support.atlassian.com/trello/docs/connect-trello-to-ai-assistants-with-trello-mcp/)
is at `https://mcp.trello.com/v1`, OAuth 2.0 only (API tokens are not accepted for MCP),
and covers boards, lists, cards, and checklists. It refuses destructive deletes: an
assistant can archive a Card or List but cannot permanently delete one.

No first-party Trello CLI is documented. With neither backend configured, draft the Card
title, description, and checklist as Trello-flavored Markdown and emit the approved text
for the user to paste. That is a normal outcome, not a degraded one.

## Naming traps

Never say, in output or in a mapping:

- **"Project"** — no Project object exists. Say Board or Workspace, and mark any project
  reading as convention.
- **"Epic"**, **"Initiative"**, **"Feature"**, **"Story"**, **"Task"** as native types.
  They are Cards. A Card titled "Epic: X" is a Card.
- **"Milestone"**, **"Sprint"**, **"Release"**, **"Iteration"**, **"Cycle"** — none
  exist. A due date is a date, not a milestone.
- **"Column"** — the noun is List; reserve "column" for Table view. **"Swimlane"** — not
  a Trello object. **"Team"** — renamed to Workspace.
- **"Sub-task"** for a checklist item — it is a checklist item, not independently
  trackable. **"Sub-card"**, **"child card"**, **"parent card"** — Trello has no
  card-to-card parentage; an attachment between Cards is `relates_to`.
- **"Ticket"** or **"issue"** for a Card in text that lands in Trello; the native noun is
  Card. **"#N"** for a Card, or any claim that a number, key, or SHA autolinks.
