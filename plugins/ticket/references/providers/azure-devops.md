# Azure DevOps (Azure Boards)

## Scope

Organization (on-premises: Project Collection) > Project > Team. An Azure DevOps Project is a durable
container holding Boards, Repos, Pipelines, Artifacts, Wiki, teams and process configuration. A Team is a
subdivision that owns Area Path and Iteration Path subscriptions, not a work-item parent. Every Work Item
belongs to exactly one Project, and its ID is unique across the whole Organization
([About work items](https://learn.microsoft.com/en-us/azure/devops/boards/work-items/about-work-items?view=azure-devops)).

## Native hierarchy

The requirement-level noun depends on the Project's process
([Choose a process](https://learn.microsoft.com/en-us/azure/devops/boards/work-items/guidance/choose-process?view=azure-devops)).
Agile is Epic > Feature > User Story > Task; Scrum is Epic > Feature > Product Backlog Item > Task; CMMI is
Epic > Feature > Requirement > Task; Basic is Epic > Issue > Task and defines no Feature level at all.
Canonical form: Epic > Feature > requirement-level Work Item > Task, joined by Parent/Child links
(`System.LinkTypes.Hierarchy`, tree topology, at most one parent).

- Bug is configurable per Team. The "Working with bugs" setting puts Bug on the requirement backlog, on the
  iteration backlog with Tasks, or off backlogs. Read the Team setting; do not assume a level.
- Epics and Features are the two predefined portfolio backlogs in Agile, Scrum and CMMI; Basic predefines
  only Epics. An inherited process can add custom portfolio backlogs to a total of five and rename any
  level, but levels cannot be reordered and a Work Item Type belongs to exactly one level
  ([Customize backlogs and boards](https://learn.microsoft.com/en-us/azure/devops/organizations/settings/work/customize-process-backlogs-boards?view=azure-devops)).
  Inherited processes also add and rename types, so inspect the process configuration before naming one.
- There is NO native level above Epic and no native goal or key-result object. A level above Epic exists
  only where someone added a custom portfolio backlog.

## Semantic roles

- Organization, Project: scope_container, native, required; everything is contained_by a Project. Team is
  also scope_container (native, required — a default team exists) but groups by Area Path subscription
  rather than by containment.
- Epic, Feature: delivery_group, native, optional, parent_of the level beneath.
- User Story / Product Backlog Item / Issue (Basic) / Requirement (CMMI): work_item, native, required —
  this is the thing the ticket is. Task: sub_item, native, optional, child_of one of those. Bug:
  work_item or sub_item, configurable per Team, optional.
- strategic_goal: absent natively. A custom portfolio backlog above Epic is configurable; anything else is
  convention (tag, field, query). strategic_measure: absent — no native objective or key-result object,
  so measured_by is convention via fields, tags, queries or a dashboard chart.

## Orthogonal objects

None of these is a parent. Never convert any of them into parent_of.

- Iteration Path / Sprint: timebox, native, optional; scheduled_in.
- Area Path: ownership and product grouping, native, required (defaults to the Project root node);
  grouped_by. Most often mistaken for a parent — it is a field, not a link.
- Classic release pipeline stage: release_group and deployment context, native but configurable — the
  Deployment control requires a Classic release pipeline and does not support YAML stages. released_in,
  via the "Integrated in release stage" link. checkpoint: absent natively; milestones are convention.
- Board, Backlog, Taskboard, Query, Dashboard, Delivery Plan: view; visualized_by. Delivery Plans need
  Basic access or higher — Stakeholders cannot use them.
- Wiki page, README: document, native, optional, via the Wiki link type; documented_by. Azure Repos Pull
  Request: review_artifact, native, optional, via the Pull Request external link type; implemented_by.
  Say "Pull Request", never "MR".
- Test Plan, Test Suite, Test Case: review_artifact, native_tier_gated — Test Case Management requires
  Basic + Test Plans access
  ([Access levels](https://learn.microsoft.com/en-us/azure/devops/organizations/security/access-levels?view=azure-devops)).

## References and autolinks

Auto-detected inside a Work Item description, rich-text field or Discussion comment
([About work items](https://learn.microsoft.com/en-us/azure/devops/boards/work-items/about-work-items?view=azure-devops),
[Markdown syntax guidance](https://learn.microsoft.com/en-us/azure/devops/project/wiki/markdown-guidance?view=azure-devops)):

- `#` plus a Work Item ID opens a picker and renders the reference as a link. Leave it bare; do not
  hand-write `[#1234](url)` for a same-Organization item.
- `@` opens the identity picker and the mention emails the target. Never `@`-mention someone merely to name
  them in prose — write the plain name. Through an API the raw form is `@<userID>` in the Markdown editor,
  or an anchor carrying `data-vss-mention` in the HTML editor
  ([Use @mentions](https://learn.microsoft.com/en-us/azure/devops/organizations/notifications/at-mentions?view=azure-devops)).
- `!` opens a pull request picker and inserts a clickable link; documented for GitHub pull requests in a
  connected repository
  ([Link GitHub commits, PRs, branches, and issues](https://learn.microsoft.com/en-us/azure/devops/boards/github/link-to-from-github?view=azure-devops)).
- Escape a hash you do not mean as a reference — write `\#` for hex colors — or the editor offers
  work-item suggestions. In table cells, leave a blank space around a work item or pull request mention.
  Bare URL autolinking is documented for pull request comments and wikis but is UNVERIFIED for Work Item
  fields; use an explicit `[text](url)` there.

Which of those create a side effect on the target:

- `@mention` sends email. Loudest side effect in the product.
- `#ID` inside a Work Item field renders a link in the body. Whether it also writes a relation onto the
  target's Links tab is UNVERIFIED — the docs say "link to another work item" without stating a link
  relation is created. The Comments REST API does return parsed `mentions` with an `artifactType` of person
  or work item, so the reference is recorded on the comment. When a durable, queryable relation is wanted,
  add a real Related or Parent/Child link instead of relying on `#`.
- `#ID` in an Azure Repos commit message creates a Commit link on the work item once pushed; `#ID` in an
  Azure Repos pull request description creates a Pull Request link. Both are real writes
  ([Link work items to objects](https://learn.microsoft.com/en-us/azure/devops/boards/backlogs/add-link?view=azure-devops)).
- From GitHub, `AB#{ID}` creates a link only from a commit message, pull request description, or issue
  description — in a comment or a pull request title it creates nothing. Keywords in front of it
  (`Fixed AB#123`, `Closed AB#123`) also transition the work item's state. That is a mutation, not a
  reference; never emit one unless the user asked for the transition.

Cross-container:

- Another Project, same Organization: IDs are Organization-unique, so `#1234` is not ambiguous, and any
  valid project segment in the URL resolves the item
  ([Rename a project](https://learn.microsoft.com/en-us/azure/devops/organizations/projects/rename-project?view=azure-devops)).
  Whether the `#` picker searches outside the current Project is UNVERIFIED, so write an explicit titled
  link: `[Contoso 1234](https://dev.azure.com/{org}/{project}/_workitems/edit/1234)`.
- Another Organization: `#ID` does not resolve — use the full URL. For a tracked relation use Remote
  Related, Consumes From, or Produces For, which require both organizations to be managed by the same
  Microsoft Entra ID
  ([Link type reference](https://learn.microsoft.com/en-us/azure/devops/boards/queries/link-type-reference?view=azure-devops)).
- Advanced Security alerts are numbered under their repository and have no documented `#`-style shorthand.
  Write a titled link; add the Security Alert link type from the Links tab for a tracked relation.

## Reading and writing

A local agent can read and write for real; this adapter is not paste-only.

- CLI: the `azure-devops` extension for Azure CLI installs on first use and covers `az boards work-item
  create`, `show`, `update`, `delete`, and `az boards work-item relation add` / `remove` / `show` /
  `list-type` ([az boards work-item](https://learn.microsoft.com/en-us/cli/azure/boards/work-item?view=azure-cli-latest)).
  `--description` and `--discussion` take body text; `--fields` sets reference-named fields.

```
az boards work-item create --title "..." --type "User Story" --project "..." --description "..."
```

- REST API: Work Item Tracking. Work items are created and patched with JSON Patch; comments use a
  separate, still preview-versioned endpoint whose body is `{"text": "..."}`
  ([Comments - Add](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/comments/add?view=azure-devops-rest-7.1)).
- MCP: Microsoft ships an official Azure DevOps MCP Server, remote and local. Use the local one from Claude
  Code, Claude Desktop, Cursor and Codex, which cannot authenticate to the remote server with Microsoft
  Entra ID. Requires Node.js 20+
  ([Azure DevOps MCP Server](https://learn.microsoft.com/en-us/azure/devops/mcp-server/mcp-server-overview)).

The Markdown editor for Work Item comments is generally available
([Sprint 259 update](https://learn.microsoft.com/en-us/azure/devops/release-notes/2025/boards/sprint-259-update)),
but existing large text fields such as Description stay in their current format until converted
individually, and a Markdown comment cannot be converted back to HTML. Detect the field's editor before
emitting Markdown; HTML fields need HTML, and a soft line break needs two trailing spaces.

## Naming traps

Never write, in a drafted Azure DevOps body:

- Bare "Project" meaning a delivery_group — an Azure DevOps Project is a scope_container.
- Bare "Issue" — the requirement-level type in Basic, and a separate off-backlog type in Agile and CMMI.
- "Story" in a Scrum or CMMI Project; those types are Product Backlog Item and Requirement, and "User
  Story" is Agile-only.
- "Epic" as a strategic_goal — it is a delivery_group, present in all four processes.
- "Sprint" when you mean the field; the field is Iteration Path. "Area" or Area Path as a parent, an epic,
  or an owner queue — it is a grouped_by field.
- "Release" as a Boards object; releases and stages live in Azure Pipelines. "Backlog", "Board",
  "Taskboard", "Delivery Plan" as containers; all four are views.
- "Ticket", "card", "MR", "sub-task", "milestone", "Team Project" — the natives are Work Item, Pull
  Request, Task, Project, and for milestones nothing at all.
