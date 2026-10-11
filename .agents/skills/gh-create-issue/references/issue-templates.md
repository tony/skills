# Issue templates and forms

Read this when Phase 3 of `create-issue` finds templates or gets a 404.
Halt shapes are in "Replies" there.

## Find them

A 404 on the directory listing means no file there: use the
`issueTemplates` names from the Phase 2 query (legacy locations such as a
root `ISSUE_TEMPLATE.md`), then list the same path in `OWNER/.github`,
where an organization keeps its defaults.

`config.yml` holds `contactLinks` and the blank-issue setting, not a
template. Templates live on the default branch only ([GitHub's
template docs](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
say a template is available once merged there).

When `isBlankIssuesEnabled` is false and no template fits the report,
stop (Stops) rather than filing a blank issue.

## Choose one

With several, ask which fits. A numeric filename prefix is the
maintainer's ordering; otherwise file order is alphabetical, so never take
the first as the default. `pick` takes the listing on stdin and `defect`, `proposal`, or `task` as
the kind; exit 1 means none or several (see Stops):

```console
$ gh api repos/OWNER/REPO/contents/.github/ISSUE_TEMPLATE --jq '.[].name' \
    | python3 /absolute/path/to/scripts/issue.py pick KIND
```

## Fill it

`gh` rejects `--template` together with `--body-file` (observed:
`--template is not supported when using --body or --body-file`), so fill
the template by hand and pass the result as the body. The script parses a
`.yml` form or a markdown template's front matter and prints JSON; it
exits 2 with `unsupported:` on YAML it cannot read, then fill by reading
the file:

```console
$ gh api repos/OWNER/REPO/contents/.github/ISSUE_TEMPLATE/NAME \
    -H 'Accept: application/vnd.github.raw' \
    | python3 /absolute/path/to/scripts/issue.py template NAME
```

`body` is the skeleton in file order. `<ANSWER>` and `<CHOOSE>` mark
unanswered fields, and `fields` lists labels, types, required flags, and
dropdown options. Fill each field from the evidence and leave `<ANSWER>`
where there is none, so the placeholder gate blocks filing. Drop an
optional field you have nothing for. A `required` field is never emptied
or invented. Tick a checkbox only when this run did what it says. Keep the
template's structure.

## Front matter

Use `title` as the start of the title. Keep `labels` the repository has
(GitHub does not add a missing one; the filing step validates them).
Ignore `assignees`, `projects`, and `type`: setting them needs permissions
the reporter may lack, and assigning is the maintainers' triage.

## Primary sources

- [Syntax for issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms): top-level keys, labels, assignees
- [Syntax for GitHub's form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema): element types, `required`, `render`
- [Configuring issue templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository): `config.yml`, template ordering
- Observed `gh issue create` error: `--template` with `--body-file`
