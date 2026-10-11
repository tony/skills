# GitLab

Contents: Scope; Native hierarchy; Semantic roles; Orthogonal objects; References and autolinks; Reading and writing; Duplicate search; Naming traps.

## Scope

Group > Subgroup > Project. A GitLab Project is a development container: one repository
plus its Issues, Merge Requests and CI/CD. It is not a delivery grouping and is nothing
like a Linear Project or a GitHub Project. Issues and Merge Requests are numbered per
Project; Epics and group-level work items are numbered per Group. Address a Project by
its slug: "All references to projects should use the **project slug** rather than the
project name" ([GLFM references][refs]).

## Native hierarchy

Epic > child Epic > Issue > Task. Every level is a work item; the relation, not the object
class, makes one a child of another. Parent relations are optional throughout: an Issue
with no Epic is a complete Issue. Epics are group-level only and tier-gated
([manage epics][epics]). Nesting is capped:
"Epics can contain multiple nested child epics, up to a total of 7 levels deep",
multi-level hierarchies are tier-gated, and an Issue "can
be set as a child item of at most one epic" ([child items][child]). Task is the sub-item
beneath an Issue. GitLab has no native level above Epic other than another Epic;
express an Initiative as a top-level Epic and say in the reply that the role rests on convention.

Type names are instance-dependent. Configurable work item types are tier-gated,
exist at the project level only, "their widgets and hierarchy restrictions match those of
issues", and cap at 40 per top-level group ([configurable types][conf]). An instance may
ship a type called Story or Bug that behaves exactly like an Issue. Resolve the list from
the instance.

The strategic family stays separate: Objective > child Objective, and Objective > Key
Result. OKRs are tier-gated and may sit behind a feature flag; check that the instance has them. Key results cannot have children, and "issues cannot be children of objectives or
key results" ([OKRs][okr]). An Objective states intent; an Epic coordinates delivery.
Never translate one into the other.

## Semantic roles

- Group and Subgroup (scope_container): native; a Group is required and owns Epics,
  Iterations and group Milestones. Project (scope_container): native, required for Issues
  and Merge Requests; an Issue is `contained_by` exactly one Project.
- Epic and child Epic (delivery_group): native_tier_gated, optional. An Epic is
  `parent_of` its Issues and an Issue is `child_of` at most one Epic; a child
  Epic is `child_of` its parent. This is decomposition, not membership;
  Milestone and Iteration are what an Issue is `grouped_by`.
- Issue (work_item): native, required. Task (sub_item): native, optional, `child_of` an
  Issue. Configurable work item type (work_item): configurable, optional.
- Objective (strategic_goal) and Key Result (strategic_measure): native_tier_gated and
  experimental, optional. An Objective is `measured_by` a Key Result.
- Weight: native_tier_gated ([weight][weight]). A field, not a level.

## Orthogonal objects

- Iteration (timebox): native_tier_gated. "Iterations are only available to groups"
  ([iterations][iter]). Work is `scheduled_in` one. An iteration cadence schedules
  iterations; it owns no work items.
- Milestone (release_group): native, project- or group-scoped. "Group milestones
  apply to any issue, epic, or merge request in that group's projects"
  ([milestones][mile]). Work is `released_in` one. Milestones and Iterations coexist on the
  same Issue and neither parents it.
- Release (checkpoint): native, tag-based, `checkpoint_of` a Project. Issue board and
  Roadmap (view): native, Roadmap tier-gated; work is `visualized_by` them, and a board
  column is a list, never a hierarchy level. Wiki (document): native, project- or
  group-scoped; work is `documented_by` a page.
- Merge Request (review_artifact): native. An Issue may be `implemented_by` one, and a
  Merge Request may exist with no Issue. Never fabricate the link.

A Merge Request declares `implemented_by` through the default closing pattern:
`Close`/`Closes`/…, `Fix`/`Fixes`/…, `Resolve`/`Resolves`/…, `Implement`/`Implements`/…
followed by `#123`, `group/project#123`, or a full Issue or work item URL. It fires only on
merge or push to the default branch, self-managed administrators can replace the pattern,
and `Related to #5` links without closing ([closing issues automatically][close]).

## References and autolinks

GitLab auto-detects a wide sigil set in descriptions and comments, so hand-linking any of
them fights the renderer. Leave bare: `#123` (Issue, or an Epic in group context),
`GL-123`, `[issue:123]`, `[work_item:123]`, `!123` (Merge Request), `&123` and
`[epic:123]`, `$123` (snippet), `~bug`, `~"feature request"`, `~"priority::high"`,
`%v1.23`, `%"release candidate"`, `9ba12248`, `9ba12248...b19a04f5`,
`*iteration:"iteration title"`, `[cadence:123]`, `[vulnerability:123]`,
`[feature_flag:123]`, `^alert#123`, `[contact:test@example.com]`, `[[Home]]` or
`[wiki_page:Home]`, `namespace/project>`, `@user_name`, `@group_name`, `@all` ([GLFM
references][refs]). Plain URLs to these objects are re-rendered in short form. None of it
works in Markdown snippet files.

Cross-container forms qualify the same sigils: `namespace/project#123`,
`namespace/project!123`, `namespace/project@9ba12248`, `group1/subgroup&123`,
`[work_item:namespace/project/123]`, `[wiki_page:namespace/project:Home]`,
`namespace/project^alert#123`. Inside the same namespace, drop the namespace:
`project#123`. For labels and milestones, prepend `/` before `namespace/project` to remove
ambiguity. Suffix `+` renders the title inline and `+s` adds assignees, milestone and
health status, on issues, tasks, objectives, key results, merge requests, epics, and on URL
references; they render live, so `#123+` cannot go stale.

Backreference axis, and GitLab inverts the GitHub rule here. Referencing an Issue, Merge
Request, Epic, work item, commit, snippet, wiki page, alert or design creates a
cross-reference on the target: "When mentioning issue `#111` in issue `#222`, issue `#111`
also displays a notification in its **Activity** feed", shown as `(Username) mentioned in
issue #(number)` ([crosslinking][cross]). A full URL creates the same event as the sigil.

An explicit titled markdown link does not suppress it: GitLab rewrites any anchor whose href matches a GitLab object URL into a reference and extracts cross-references from those anchors ([reference processing][proc]). There is no documented
GitLab equivalent of a no-backlink host. The only documented suppressor is escaping ("If
you don't want `#123` to link to an issue, add a leading backslash `\#123`") which also
kills the link.

Label, milestone, iteration, cadence, feature flag, contact and project references appear
to create no cross-reference event, because those objects are not mentionable; the docs do not say so, so preview
before posting.

`@user_name` and `@group_name` are side effects, not formatting: "GitLab notifies all
mentioned users with to-do items and emails", and the person becomes a participant
([mentions][ment]). Avoid `@all`.

House forms: bare short ref for a same-Project commit reachable from trunk, and
`namespace/project@9ba12248` for a cross-project commit. For an Issue or Merge Request,
`ref_form.py gitlab` prints the form for the intent: bare `#123` in-Project, the
`namespace/project#123` path elsewhere, and an escape or code span when the target's
timeline must stay untouched (the link is lost). Unlike GitHub, a titled link buys nothing
cross-container; it posts the same cross-reference.

## Reading and writing

`glab` is GitLab's CLI, authenticated with `glab auth login` ([GitLab CLI][cli]). It has
`issue`, `mr`, `work-items`, `milestone` and `api` command groups; there is no `epic`
group. `glab issue create` takes `-t/--title`, `-d/--description`, `--description-file`
(`-` reads standard input), `-l/--label`, `-m/--milestone`, `-a/--assignee`, `--epic`,
`-w/--weight`, `-c/--confidential`, `--linked-issues` and `--no-editor`
([glab issue create][create]). A drafted body goes in from a file, undamaged by shell
quoting. The scratch path comes from the skill's filing step; a flag the installed version
lacks fails the command, so report that and print the body instead.

```console
$ glab issue create --title "..." --description-file "<scratch path>" --yes
```

Epics and other configurable work items are not created by `glab issue create`;
the `work-items` command group is the route for them ([GitLab CLI][cli]). Preview the
rendered body before posting: sigils, label chips, `+` expansions and
cross-references only reveal themselves after render.

Check each capability you use, and only those. Create:

```console
$ glab issue create --help | grep -e '--description-file'
```

Update:

```console
$ glab issue update --help | grep -e '--description-file'
```

Read back:

```console
$ glab issue view --help | grep -e '--comments'
```

Epics and other work items:

```console
$ glab --help | grep -e work-items
```

### Read recipe

Read with comments, saving the output for the checks (body field path `description`):

```console
$ glab issue view <iid> --comments -F json > "<scratch dir>/first.json"
```

`-c/--comments` and `-F/--output json` are documented ([glab issue view][view]); the
JSON is the issue object of the [Issues API][restapi]. Rewrite a body with
`glab issue update <iid> --description-file "<scratch path>"` ([glab issue update][upd]).

## Duplicate search

Search open and closed items together; `glab issue list` hides closed ones by
default.

```console
$ glab issue list --all --search "<keywords>"
```

## Naming traps

Never write "Pull Request"; the noun is Merge Request and `!123` is its sigil. Never say
bare "Project" for a delivery grouping; the delivery_group is an Epic. Never say "repo" as the home of an Epic;
Epics live in a Group. Never treat Objective and Epic as interchangeable, and never promote
a Key Result into a parent. Never say "Sprint"; the noun is Iteration. Never say "Subtask"; the sub_item is a
Task. Never say "story points"; the field is weight. Never say "Backlog" as an object; it
is a board list. Never assume a work item type exists on the instance, and never invent a
sigil for one that has none.

[child]: https://docs.gitlab.com/user/work_items/child_items/
[cli]: https://docs.gitlab.com/cli/
[create]: https://docs.gitlab.com/cli/issue/create/
[close]: https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically
[conf]: https://docs.gitlab.com/user/work_items/configurable_work_item_types/
[cross]: https://docs.gitlab.com/user/project/issues/crosslinking_issues/#from-linked-issues
[epics]: https://docs.gitlab.com/user/group/epics/manage_epics/
[gql]: https://docs.gitlab.com/api/graphql/reference/#mutationworkitemcreate
[iter]: https://docs.gitlab.com/user/group/iterations/
[mcp]: https://docs.gitlab.com/user/model_context_protocol/mcp_server/
[ment]: https://docs.gitlab.com/user/discussions/#mentions
[mile]: https://docs.gitlab.com/user/project/milestones/#project-milestones-and-group-milestones
[okr]: https://docs.gitlab.com/user/okrs/
[proc]: https://docs.gitlab.com/development/gitlab_flavored_markdown/reference_processing/
[refs]: https://docs.gitlab.com/user/markdown/#gitlab-specific-references
[restapi]: https://docs.gitlab.com/api/issues/
[weight]: https://docs.gitlab.com/user/work_items/weight/
[view]: https://docs.gitlab.com/cli/issue/view/
[upd]: https://docs.gitlab.com/cli/issue/update/
