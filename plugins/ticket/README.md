# ticket

Manage work across trackers (Linear, Jira, GitHub, etc.) respecting each
platform's native object graph. Drafts durable tickets focused on
invariants.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install ticket@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add ticket@skills
```

The skills below are written with Claude Code's leading slash. Codex uses
the same names without it, so `/ticket:…` there is `ticket:…`.

## Components

### `/ticket:draft` (skill)

Writes a new item into Linear, Jira, GitLab, Shortcut, Azure DevOps, Trello,
Asana, or GitHub. Resolves the provider and the object's semantic role before
drafting, reads the container's real templates and configured work types,
searches for the thing that already exists, gathers evidence, then presents
the full title and body before anything is filed.

Files through a real backend where one exists. Where none does, it renders,
presents, and emits the approved text to paste, and says that is what it is
doing.

### `/ticket:rebuild` (skill)

Takes one live item that grew wrong and rebuilds it. Sorts the existing body
into keep, cut, relocate, demote, and repair; reports what the item is
missing; then shows a diff and updates only on approval.

Nothing valuable is deleted. Depth that does not belong at the item's
altitude is relocated into a document, and the item links to it.

## The three tenses

The whole plugin is one content contract, applied per tense.

**Past.** Carry what cannot be recovered from the repository — a measurement
with the conditions that produced it, a dead end with the reason it died, a
retracted number with what was actually measured. Drop anything a reader gets
by opening the file or reading the log.

**Present.** No reference that rots, and none that mints a backlink you did
not want. Auto-linking is not free: on most trackers a bare reference posts a
visible event onto the thing you referenced.

**Future.** A handful of invariants, each passing one test — *if violated, is
the work pointless, or is a neighbour broken?* Everything else is intent,
labelled non-binding. No checkbox definition of done, and no measurement
threshold as a gate.

## Providers are typed graphs, not one ladder

There is no universal `Initiative > Epic > Project > Milestone > Issue >
Task`. That sequence conflates scope containment, strategic planning, work
decomposition, timeboxes, release groupings, checkpoints, views,
documentation, and implementation — nine independent kinds of relationship.

So the plugin resolves each object to a canonical role and keeps the
provider's own noun in the output. A Linear Project is a delivery group whose
closest Jira analogue is an Epic, and calling it an Epic in Linear-native
output is wrong. A GitLab merge request is not a pull request. A GitHub
Milestone, a Linear Project Milestone, and an Asana Milestone are three
unrelated things sharing a word.

`references/hierarchy.md` holds the roles and the collisions.
`references/providers/` holds one file per provider: its real hierarchy, what
its renderer auto-detects, which reference forms create a backlink, and what
a local agent can actually read and write.

## Relationship to `gh`, `pr`, and `lean`

### Reach for `ticket` when

The tracker is not GitHub, or the object is not a single issue — an epic, a
project, an initiative, a document — or an existing item needs rebuilding.

### Reach for `gh` when

You are filing an ordinary GitHub issue. `gh:create-issue` is more
specialized for that one case, and `/ticket:draft` hands off to it.

### Reach for `pr` when

You are describing a branch. `pr` owns pull request bodies in more depth, and
this plugin's `review_artifact` role defers to it.

### Reach for `lean` when

The text already says the right things and needs to say them in fewer words.

## Prerequisites

`gh` for GitHub. Everything else is optional — each provider file states what
a local agent can reach, and every adapter degrades to drafting and emitting
approved text rather than failing.

The mechanical slop checks resolve the registry shipped by the `pr` or `slop`
plugin at runtime. When neither is installed, those checks are skipped with a
one-line notice and the judgment-based rules still apply.
