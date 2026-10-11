# GitHub

Contents: Scope; Native hierarchy; Semantic roles; Orthogonal objects; References and autolinks; Reading and writing; Duplicate search; Naming traps.

## Scope

Organization or personal account > Repository. Every Issue is created in a
Repository and numbered uniquely within it. A GitHub Project is owned by the
account, not the Repository, so it sits beside this chain, not inside it.

## Native hierarchy

Issue > sub-issue > nested sub-issue, recursively. Every level is an Issue with
its own number, type, labels and milestone; "sub-issue" is a relation, not a
different object type. GitHub states the ceiling: "You can add up to 100
sub-issues per parent issue and create up to eight levels of nested sub-issues"
([sub-issues][sub]). That flow can attach an existing Issue from another repo.

Issue type (Task, Bug, Feature, or an organization-defined type) classifies an
Issue and establishes no hierarchy level. Types live in Organization settings,
default to task, bug and feature, and cap at 25 per organization
([issue types][types]), so the docs describe none for personal-account repositories.

GitHub has no native Initiative or Epic level. Express one as a parent Issue
with sub-issues, a custom issue type, a label, a Project field or a tracking
Issue, and say in the reply that the Epic role rests on convention. A custom issue type named Epic is still an Issue.

## Semantic roles

- Organization or personal account, then Repository (scope_container): native,
  required; an Issue is `contained_by` exactly one Repository.
- Issue (work_item): native, required.
- Sub-issue (sub_item): native, optional; `child_of` a parent Issue, which is
  `parent_of` it. The only native `parent_of` GitHub has.
- Issue type (no canonical role): native, configured in organization
  settings, optional. A classification facet, not a level.
- Epic or Initiative (delivery_group or strategic_goal): convention, optional.
- Objective or key result (strategic_goal, strategic_measure): absent; a
  Project number field or tracking Issue is the nearest convention.

## Orthogonal objects

- GitHub Project (view): native, owned by an organization or a personal
  account, optional; items are `grouped_by` it. It collects and presents
  work, and parents none of it. Spans repositories, holds draft issues,
  caps at 50 fields ([projects][proj], [creating a project][mkproj]).
- Project view, table, board or roadmap (view): native, optional; the Project
  is `visualized_by` them. A board is a layout, not an object.
- Project iteration field (timebox): native, optional; items `scheduled_in` it.
- Milestone (release_group): native, optional, repository-scoped, groups both
  Issues and pull requests, has a due date; items are `released_in` it.
- Release and its tag (checkpoint): native, optional, `checkpoint_of` a
  Repository; no native binding from an Issue to a Release.
- Wiki page, README or repository file (document): wiki is configurable per
  repository, files are convention; work is `documented_by` them.
- Pull request (review_artifact): native, optional; an Issue may be
  `implemented_by` one, and a pull request may have no linked Issue.

Closing keywords create that `implemented_by` link: `close`, `closes`,
`closed`, `fix`, `fixes`, `fixed`, `resolve`, `resolves`, `resolved` (as
`Closes #10` in-repo or `Fixes owner/repo#100` cross-repo) interpreted only
when the pull request targets the default branch ([linking a PR][link]).
Without one there is no link; never fabricate it.

## References and autolinks

Auto-detected in Issue and pull request bodies and comments, so left bare: a
plain URL; `#26`; `GH-26`; `owner/repo#26`; a full 40-character commit SHA;
`user@SHA`; `owner/repo@SHA`; a same-repository label URL, which renders as the
label chip. Autolinks are absent in wikis and repository files, so a reference
that renders in an Issue will not render in a README ([autolinks][auto]).

Backreference axis, verified: "By default, references generate a backlink. For
example, manually linking to an issue in a pull request will automatically
generate another link from the issue back to the pull request." The suppressor
is the host, not the link form: "you can use `redirect.github.com` instead of
`github.com` when constructing the URL in your reference." Hover cards then stop
appearing, and the technique is unsupported on GitHub Enterprise Cloud with data
residency (`ghe.com`) ([avoiding backlinks][back]).

So wrapping a `github.com` URL in `[text](url)` does not suppress the
cross-reference (that titled link is exactly the "manually linking" case the
docs say generates one) and a bare `#N` has no URL to rewrite at all. Use a
titled link for disambiguation, `redirect.github.com` to avoid the event.

House forms:
- Same repository, commit reachable from trunk: bare 7-character ref, no link.
- Issue or pull request: `ref_form.py github` prints the form for the intent (it
  applies the two rules above: bare `#N` in the same repository, a titled link
  elsewhere, and the `redirect.github.com` host to stay off the timeline).
- Same repository, Dependabot alert: `[dependabot#{repo}#{n}](URL)`. Alerts are
  numbered in their own per-repository namespace under `/security/dependabot/`,
  confirmed by `GET /repos/{owner}/{repo}/dependabot/alerts/{alert_number}`
  ([Dependabot alerts API][dep]), so `#5` never means alert 5.
- Cross-repository commit: `owner/repo@SHA`, or `user@SHA` when the repository
  name is the same under a different owner.

Custom autolinks are repository configuration: an admin maps a prefix to a URL
containing `<num>`, numeric or alphanumeric, and prefixes may not overlap, so
`TICKET` and `TICK` cannot coexist ([custom autolinks][custom]). Emit `JIRA-123`
only after confirming that repository configures that prefix; an unconfigured
prefix renders as literal text and the reference dies silently.

`@username` and `@org/team-name` are side effects, not formatting: they
subscribe the person or team and notify them, switchable per team by maintainers
([team notifications][team]).

## Reading and writing

`gh issue create` takes the body from a file with `--body-file`, and `--type` and
`--parent` when the user names them
([gh issue create](https://cli.github.com/manual/gh_issue_create)), so a
drafted body goes in from a file undamaged by shell quoting. The scratch path
comes from the skill's filing step. `--type` takes an issue type the owner
defines; add it only when the
user names one.

```console
$ gh issue create --title "..." --body-file "<scratch path>"
```

`gh issue edit` rewrites a body, and `--parent` on create, or `--parent` and
`--add-sub-issue` on edit, set sub-issue relations ([gh issue edit][edit], and its
`--help`). Preview the render first: autolinks, label chips and cross-references only
appear then.

Check each capability you use, and only those. Create (add the `--type` and
`--parent` lines only when the user names a type or a parent):

```console
$ gh issue create --help | grep -e '--body-file'
```

```console
$ gh issue create --help | grep -e '--type'
```

```console
$ gh issue create --help | grep -e '--parent'
```

Edit:

```console
$ gh issue edit --help | grep -e '--body-file'
```

Read back:

```console
$ gh issue view --help | grep -e '--json'
```

### Read recipe

Read with comments, saving the output for the checks (body field path `body`):

```console
$ gh issue view <number> --json number,title,body,url,state,labels,milestone,issueType,parent,subIssues,comments > "<scratch dir>/first.json"
```

`gh issue view --json` with no value prints its field list; `issueType`, `parent` and
`subIssues` were in it when this was written, so drop any the installed version
lacks. The role and the children come from `issueType`, `parent` and `subIssues`. Rewrite a body with
`gh issue edit <number> --body-file "<scratch path>"` ([gh issue edit][edit]).

## Duplicate search

Search open and closed items together; `gh issue list` hides closed ones by
default and fetches 30 unless `--limit` says otherwise (`gh issue list --help`).

```console
$ gh issue list --state all --limit 100 --search "<keywords>"
```

## Naming traps

Never say Epic or Initiative as though it were native. Never say bare
"Project": write GitHub Project (view), account-owned and not a Repository.
It is not a Linear Project and
does not parent its items. Never say "board" as
an object; it is a Project view layout. Never call a Milestone a parent or an
epic, and never say "sprint"; the native noun is a Project iteration field
value. Never say "ticket", "story" or "story points"; the noun is Issue, and
points exist only where a Project number field defines them. Never write "Task"
to mean a hierarchy level; Task is a default issue type. Never call a sub-issue
a different object class from an Issue, call a pull request an Issue, or assert
a link the pull request does not declare.

[auto]: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls
[back]: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls#avoiding-backlinks-to-linked-references
[custom]: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/configuring-autolinks-to-reference-external-resources
[dep]: https://docs.github.com/en/rest/dependabot/alerts
[link]: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
[mcp]: https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/set-up-the-github-mcp-server
[proj]: https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects
[sub]: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues
[subapi]: https://docs.github.com/en/rest/issues/sub-issues
[team]: https://docs.github.com/en/organizations/organizing-members-into-teams/configuring-team-notifications
[types]: https://docs.github.com/en/issues/tracking-your-work-with-issues/configuring-issues/managing-issue-types-in-an-organization
[mkproj]: https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/creating-a-project
[mcprepo]: https://github.com/github/github-mcp-server
[edit]: https://cli.github.com/manual/gh_issue_edit
