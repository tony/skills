# Resolving a work item's provider and context

Procedure for working out what an object actually is before writing about
it. The taxonomy it resolves against is in `hierarchy.md`.

## Detect the provider before interpreting any noun

Use evidence in this order, stopping at the first that answers:

1. The connected provider or API object type.
2. The canonical object URL.
3. The repository remote URL.
4. Integration metadata.
5. An explicit statement from the user.
6. A branch-name or ticket-key convention.
7. Textual inference — last resort, and say that you inferred.

Key shape is not provider evidence. `#123` fits GitHub, GitLab, and Azure
DevOps. `ENG-123` fits Jira, Linear, and Shortcut. The words `Epic`,
`Project`, `Task`, and `Milestone` identify nothing.

## Capture native type and semantic role separately

Both, always. One keeps output correct; the other permits cross-provider
reasoning. Neither substitutes for the other.

```yaml
provider: github
native_type: issue
native_display_type: Epic
semantic_role: delivery_group
mapping_basis: convention
```

That reads as a GitHub Issue the organization classifies as an Epic. It does
not mean GitHub exposes a native Epic object, and the body must not imply
that it does.

## Traverse only actual hierarchy relations

Retrieve the native object, follow explicit parent links upward, record the
ancestor path, and stop when there is no parent, access is denied, or the
provider has no such concept. Follow child links only when they are useful.

Do not infer a parent because two items share a project, a milestone, a
sprint, a cycle, an iteration, a version, a board, a label, a document, or an
assignee. Shared membership is `grouped_by`, `scheduled_in`, or
`visualized_by` — never `parent_of`.

## Collect orthogonal context separately

After the parent chain resolves, gather strategic goals, strategic measures,
timeboxes, release groupings, checkpoints, views, documents, dependencies,
and implementation artifacts into their own structure.

```yaml
hierarchy:
  parent: ENG-100
  ancestors:
    - ENG-50

associations:
  scheduled_in: Cycle 42
  checkpoint_of: Public Beta
  visualized_by: Authentication Roadmap
  documented_by: Login Migration Spec
  implemented_by: github:acme/api#456
```

## Never synthesize a missing level

The absence of a level is information. Report it.

A GitHub issue with no parent is an issue with no parent — not an implied
epic. A Linear issue with no project is reported with its team; a project is
not inferred from labels or title wording. A Jira story with no epic is
unparented, and its sprint or version is not its parent. A Trello card is
reported with its board and list, with no epic or project semantics unless
workspace evidence establishes them. An Azure DevOps user story with no
feature is reported as-is, whatever its area path, iteration, or board
suggests.

## Prefer native nouns in output

Good: `Linear Project "Authentication Refresh"`. `GitLab Epic "Authentication
Refresh"`. `GitHub Issue #100, type Epic`. `Jira Epic AUTH-100`. `Azure
DevOps Feature 100`. `Trello Card "Authentication Refresh", used by this
board as an epic`. `Asana Milestone "Public Beta", a milestone Task`.

Bad: `Epic "Authentication Refresh"` when the provider is Linear. `Project
"Authentication Refresh"` when the object is a GitHub Project view. `PR !42`
for a GitLab merge request. Bare `Task` or bare `Milestone` when the reader
cannot tell which provider's meaning applies.

When a cross-provider comparison is necessary, state the native object, its
canonical role, the closest analogue, and the material mismatch:

`Linear Project (delivery group). Closest Jira analogue: Epic. Unlike a Jira
Space, it is not the root work container.`

## Respect instance configuration over defaults

Provider defaults in `providers/<name>.md` are fallback guidance, not proof
of how an installation is set up. Inspect real metadata when it is
reachable — Jira's configured hierarchy and renamed work types, GitHub custom
issue types, GitLab tier and configured work item types, Azure DevOps process
customization, Trello custom fields and power-ups, Shortcut workspace
features, Linear plan-dependent sub-initiatives, Asana portfolios and custom
fields.

When observation conflicts with the default map, keep the observation and
record the deviation.

## Capture model

Fill what the provider data supports. Leave the rest out rather than
guessing.

```yaml
provider: github | gitlab | linear | trello | jira | azure_devops | shortcut | asana
source_url: string

native:
  object_type: string
  display_type: string | null
  id: string
  title: string
  aliases: [string]

semantic:
  role: scope_container | strategic_goal | strategic_measure | delivery_group |
        work_item | sub_item | timebox | release_group | checkpoint | view |
        document | review_artifact
  mapping_basis: native | native_tier_gated | configurable | convention | external
  confidence: explicit | configured | inferred

scope:
  container: { provider, type, id, title }

hierarchy:
  parent: object | null
  ancestors: []
  children: []

associations:
  strategic_goals: []
  strategic_measures: []
  timeboxes: []
  release_groups: []
  checkpoints: []
  views: []
  documents: []
  implementation: []
  dependencies: []

availability:
  support_status: native | native_tier_gated | configurable | convention | external | absent
  requirement: required | optional | not_applicable
  tier_or_configuration_notes: string | null

evidence:
  provider_metadata: []
  explicit_links: []
  conventions: []
  unresolved_ambiguities: []
```

## Reporting context back

Summarize in provider-native language, one labelled line per relation.

```text
Work item:      Linear Issue ENG-142, "Support passkeys"
Delivery:       Linear Project "Authentication Refresh"
Strategic:      Linear Initiative "Account Security"
Checkpoint:     Linear Project Milestone "Public Beta"
Timebox:        Linear Cycle 42
Documentation:  Linear Document "Passkey Design"
Implementation: GitHub Pull Request acme/api#456
```

For a convention-based hierarchy, say that it is one.

```text
Work item:      GitHub Issue #142, type Feature
Parent:         GitHub Issue #100, type Epic
                delivery group by organization convention
Release:        GitHub Milestone "v3.0"
Planning view:  GitHub Project "Authentication Roadmap"
Implementation: GitHub Pull Request #456
```
