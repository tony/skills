# Asana

## Scope

Workspace or Organization contains Teams; a Team contains Projects; a Project belongs to
exactly one Team and holds Sections; a Section groups Tasks; a Task carries Subtasks up to
five levels deep. Portfolios sit beside this chain and gather Projects or Portfolios.

The chain is not single-parent at the Task level. The object hierarchy doc states:
"Tasks can be orphaned and belong to no projects, they can belong to one project, or
they can be multi-homed across two or more projects," and "Subtasks do not inherit the
projects of their parent tasks." Treat `contained_by` for a Task as a set, and never
assume a Subtask is visible in its parent's Project.
Source: https://developers.asana.com/docs/object-hierarchy

## Native hierarchy

Portfolio is tier-gated to Advanced and above; a Project may sit in more than one
Portfolio. Project is the principal delivery container. Section is project-local ordering
and grouping — a phase, column, or category; a Task occupies one Section per Project it is
homed in, and a Section is not a container of record. Subtask is itself a full Task with
the same fields.

There is NO native timebox: Asana ships no Sprint, Iteration, or Cycle object. There is
NO native release group: nothing corresponds to a GitHub Milestone, a GitLab Milestone,
or a Jira Version. Do not invent one. Teams approximate both with a Section, a
dedicated Project, a Portfolio, or a custom field — convention, not a native level.

Task subtypes are a field, not a label: `resource_subtype` takes `approval`, `custom`,
`default_task`, or `milestone`. Source: https://developers.asana.com/reference/tasks

## Semantic roles

- Workspace / Organization — scope_container. native, required.
- Team — scope_container, second level. native, required for a Project in an Organization.
- Portfolio — delivery_group, higher order. native_tier_gated (Advanced+), optional.
- Project — delivery_group, principal. native, required.
- Section — delivery_group, project-local. native, optional. `grouped_by`, never `parent_of`.
- Task — work_item. native, required.
- Subtask — sub_item. native, optional. `child_of` its Task.
- Task with `resource_subtype: milestone` — checkpoint. native, optional. `checkpoint_of`
  a Project; per the Tasks reference it cannot carry a start date.
- Task with `resource_subtype: approval` — review_artifact. native_tier_gated (Advanced+),
  optional. https://help.asana.com/s/article/how-to-use-approvals
- Goal — strategic_goal. native_tier_gated (Advanced+), optional.
- Goal metric — strategic_measure. native_tier_gated, optional. Written via
  `POST /goals/{goal_gid}/setMetricCurrentValue`.
  https://developers.asana.com/reference/updategoalmetric
- Project brief, and Project or Portfolio status update — document. native, optional.
- Project views (List, Board, Timeline, Calendar) and saved reporting — view. native,
  optional, `visualized_by`.
- timebox and release_group — absent natively; convention only.

## Orthogonal objects

None of the following is a parent of a work item. A Milestone Task is `checkpoint_of` a
Project: it marks a date, holds nothing under it, groups nothing. A Project brief is
`documented_by` on the Project; a status update is `documented_by` on the Project,
Portfolio, or Goal it reports on. Project views are `visualized_by` — switching to Board
view changes no containment. An Approval Task is a `review_artifact` in the Task graph;
it does not own the work it gates. Task `dependencies` / `dependents` are `blocks`.

Goal relationships attach supporting work: a `goal_relationship` links a `supported_goal`
to a `supporting_resource`, documented as "another goal, a project, or a portfolio," with
`resource_subtype` values such as `subgoal`. Model as `implemented_by` or `measured_by`,
never `parent_of`. Source: https://developers.asana.com/reference/goal-relationships

## References and autolinks

First axis, auto-detection: Asana's renderer detects nothing in plain text. No `#N`, no
issue key, no sigil, no commit-SHA autolink. A Task identifier is an opaque numeric `gid`
that renders as literal digits and tells a reader nothing. The GitHub instinct "leave it
bare" inverts here — a bare reference in Asana is always noise, so every reference must
be an explicit link.

Body format is HTML, not markdown. "The rich text field name for an object is equivalent
to its plain text field name prefixed with `html_`" — `html_notes` on a Task, `html_text`
on a comment. Content must be valid XML wrapped in `<body>`. Supported tags: `<body>`,
`<strong>`, `<em>`, `<u>`, `<s>`, `<code>`, `<ol>`, `<ul>`, `<li>`, `<a>`, `<blockquote>`,
`<pre>`, `<h1>`, `<h2>`, `<hr/>`, `<img>`, `<table>`, `<tr>`, `<td>`, `<object>`. "Only
`<a>` tags support attributes, and any attributes on other tags will be similarly
rejected." Unsupported tags return 400. The object-link form is a GID anchor: write
`<a data-asana-gid="123"/>` and "if you have access to that object, the API will
automatically generate the appropriate `href` and other attributes for you." Mentionable
types are `user`, `task`, `project`, `tag`, `conversation`, `project_status`, `team`,
`search`. Add `data-asana-dynamic="false"` to keep your own anchor text instead of the
live object name. Source: https://developers.asana.com/docs/rich-text

Second axis, side effects on the target: one case is documented, and it is the one to be
careful with. Asana's help docs state that @mentioning a PERSON in a task description or
comment adds them as a collaborator on the task and sends them an Inbox notification — a
user mention is a write against a human's queue. To merely name someone, write their name
as plain text and do not link the user GID.
Source: https://help.asana.com/s/article/collaborating-in-asana

UNVERIFIED: whether mentioning a Task, Project, Portfolio, or Goal produces any visible
backreference — story, activity entry, or notification — on the target. Asana's help
material describes object mentions only as creating a link that connects work; no official
page found states a target-side event, and the Stories reference publishes no enumerated
`resource_subtype` list in which such an event could be confirmed. Assume no backreference
exists: if the connection must be discoverable FROM the target, a description link is not
enough — use a native relation (dependency, subtask, multi-home, or goal relationship).

Cross-container: a `gid` is unique across the workspace, so the link form for a Task in
another Project, Team, or Portfolio is identical — there is no `owner/repo#N`-style
qualifier and no cross-container penalty to weigh. Across workspaces, or for a reader
without access, the GID anchor will not resolve for them; use the object's `permalink_url`
in a plain `<a href="...">`, expect a permission wall rather than a broken link, and name
the object in prose as well as linking it. UNVERIFIED: whether pasting a bare
`app.asana.com` URL auto-converts into a titled smart link. Write the anchor.

## Reading and writing

A local agent has a real backend. Prefer the official MCP server, V2, generally available
at `https://mcp.asana.com/v2/mcp` over Streamable HTTP with OAuth. Documented tools include
`search_objects`, `get_task`, `get_my_tasks`, `search_tasks`, `get_project`, `create_tasks`,
`update_tasks`, `add_comment`, and `create_project_status_update`, plus preview tools that
render a confirmation UI before committing. Tokens issued for MCP apps work only against
the MCP server, not the standard REST API. Otherwise use the REST API at
`https://app.asana.com/api/1.0` with a personal access token or OAuth, plus the official
Python or JavaScript client library — the Java and Ruby libraries are discontinued.
Sources: https://developers.asana.com/docs/mcp-tools-reference and
https://developers.asana.com/docs/client-libraries

UNVERIFIED as absent: no first-party Asana CLI appears in the developer docs, which point
to cURL, Postman, and the API explorer instead. Treat "there is no official CLI" as an
argument from absence, not a cited statement.

The writing gotcha that outranks the rest: send HTML, never markdown. A body drafted in
markdown is stored and displayed as literal asterisks and brackets. Convert before the
write, and validate the fragment parses as XML.

## Naming traps

- Never say "Milestone" to mean a grouping of work. An Asana Milestone is a Task subtype
  and a checkpoint; do not translate a GitHub Milestone, GitLab Milestone, or Jira Version
  into one by name.
- Never say "Story" to mean a unit of work. In Asana a Story is an activity-feed event or
  comment on a Task. The work item is a Task.
- Never say bare "Project". An Asana Project is a delivery_group, not the scope_container
  a Jira Project is. Qualify it on first use in cross-provider text.
- Never say "Section" to mean containment; it is project-local grouping.
- Never say "Portfolio" to mean a container of Tasks; it gathers Projects and Portfolios.
- Never say "Sprint", "Iteration", "Cycle", "Epic", "Version", or "Release" as if Asana has
  such an object. Name what the team actually built — a Section, a Project, a Portfolio, a
  custom field — and say it is a convention.
- Never say "Tag" to mean a container; it is a cross-project label.
- Never assume one Project per Task. Multi-homing is normal Asana practice, so "move this
  to Project X" may need to be "also add it to Project X."
