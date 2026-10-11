# Jira

Contents: Scope; Native hierarchy; Semantic roles; Orthogonal objects; References and autolinks; Reading and writing; Duplicate search; Naming traps.

## Scope

Atlassian Site (tenant) > Jira Space (scope_container) > Jira Work Item
(work_item).

Jira's API and JQL use `project`, `issue`, and `issuetype` for the objects the
Cloud UI calls Space, Work Item, and Work Type. Use the instance's names in
prose and the API's field names in requests. An Atlassian Project is a separate
status and reporting record; a Confluence Space is also a different object.

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
A Jira Task is level 0 (beside Story and Bug, never beneath them) and nothing
sits between the Epic level and the standard level.

The level-1 type can be renamed and still stays level 1. Levels above 1 are
configurable and plan-gated, named whatever the org
chose: Initiative, Theme, Program, Capability ([custom hierarchy levels](https://support.atlassian.com/jira-software-cloud/docs/configure-custom-hierarchy-levels-in-advanced-roadmaps/)).
Never assert Initiative exists, or sits at a given level, without reading the
instance's work type hierarchy.

A work item must belong to a Jira Space and a Subtask requires a parent, but a
standard work item needs no Epic-level parent: an unparented Story is
unparented, not an implied Epic.

## Semantic roles

- **Jira Space**: scope_container; native, required.
  Every work item is `contained_by` exactly one.
- **Epic-level work item**: delivery_group; native, optional; `parent_of`
  standard work items.
- **Configured level above Epic**: strategic_goal; native_tier_gated and
  configurable, optional; absent where the plan lacks them.
- **Standard work item** (Story, Task, Bug, Incident, Request), work_item;
  native, required as the thing written.
- **Subtask**: sub_item; native, optional, `child_of` required once created.
- **Linked work items** (blocks, is blocked by, relates to, duplicates),
  `blocks` and `relates_to`; native, optional, reciprocal by construction.
- **strategic_measure**: absent natively; convention only, via a custom field
  or a configured Work Type. Do not present it as native.

## Orthogonal objects

- **Sprint**: timebox; native to Jira Software, optional; `scheduled_in`.
- **Version**, surfaced as Release: release_group; native, optional;
  `released_in`.
- **Board**: view; native, optional; `visualized_by`. A filter, not a
  container.
- **Plan** (cross-Space): view; native_tier_gated, optional; `visualized_by`.
- **Timeline**: view; native, optional; `visualized_by`.
- **Confluence page or Jira Docs content**: document; external, optional;
  `documented_by`.
- **External Pull Request or Merge Request**: review_artifact; external,
  optional; `implemented_by`. Name it after its host.

Jira has no universal native Milestone object. Translate by intent and say
which you picked: shipping target to a Version; fixed work period to a Sprint;
portfolio checkpoint to a configured Work Type or custom field; date checkpoint
to the due date or a custom date field; phase inside an Epic to a child work
item, component, or custom field.

## References and autolinks

What the Cloud editor auto-detects in a description or comment: a typed work
item key becomes a hyperlink to that work item, the behavior Atlassian's
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

Applied: `ref_form.py jira` prints the form (a bare key on the same site, where the
renderer links it and nothing lands on the target; a titled link for an object without a
key, another site, or another tracker). For a visible reciprocal relationship
do not lean on prose: create a Linked work item of the right type, the one
in-tracker mechanism that shows on both objects by design.

## Reading and writing

Atlassian CLI: after `acli jira auth login`, the `acli jira workitem` group
covers create, edit, comment, link, search, and transition, with the body
supplied through `--description`, `--description-file`, `--from-file`,
`--from-json`, or `--editor`, in plain text or ADF ([acli jira workitem create](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-create/)).

A description is plain text or ADF ([ADF](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)),
never markdown, and the editor's autoformatting does not apply to API input.

Write format. The Jira description field takes plain text or ADF, never
markdown, so a markdown body is converted before any write. Run
`jira_text.py` (in the plugin's `scripts/`) on the saved body: it drops
heading, bold, and code markers, indents fenced blocks four spaces, turns
`[text](url)` into `text (url)`, keeps `- ` and `1. ` lists, and unfolds a
`<details>` block under its summary line. It exits 1 and prints the reason
when the body holds an image, a table, or a nested list that plain text would drop or
flatten;
print the body for the user to paste and file nothing then. The converted
text is what the preview shows and what `--description-file` receives. acli
accepts ADF, but no documented flag converts markdown to it, so this skill
writes plain text.

### Commands

Create ([acli jira workitem create](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-create/)):

```console
$ acli jira workitem create \
    --project "<KEY>" \
    --type "<Work Type>" \
    --summary "<title>" \
    --description-file "<scratch path>"
```

Update ([acli jira workitem edit](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-edit/)),
where `--yes` skips the confirmation prompt:

```console
$ acli jira workitem edit \
    --key "<KEY>" \
    --summary "<title>" \
    --description-file "<scratch path>" \
    --yes
```

Read the body and its comments, saving the output for the checks:

```console
$ acli jira workitem view <KEY> --json --fields summary,description,comment,issuetype,parent,subtasks,issuelinks > "<scratch dir>/first.json"
```

`--fields` takes a comma-separated list and `--json` is documented. The shape of acli's
JSON is not documented, so find the body's key path in the output; the REST v3 issue
puts it at `fields/description`.

Check each capability you use, and only those. Create:

```console
$ acli jira workitem create --help | grep -e '--description-file'
```

Edit:

```console
$ acli jira workitem edit --help | grep -e '--description-file'
```

Read back:

```console
$ acli jira workitem view --help | grep -e '--json'
```

When a check fails, treat that capability as absent and print the body to paste.

## Duplicate search

Search every status; a JQL query with no `status` clause includes closed
work items.

```console
$ acli jira workitem search --jql "project = <KEY> AND text ~ \"<keywords>\""
```

## Naming traps

Never say Project for a Jira Space in prose; keep it for the API field and for
the Atlassian Project reporting object. Never say Space when you mean a
Confluence Space. Never say Issue Type where the instance says Work Type. Never
say Initiative unless you have read that level in the configuration. Never call
a Jira Task a subtask, and never map it onto a GitLab Task or an Azure DevOps
Task. Never say Milestone: name the Version, Sprint, date, or field you
actually mean. Never call a Sprint, Version, Board, or Plan a parent. Never
write `#123`, and never invent a sigil for anything Jira does not key.
