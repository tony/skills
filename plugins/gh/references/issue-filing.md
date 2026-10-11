# Filing

Read this only after the user approved filing (Phase 7 of
`create-issue`). Reply shapes are in "Replies" there.

Block on a leftover placeholder (an unresolved `<SHA>`, `<VERSION>`,
`<ANSWER>`, `CONTACT`). A row labeled `fenced` sits inside a code fence
and passes only when it is in output the user pasted (such as `<DEBUG>`):

```console
$ python3 /absolute/path/to/scripts/issue.py placeholders PATH
```

A block is a stop (Stops). Unfenced `<Foo>`-shaped text blocks by design;
backtick code to pass. The user may instead submit it themselves: add `--web` to `gh issue
create` so it opens the prefilled form. That route exists only after the
auth check passed, so an unverified draft never offers it.

An unknown label aborts the create and files nothing. Look up only the
wanted labels (`gh label list` pages, so a full listing truncates) and keep
the ones the repository has, once per label:

```console
$ gh label list \
    --repo OWNER/REPO \
    --search NAME \
    --limit 100 \
    --json name \
    | python3 /absolute/path/to/scripts/issue.py labels NAME
```

File from a file, never from an inline `--body`, so fences, HTML, and `$`
survive shell quoting. A bare `gh issue create` in a non-interactive shell
cannot prompt and files nothing, so always pass `--title` and
`--body-file`:

```console
$ gh issue create \
    --repo OWNER/REPO \
    --title "TITLE" \
    --body-file PATH \
    [--label NAME]
```

Remove the scratch file whichever branch ended the run (filed, printed,
dropped, or stopped):

```console
$ rm -f PATH
```

Read the created issue back, taking the URL from the create output. Exit
1 means the title differs:

```console
$ gh issue view URL \
    --repo OWNER/REPO \
    --json title \
    | python3 /absolute/path/to/scripts/issue.py readback "TITLE"
```

## Primary sources

- `gh issue create --help`: `--web` opens the browser to create the issue
  with the prefilled fields.
- [gh issue create manual](https://cli.github.com/manual/gh_issue_create)
