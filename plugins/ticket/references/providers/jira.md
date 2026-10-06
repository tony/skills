# Jira

## Scope

Atlassian Site (tenant) > Jira Space (scope_container) > Jira Work Item
(work_item).

Jira Cloud renamed Project to Space, Issue to Work Item, and Issue Type to Work
Type. The old nouns stay live in existing instances, in JQL, and in every REST
endpoint, so carry both: `Jira Space (former and API name: Jira Project)`. They
are one object. An Atlassian Project is a different object — a status and
reporting record — and never a Jira Space; a Confluence Space is not one either.

A work item key is `SPACEKEY-123`: two or more uppercase letters, a hyphen, a
number ([smart commits](https://support.atlassian.com/jira-software-cloud/docs/process-issues-with-smart-commits/)).
Space keys are reserved site-wide, including keys freed by a rename, so a key
resolves to one work item per site ([editing a project key](https://confluence.atlassian.com/adminjiraserver/editing-a-project-key-938847080.html),
a Data Center page; Cloud publishes no equivalent statement).

## Native hierarchy

Three default levels, numbered by Jira itself: level 1 Epic-level work item,
level 0 standard work item (Story, Task, Bug, Incident, Request, and every
other standard Work Type), level -1 Subtask ([configure the work type
hierarchy](https://support.atlassian.com/jira-cloud-administration/docs/configure-the-issue-type-hierarchy/)).
A Jira Task is level 0 — beside Story and Bug, never beneath them — and nothing
sits between the Epic level and the standard level.

The level-1 type can be renamed and still stays level 1. Levels above 1 are
configurable and tier-gated to Premium and Enterprise, named whatever the org
chose: Initiative, Theme, Program, Capability ([custom hierarchy levels](https://support.atlassian.com/jira-software-cloud/docs/configure-custom-hierarchy-levels-in-advanced-roadmaps/)).
Never assert Initiative exists, or sits at a given level, without reading the
instance's work type hierarchy.

A work item must belong to a Jira Space and a Subtask requires a parent, but a
standard work item needs no Epic-level parent: an unparented Story is
unparented, not an implied Epic.

## Semantic roles

- **Jira Space** (alias Jira Project) — scope_container; native, required.
  Every work item is `contained_by` exactly one.
- **Epic-level work item** — delivery_group; native, optional; `parent_of`
  standard work items.
- **Configured level above Epic** — strategic_goal; native_tier_gated and
  configurable, optional; absent on Free and Standard.
- **Standard work item** (Story, Task, Bug, Incident, Request) — work_item;
  native, required as the thing written.
- **Subtask** — sub_item; native, optional, `child_of` required once created.
- **Linked work items** (blocks, is blocked by, relates to, duplicates) —
  `blocks` and `relates_to`; native, optional, reciprocal by construction.
- **strategic_measure** — absent natively; convention only, via a custom field
  or a configured Work Type. Do not present it as native.

## Orthogonal objects

None of these is a parent. Membership says nothing about decomposition.

- **Sprint** — timebox; native to Jira Software, optional; `scheduled_in`.
- **Version**, surfaced as Release — release_group; native, optional;
  `released_in`.
- **Board** — view; native, optional; `visualized_by`. A filter, not a
  container.
- **Plan** (cross-Space) — view; native_tier_gated, optional; `visualized_by`.
- **Timeline** — view; native, optional; `visualized_by`.
- **Confluence page or Jira Docs content** — document; external, optional;
  `documented_by`.
- **External Pull Request or Merge Request** — review_artifact; external,
  optional; `implemented_by`. Name it after its host.

Jira has no universal native Milestone object. Translate by intent and say
which you picked: shipping target to a Version; fixed work period to a Sprint;
portfolio checkpoint to a configured Work Type or custom field; date checkpoint
to the due date or a custom date field; phase inside an Epic to a child work
item, component, or custom field.

## References and autolinks

What the Cloud editor auto-detects in a description or comment: a typed work
item key becomes a hyperlink to that work item — the behavior Atlassian's
standing request to disable it describes ([JRACLOUD-37224](https://jira.atlassian.com/browse/JRACLOUD-37224));
a pasted URL converts to a Smart Link, stored as an ADF [inlineCard](https://developer.atlassian.com/cloud/jira/platform/apis/document/nodes/inlineCard/)
node and rendered inline by default ([Smart Link view options](https://support.atlassian.com/platform-experiences/docs/smart-link-view-options/));
`@` plus a name inserts a mention; markdown `[text](url)` autoformats into a
plain hyperlink ([markdown and shortcuts](https://support.atlassian.com/jira-software-cloud/docs/markdown-and-keyboard-shortcuts/)).
Nothing documents a shorthand for a Space, Sprint, Version, Board, or document,
and Jira has no `#123` form at all. Do not invent one.

Which of those reach the target. A key in a body creates nothing there: Jira
Cloud does not convert mentions into links, Atlassian closed that request as
Won't Fix ([JRACLOUD-647](https://jira.atlassian.com/browse/JRACLOUD-647)), and
the plugin minting reciprocal `mentions` / `is mentioned by` links is [Data
Center only](https://support.atlassian.com/jira/kb/jira-autolink-plugin/). An
`@` mention does reach a person, notified when the description or comment saves
([watch, share and comment](https://support.atlassian.com/jira-software-cloud/docs/watch-share-and-comment-on-a-work-item/)),
so mention only someone you mean to page. A key in a commit message, branch
name, or PR title lands on that work item's development panel through the
connected dev tool ([reference work items in development](https://support.atlassian.com/jira-software-cloud/docs/reference-issues-in-your-development-work/)),
so never use a live key as illustration in a commit. A Jira URL placed on a
Confluence page mints a reciprocal remote link back onto the work item, shown
as Mentioned in ([Jira and Confluence together](https://support.atlassian.com/confluence-cloud/docs/use-jira-and-confluence-together/),
[missing Mentioned in](https://support.atlassian.com/jira/kb/mentioned-in-confluence-page-is-not-displaying-on-individual-jira-issues/)).

Unverified, no Atlassian doc addressing any of them: whether a Jira-to-Jira
Smart Link registers on the target; whether a Confluence URL inside a Jira body
registers on the page; whether a bare key written through the API rather than
typed in the editor still renders as a link.

Applied. Same site, any Space, work item exists: bare uppercase key, no link —
the renderer links it and nothing lands on the target. Any Atlassian object
without a key (Sprint, Version, Board, Plan, Confluence page): titled
`[text](url)`, so the reference still reads when the reader cannot unfurl it.
Different Atlassian site, or any non-Atlassian tracker: full titled link, since
a key resolves only inside its own site. For a visible reciprocal relationship
do not lean on prose — create a Linked work item of the right type, the one
in-tracker mechanism that shows on both objects by design.

## Reading and writing

Atlassian CLI: after `acli jira auth login`, the `acli jira workitem` group
covers create, edit, comment, link, search, and transition, with the body
supplied through `--description`, `--description-file`, `--from-file`,
`--from-json`, or `--editor`, in plain text or ADF ([acli jira workitem create](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-create/)).

Cloud platform REST [v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
and [v2](https://developer.atlassian.com/cloud/jira/platform/rest/v2/intro/)
expose the same operations; v3 takes rich text as [ADF](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
JSON, v2 takes wiki markup strings. Neither accepts markdown, and
autoformatting is an editor behavior, so `[text](url)` inside an ADF text node
stays literal — emit a text node carrying a `link` mark for a titled link, or
an `inlineCard` node for a Smart Link, and the two-axis choice is exactly yours.

MCP: the hosted [Atlassian Rovo MCP Server](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/)
groups Jira tools into read, write, and search — get a work item, create one,
edit fields, add a comment, link two work items, JQL search — gated by
org-granted permission groups, over OAuth or an API token.

With none of the three configured, the adapter drafts the body and emits the
approved text for the user to paste. A normal outcome.

## Naming traps

Never say Project for a Jira Space in prose; keep it for the API field and for
the Atlassian Project reporting object. Never say Space when you mean a
Confluence Space. Never say Issue Type where the instance says Work Type. Never
say Initiative unless you have read that level in the configuration. Never call
a Jira Task a subtask, and never map it onto a GitLab Task or an Azure DevOps
Task. Never say Milestone — name the Version, Sprint, date, or field you
actually mean. Never call a Sprint, Version, Board, or Plan a parent. Never
write `#123`, and never invent a sigil for anything Jira does not key.
