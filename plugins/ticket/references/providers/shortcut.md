# Shortcut

Contents: Scope; Native hierarchy; Semantic roles; Orthogonal objects; References and autolinks; Reading and writing; Duplicate search; Naming traps.

## Scope

Organization > Workspace. An Organization holds a collection of Workspaces, and
["Workspaces are independent of each other"](https://www.shortcut.com/help/admin/workspace-management/)
with no reporting across them. Everything below lives inside one Workspace. Team
(`Group` in the REST API) is a cross-functional squad that owns and filters
Stories, Epics, and Iterations (an ownership dimension, not a containment level):
a Story belongs to a Workspace and carries a Team field.

## Native hierarchy

Objective > Epic > Story > Sub-task. Shortcut has no native Project work
level and no release object: the
[REST API](https://developer.shortcut.com/api/rest/v3) lists none.

- **Objective** is ["Shortcut's top-level planning object"](https://www.shortcut.com/help/objectives/objectives-overview/).
  A *Tactical Objective* is Epic-driven and on all plans; it becomes *Strategic*
  once it has a Key Result, which is plan-gated.
- **Epic** aligns to an Objective directly, or to a Key Result on a Strategic
  Objective. Stories have no Objective field; a Story reaches an Objective only
  through its Epic.
- **Story** is the standard unit of work and the only object required to record
  work. Story types (Feature, Bug, Chore) classify a Story; they add no level.
- **Sub-task** is toggled at Settings > Features. It is itself a Story carrying
  `parent_story_id` and inheriting the parent's Epic and Team; disabling leaves
  ["any Sub-tasks that were created ... still visible as individual Stories"](https://www.shortcut.com/help/stories/sub-tasks/).

## Semantic roles

- **Workspace**: scope_container. native, required.
- **Team (`Group`)**: ownership dimension, not a role in the chain. native,
  optional. `grouped_by`, never `contained_by`.
- **Objective**: strategic_goal. native (Tactical) / native_tier_gated
  (Strategic). optional.
- **Key Result**: strategic_measure. native_tier_gated, optional. An aligned
  Epic is `measured_by` it, never `child_of`: progress is updated manually, not
  rolled up from Story or Epic completion.
- **Epic**: delivery_group. native, optional. `grouped_by` an Objective.
- **Story**: work_item. native, required.
- **Sub-task**: sub_item. configurable (Workspace toggle), optional. `child_of`.
- **Story Relationship (`StoryLink`)**: native link types blocks, duplicates,
  relates to; record as `blocks` and `relates_to`. native, optional.

## Orthogonal objects

- **Iteration**: timebox. native, optional. Stories are `scheduled_in` it.
- **release_group**: absent. The REST API has no release or version object; use a Label or
  Custom Field by convention and say which.
- **checkpoint**: absent. The REST API has no phase or dated-checkpoint object; its
  Milestones are marked deprecated in favor of Objectives ([REST API](https://developer.shortcut.com/api/rest/v3)).
- **Epic Health / Objective Health**: no canonical role. native, optional. A
  dated status (On Track, At Risk, Off Track) with a comment, kept as health
  history. It reports on progress rather than marking a point in it.
- **Space**: view. native, optional. A saved, filtered, shareable tab on the
  Stories page. `visualized_by`, never `contained_by`.
- **Roadmap**: view. native, optional. Teams and Epics in a Table or Timeline.
- **Doc**: document. native, optional. `documented_by`. Docs link to Stories,
  Epics, Iterations, Objectives, and other Docs.
- **Pull request / merge request**: review_artifact, external. `implemented_by`.
  Use the code host's own noun.

## References and autolinks

**Auto-detected in a Story or Epic body.** The Story Dialog resolves
[`sc-XXXXX` or `#XXXXX`](https://www.shortcut.com/help/stories/stories-overview/)
to a Story in the same Workspace. Write the bare token; do not wrap it in a
markdown link. `@member` and `@team-handle` are resolved in Story and Epic
descriptions and comments, and in Objective and Iteration descriptions
([Teams](https://www.shortcut.com/help/teams/teams-overview/)). No body-text
shorthand for an Epic, Objective, Iteration, or Doc is documented; none is
documented, so use the permalink rather than guess a sigil.

**Which references have a side effect on the target.** An `@` mention does: it
stores `member_mention_ids` / `group_mention_ids` on the object and raises email,
Slack, and browser notifications plus an Activity Feed entry for the person or
Team named ([Notifications](https://www.shortcut.com/help/account/notifications/)).
Treat every `@` as paging a human; to credit someone without paging them write
their plain name, since no documented escape renders an `@` handle inert.

A bare `sc-XXXXX` / `#XXXXX` is not documented to write anything to the target.
Shortcut's two-way mechanisms are structural, not textual: a Story Relationship
is one `StoryLink` record (subject, verb, object) listed in `story_links` on both
Stories, and Doc
["Relationships are a two-way street; the link is shown from both the Doc and the entity being linked"](https://www.shortcut.com/help/docs/docs-overview/).
So set the relationship field when the link must exist on the other object; the
inline token is enough when it is only context.

**Other Workspace.** Story public IDs are per-Workspace and `#123` resolves
against the reading Workspace, so a bare token aimed at another Workspace
silently points at the wrong Story. Use a titled markdown link around the
permalink copied from that Story's dialog, which embeds the Workspace URL slug.
Assume it registers nothing on the target, and that the reader may lack access.

**Code host.** Do not narrate PR URLs in the body; let the VCS integration attach
them. Reference runs git-to-Shortcut, using
[`[sc-123]`](https://www.shortcut.com/help/integrations/github/) or the Story URL
in a commit message, PR title, PR description, or PR comment, or a branch
containing `/sc-<story-id>/`. Each has side effects: the commit, branch, or PR is
displayed on the Story, and a configured commit verb or event handler can move
its Workflow State. `[skip-sc]` in the PR title or body (or the `skip-sc` label)
blocks that movement, and `[sc-new-story]` **creates a Story**; never emit
either as filler. Making `sc-123` clickable on the GitHub side is a per-repo
[autolink reference](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/configuring-autolinks-to-reference-external-resources),
not automatic. Going the other way, `#123` inside a Shortcut body means Story
123, never use `#N` for a GitHub or GitLab issue there; write the full URL.

## Reading and writing

Prefer Shortcut's MCP server, found through the connected tool list (`resolve.md`,
"Finding the backend"); its setup and coverage are documented at
[MCP Server docs](https://www.shortcut.com/help/integrations/mcp-server/). Use a tool that
creates or updates Stories. Objectives and Key Results are not writable unless the tool
list shows a tool for them; otherwise print the body to paste. The fallback is the
[REST API v3](https://developer.shortcut.com/api/rest/v3), whose read recipe below is
also its check: `curl -f` fails on a rejected token or a wrong id.

### Read recipe

Read a Story over REST, saving the output for the checks (body field path
`description`). The Story object carries a `comments` array, and requests send the
token in the `Shortcut-Token` header ([REST API v3](https://developer.shortcut.com/api/rest/v3)):

```console
$ curl -fsS \
    -H "Shortcut-Token: $SHORTCUT_API_TOKEN" \
    https://api.app.shortcut.com/api/v3/stories/<story-public-id> > "<scratch dir>/first.json"
```

`PUT /api/v3/stories/{story-public-id}` takes `description` for a rewrite.

## Duplicate search

Shortcut's `is:archived` search operator selects archived Stories
([Archiving FAQ](https://help.shortcut.com/hc/en-us/articles/360018662831-Archiving-in-Shortcut-FAQ)).
The [MCP docs](https://www.shortcut.com/help/integrations/mcp-server/) list no search
tool or parameters, so read the schema the connected server reports.

## Naming traps

Never say **ticket** or **issue**; say Story. Never say **sprint**; say
Iteration. Never say **board**; say Workflow. Never say **milestone**: the REST API marks it deprecated in favor of Objectives.
Never say **Group**: the API's `group_id` field is the Team field. Never say **Project** for a delivery
grouping; the delivery_group is an Epic. Never call a **Space** a container; it is a saved filtered view. Never call
an **Epic** the top-level goal, or a **Key Result** a parent of an Epic. Never
conflate a **Task** (checklist item, `/stories/{id}/tasks`) with a **Sub-task**
(child Story, `/stories/{id}/sub-tasks`).
