# Provider-aware planning hierarchy

## Core rule

Treat planning systems as provider-specific typed graphs, not as one
universal hierarchy.

Never assume `Initiative > Epic > Project > Milestone > Issue > Task`. That
sequence conflates relationships that are independent of each other:

- **Scope containment** — organization, workspace, group, repository, Jira
  Space, Azure DevOps Project, Trello Board.
- **Strategic planning** — initiative, objective, theme, key result.
- **Work decomposition** — epic, project, feature, issue, story, task,
  subtask.
- **Timeboxes** — sprint, cycle, iteration.
- **Release groupings** — milestone, version, release.
- **Checkpoints** — project milestone, phase, target date.
- **Views** — board, list, roadmap, plan, saved view.
- **Documentation** — document, wiki, Confluence page, specification.
- **Implementation** — pull request, merge request, branch, commit.

A milestone does not normally parent an issue. A board visualizes work. A
document contextualizes work. A pull request implements work. Preserve the
distinctions.

## Canonical semantic roles

Internal role names, deliberately belonging to no provider.

**`scope_container`** — a durable namespace or ownership boundary in which
work exists. GitHub Repository, GitLab Project, Jira Space, Azure DevOps
Project, Linear Team, Trello Board, Shortcut Workspace.

**`strategic_goal`** — a long-range outcome or portfolio-level object. Linear
Initiative, Shortcut Objective, GitLab Objective, a Jira work item configured
above Epic.

**`strategic_measure`** — a measurable result attached to a strategic goal.
Shortcut Key Result, GitLab Key Result. Not executable delivery work unless
the provider or the organization explicitly treats it that way.

**`delivery_group`** — a bounded body of work larger than an ordinary work
item. Jira Epic, Linear Project, GitLab Epic, Shortcut Epic, Azure DevOps
Epic or Feature, a GitHub parent Issue used as an Epic by convention.

**`work_item`** — the principal assignable unit. GitHub Issue, GitLab Issue,
Linear Issue, Jira Story/Task/Bug, Azure DevOps User Story or Product Backlog
Item, Shortcut Story, Trello Card.

**`sub_item`** — a smaller unit beneath a work item. GitHub Sub-issue, GitLab
Task, Linear Sub-issue, Jira Subtask, Azure DevOps Task, Shortcut Sub-task,
Trello checklist item.

**`timebox`** — a fixed planning period. Jira Sprint, Linear Cycle, GitLab
Iteration, Shortcut Iteration, Azure DevOps Iteration, GitHub Project
iteration field.

**`release_group`** — work collected against a release. Jira Version or
Release, GitHub Milestone used for a release, GitLab Milestone used for a
release.

**`checkpoint`** — a stage, phase, or date inside a larger delivery effort.
Linear Project Milestone, a due date, a custom phase field.

**`view`** — a presentation or saved collection. GitHub Project, GitLab Issue
Board, Jira Board or Plan, Linear View, Shortcut Space or Roadmap, Azure
DevOps Board or Delivery Plan.

**`document`** — long-form contextual material. Linear Document, Shortcut
Doc, GitHub wiki page or repository file, GitLab wiki page, a linked
Confluence page, Azure DevOps wiki page.

**`review_artifact`** — the code-review object implementing one or more work
items. GitHub Pull Request, GitLab Merge Request, Azure Repos Pull Request,
or an external PR/MR linked from a tracker that does not host code.

## Relation vocabulary

Use these names. They preserve semantics that a generic "parent" would erase.

`contained_by` — namespace or ownership containment.
`parent_of` / `child_of` — actual work decomposition.
`grouped_by` — portfolio, milestone, or collection membership.
`scheduled_in` — timebox assignment.
`released_in` — release or version assignment.
`checkpoint_of` — phase or checkpoint within a delivery group.
`visualized_by` — board, roadmap, plan, or saved view.
`documented_by` — linked documentation.
`implemented_by` — pull request, merge request, branch, or commit.
`measured_by` — key result or other strategic measurement.
`blocks` — dependency.
`relates_to` — non-hierarchical association.

Never convert `grouped_by`, `scheduled_in`, `released_in`, `checkpoint_of`,
`visualized_by`, `documented_by`, or `implemented_by` into `parent_of`.

## Support and requirement are two fields

Record whether a concept exists separately from whether it is mandatory.

Support status is one of `native`, `native_tier_gated` (native but dependent
on subscription level), `configurable` (shape or name depends on instance
configuration), `convention` (represented through a generic object, label,
type, field, or naming habit), `external` (owned by another connected
system), or `absent`.

Requirement is one of `required` (the child cannot exist without it),
`optional`, or `not_applicable`.

Collapsing the two loses real information. A GitLab Epic is
`native_tier_gated` and `optional`. A Jira Subtask parent is `native` and
`required`. A Trello Epic is normally `absent`, and `convention` only when
the workspace has explicitly defined one.

## Native naming

Lead with the provider's own noun, then the role:

`<Provider> <native object> (<semantic role>)`

Linear Project (delivery group). GitHub Project (planning collection and
view). GitLab Project (development container). Jira Space (work container;
former name: Jira Project). Atlassian Project (status and reporting object).
Linear Project Milestone (checkpoint inside a Project). Trello Card (generic
work object).

When translating between providers, say **closest analogue**, never
**equivalent**, and name the mismatch:

- Linear Project; closest Jira analogue: Epic.
- GitLab Project; closest GitHub analogue: Repository plus repository-level
  collaboration features — not GitHub Project.
- GitHub Milestone; closest Jira analogue: Version, when used for a release.
- Shortcut Objective; closest Linear analogue: Initiative, with different key
  result semantics.

## Dangerous collisions

**Project.** GitHub Project is a collection and view. GitLab Project is a
development container holding a repository. Linear Project is a delivery
group. Jira Space is the work container formerly called a Jira Project, while
Atlassian Project is a separate status and reporting object. Azure DevOps
Project is a development and service container. Asana Project is a delivery
container holding Tasks. Trello and Shortcut have no native Project work
object. Never emit the unqualified noun when the provider is ambiguous.

**Epic.** Native in Jira, GitLab (tier-gated), Azure DevOps, and Shortcut. In
GitHub it is an issue type or a parent-issue convention. In Linear it is
absent — the Project occupies the comparable role, and calling it an Epic in
Linear-native output is wrong. In Trello it exists only by convention.

**Initiative and Objective.** Linear Initiative is a native strategic
grouping of Projects. Shortcut Objective is the native top level above Epics.
Jira Initiative is usually a configured level above Epic and may not exist.
GitLab Objective belongs to a separate OKR family. Map by strategic meaning,
never by spelling.

**Milestone.** GitHub Milestone groups issues and pull requests. GitLab
Milestone groups issues, epics, and merge requests. Linear Project Milestone
is a checkpoint inside one Project. Asana Milestone is a single Task subtype.
Jira has no universal Milestone object. Never map this noun by name alone.

**Task.** A Jira Task sits at Story and Bug level. A GitLab Task is a child
beneath an Issue. An Azure DevOps Task is a child beneath a requirement-level
work item. An Asana Task is the primary work item. Four different altitudes,
one word.

**Issue.** Primary work item in GitHub, GitLab, and Linear. In Jira it is the
legacy and API-facing term for Work Item. In the Azure DevOps Basic process
it is a specific requirement-level type. Closest analogues elsewhere:
Shortcut Story, Trello Card, Asana Task.

**Sprint, Cycle, Iteration.** The same broad concept under provider-native
names. Keep the native noun. Do not press Milestone into service as the
universal timebox.

**Board.** A Trello Board physically contains cards. Everywhere else a board
is a view. Never infer ownership or parentage from board membership.

**Pull Request and Merge Request.** GitHub and Azure Repos say Pull Request.
GitLab says Merge Request. Trackers without a code host name the artifact
after its host. Emitting "Pull Request" for a GitLab merge request is a
correctness error, not a style preference.

## Provider files

One per tracker. Each carries that provider's real hierarchy, its native-to-
canonical role map with support status and requirement, what its renderer
auto-detects, which reference forms fire a backreference, and what a local
agent can actually read and write.

- `references/github.md`
- `references/gitlab.md`
- `references/linear.md`
- `references/jira.md`
- `references/azure-devops.md`
- `references/shortcut.md`
- `references/trello.md`
- `references/asana.md`
- `references/generic.md` — the fallback for anything else, which
  assumes nothing is auto-detected and no write backend exists.

The defaults in those files are fallback guidance. An instance's own
configuration beats them, per `references/resolve.md`.
