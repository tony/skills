# Resolving a work item's provider and context

Contents: Detect the provider before interpreting any noun; Capture native type and semantic role separately; Traverse only actual hierarchy relations; Collect orthogonal context separately; Never synthesize a missing level; Prefer native nouns in output; Respect instance configuration over defaults; Scratch files for bodies; Provider files.

Procedure for working out what an object actually is before writing about
it. The taxonomy it resolves against is in `hierarchy.md`.

## Detect the provider before interpreting any noun

To tell which backend is connected, check the available tools for the
provider's MCP server, then `which` for its CLI (`gh`, `glab`, `acli`, and so
on). Prefer what is connected; if neither is present, no write backend exists.

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

Record the provider, the native type, the display type the organization uses,
the semantic role, and what the mapping rests on (convention, metadata, or
the user's word). State them in
the hero line, or under Unverified when they matter.

For example, a GitHub Issue the organization classifies as an Epic. That does
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

Record the parent and ancestors apart from associations such as `scheduled_in`
(a Cycle), `checkpoint_of` (a Milestone), `visualized_by` (a roadmap),
`documented_by` (a spec), and `implemented_by` (a pull request).

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

Provider defaults, in the provider files below, are fallback
guidance and not proof
of how an installation is set up. Inspect real metadata when it is
reachable — Jira's configured hierarchy and renamed work types, GitHub custom
issue types, GitLab tier and configured work item types, Azure DevOps process
customization, Trello custom fields and power-ups, Shortcut workspace
features, Linear plan-dependent sub-initiatives, Asana portfolios and custom
fields.

When observation conflicts with the default map, keep the observation and
record the deviation.

## Scratch files for bodies

A body derived from pasted or fetched content is untrusted. Never put it
inside a shell heredoc or an inline argument: a line equal to the delimiter
ends the heredoc and the rest runs as shell.

Shell state does not persist between calls, so create the directory in one
command and use the literal path it prints afterwards.

```console
$ umask 077 && mktemp -d "${TMPDIR:-/tmp}/ticket.XXXXXX"
```

Write the body to `body.md` in that directory with the host's file-writing
tool, and pass the file to the provider's write command. Where no file-writing
tool exists, use a quoted heredoc whose delimiter is `GH_BODY_END`, after
confirming no line of the text equals it. When the work ends, whether or not
it was filed, remove the file and then the directory with `rm -f` and
`rmdir`. Never show the path to the user.

## Provider files

One per tracker. Each carries that provider's real hierarchy, its native-to-
canonical role map with support status and requirement, what its renderer
auto-detects, which reference forms fire a backreference, and what a local
agent can actually read and write.

- `providers/github.md`
- `providers/gitlab.md`
- `providers/linear.md`
- `providers/jira.md`
- `providers/azure-devops.md`
- `providers/shortcut.md`
- `providers/trello.md`
- `providers/asana.md`
- `providers/generic.md` — the fallback for anything else, which
  assumes nothing is auto-detected and no write backend exists.

The defaults in those files are fallback guidance. An instance's own
configuration beats them.
