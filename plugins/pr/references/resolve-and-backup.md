# Resolve the PR and back up its description

Shared by `/pr:refresh` and `/pr:rewrite`. Both edit an existing PR, so
both resolve it, diff against its real base, and back up the body first.

## Resolve the PR and its target

Use the PR number or URL in `$ARGUMENTS`; otherwise use the current
branch's PR (omit `<number>`):

```console
$ gh pr view <number> --json number,title,body,url,baseRefName,headRefName,state
```

When `gh` is missing, unauthenticated, or finds no PR, stop: say what
failed, name the fix (`gh auth login`, or the PR number to pass), and
change nothing.

Compare `headRefName` with `git branch --show-current`. On a mismatch,
or a detached HEAD, stop: the diff would describe another branch. Say
the PR's head branch is not checked out and name `headRefName`; change
nothing.

The diff base is `baseRefName`, so a stacked PR diffs against its parent
branch, never against trunk. Gather the net change:

```console
$ git fetch origin <baseRefName>
```

```console
$ git log origin/<baseRefName>..HEAD --oneline
```

```console
$ git diff origin/<baseRefName>...HEAD --stat
```

```console
$ git diff origin/<baseRefName>...HEAD
```

## Back up the current description

After the fetch and before drafting, save the body and title verbatim.
Shell state does not persist, so this runs as one script; it prints the
backup directory, and every later command uses that literal path. Take
`<number>` from the JSON above:

```bash
d="$(git rev-parse --git-path pr-backups)/$(date -u +%Y%m%d-%H%M%SZ)-pr<number>"
mkdir -p "$d"
gh pr view <number> --json body --jq .body >"$d/body.md"
gh pr view <number> --json title --jq .title >"$d/title.txt"
printf '%s\n' "$d"
```

Tell the user the printed path. To restore:
`gh pr edit <number> --body-file <backup>/body.md`.
