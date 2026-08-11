# Linear

## Scope

Workspace (scope_container) > Team (scope_container) > optional Sub-team
(scope_container). A Workspace has its own slug (`linear.app/example`) and holds
every Team, Issue, Project, Initiative and Document for one company. Every Issue
is contained_by exactly one Team, and that Team owns the workflow statuses,
Cycles, labels and triage it moves through. Teams are an ownership and process
boundary — never a delivery level. See
[Concepts](https://linear.app/docs/conceptual-model),
[Sub-teams](https://linear.app/docs/sub-teams).

## Native hierarchy

Initiative (strategic_goal) > optional Sub-initiative > Project
(delivery_group) > Issue (work_item) > Sub-issue (sub_item).

An Initiative groups Projects around a company objective at the workspace level
and must be switched on in workspace settings before it exists; Sub-initiatives
nest Initiatives and are Enterprise-only
([Initiatives](https://linear.app/docs/initiatives),
[Sub-initiatives](https://linear.app/docs/sub-initiatives)). A Project is an
outcome-oriented delivery unit that can span Teams. An Issue is the primary work
item; a Sub-issue decomposes one and is itself a full Issue.

Linear has NO native Epic level. A Linear Project is normally the closest
analogue to a Jira, GitLab or Shortcut Epic — but it is not one, and Linear does
not use the word. There is likewise no native release object and no native
metric or key-result object.

## Semantic roles

- Workspace — scope_container. native, required.
- Team — scope_container. native, required: an Issue is always linked to one
  Team and must have a title and a status
  ([Create issues](https://linear.app/docs/creating-issues)).
- Sub-team — scope_container. native_tier_gated (Business and Enterprise;
  nesting past one level is Enterprise), optional.
- Initiative — strategic_goal. configurable then native, optional.
- Sub-initiative — nested strategic_goal. native_tier_gated (Enterprise).
- Project — delivery_group. native, optional; may exist with no Initiative.
- Issue — work_item. native, required; may exist with no Project.
- Sub-issue — sub_item. native, optional.
- Cycle — timebox. configurable then native (per Team), optional.
- Project Milestone — checkpoint. native, optional.
- Custom View — view. native, optional; Initiative views are native_tier_gated
  (Enterprise).
- Document — document. native, optional.
- Pull Request or Merge Request — review_artifact. external, optional.
- strategic_measure — absent. Convention: state it in the Initiative
  description, an initiative update, or an attached Document.
- release_group — absent. Convention: a label, or a Project per release.

## Orthogonal objects

None of these is a parent, and none belongs in the containment chain.

- Cycle — a Team's repeating planning period; Issues are scheduled_in one.
- Project Milestone — a stage inside one Project. Record it as checkpoint_of
  that Project and grouped_by for its assigned Issues; never place it between
  Project and Issue. It cannot be shared across Projects
  ([Project milestones](https://linear.app/docs/project-milestones)).
- Custom View — presentation. Work is visualized_by a View; a board is a display
  mode of a View, not an object.
- Document — long-form, attachable to a Project, Initiative, Team, Issue or
  Cycle; work is documented_by one.
- Pull Request or Merge Request — an Issue is implemented_by one, kept as a
  git-host attachment.

## References and autolinks

Auto-detected in a description or comment body: a bare issue identifier
(`ENG-123`), an `@ENG-123` mention, and a plain issue URL; `@text` also mentions
a user, project, date or document ([Editor](https://linear.app/docs/editor)).
Through the GraphQL API and MCP the documented way to write any mention is the
plain URL of the resource
([Getting started](https://linear.app/developers/graphql)). YouTube, Loom,
Descript and Figma links auto-embed rather than link.

The side effect is what matters. Referencing an Issue in a description or
comment automatically makes it a related issue on the target, visible in that
issue's sidebar ([Issue relations](https://linear.app/docs/issue-relations)),
and mentioning a user notifies their Inbox and subscribes them. Linear inverts
GitHub's default: the cheap idiomatic form also mints a relation. So write bare
`ENG-123` whenever you want that relation, which is most of the time. When you
do not, Linear publishes no opt-out for the body. Whether a titled markdown link
or an inline-code identifier suppresses the relation is UNVERIFIED — Linear
documents no escape syntax and no `redirect.` host equivalent, so do not promise
suppression. The documented remedy is after the fact: hover the related issue
and click the X, or run Remove relation.

Cross-container: an issue ID already carries its owning Team, so `ENG-123`
resolves from any Team in the Workspace and no `team/ENG-123` form exists.
Across Workspaces there is no shorthand; use the full URL
`https://linear.app/<workspace>/issue/ENG-123/<slug>`, assume the reader may
lack access, and carry a one-line human summary beside it — whether such a URL
mentions or relates anything is UNVERIFIED. Moving an Issue to another Team
reissues its identifier; old ones keep resolving
([Edit issues](https://linear.app/docs/editing-issues)).

Pointing from a git host into Linear is where an opt-out is documented: a magic
word plus the issue ID in a pull request title or description (`Fixes ENG-123`)
links the PR and makes Linear post a linkback comment on the git host, while
`Ignore ENG-123` or `skip ENG-123` prevents that link. Magic words in PR
comments create nothing ([GitHub](https://linear.app/docs/github)).

Markdown dialect: Linear converts typed or pasted markdown to rich text and
supports most of it. Two documented divergences from GFM — `+++ Title` opens and
`+++` closes a collapsible section, and a `mermaid` code block renders as a
diagram. `:shortcode:` emoji work; Linear-hosted images sit behind
authentication and will not render outside it. Whether pasted GFM pipe tables
convert is UNVERIFIED, and no commit-SHA autolinking is documented — write
commit refs as full git-host URLs.

## Reading and writing

A local agent has a real backend here; drafting for paste is the fallback.

- Official remote MCP server at `https://mcp.linear.app/mcp` over Streamable
  HTTP, read-only variant at `https://mcp.linear.app/mcp/readonly`. Auth is
  OAuth 2.1 with dynamic client registration, or a bearer API key; tools find,
  create and update issues, projects and comments
  ([MCP server](https://linear.app/docs/mcp)). Prefer this.
- GraphQL API at `https://api.linear.app/graphql`, personal API key in the
  `Authorization` header or an OAuth bearer token. `issueUpdate` takes the
  shorthand `ENG-123` as well as a UUID, and property changes within three
  minutes of creation fold into creation rather than the activity log, so
  create-then-correct stays clean.
- Official TypeScript SDK, `@linear/sdk`. No first-party CLI is documented;
  community CLIs exist, are unofficial, and may not be installed.

## Naming traps

Never say, in Linear-native output:

- "Epic" — Linear has none. Say Project, or Initiative if strategic.
- "Team" or "Sub-team" as a delivery level — both are ownership and workflow.
- `#123` — `#` opens a heading, and Linear has no `#N`. Write `ENG-123`.
- "Milestone" unqualified — say Project Milestone. GitHub's is repo-level and
  GitLab's is a timebox; Linear's lives inside one Project.
- "Sprint" — the timebox is a Cycle, and it is not tied to a release.
- "Release", "Fix Version", "Version" — no such object exists.
- "Board" as an object — it is a display mode of a View.
- "Story", "Task", "Sub-task", "Ticket" — Linear has Issue and Sub-issue.
- "Backlog" as a container — it is a workflow status category.
- "Wiki page", "Confluence page", "Page" — Linear has Documents.
- "OKR", "Key Result", "Goal" as objects — Initiatives and Sub-initiatives carry
  the structure; no numeric target field exists.
