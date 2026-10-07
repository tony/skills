# The situation sweep

Shared by `/situate` and the `situational-awareness` skill; they report in the shape in `report-shape.md`.

Six layers, gathered in order. Each degrades on its own: a repo with no
remote still has commits, a branch with no pull request still has a
diff.

Never blur two findings: nothing found is "none" (`none is open`,
`none is referenced`); a lookup that could not run is `unavailable`
with the reason. A repository with no remote has no pull request to
check, so write `no remote, so no pull request is open or checkable`.
Say where a "none" was looked: `none is referenced in commits, the
branch name, or a pull request body`.

Never print an absolute path, a temp directory, or a host-sandbox
detail; say "the home directory" or "the project root" instead.

Script paths here (`../scripts/...`) resolve from this file's directory; print the absolute path once and write it literally in each command.

## Contents

- Read-only contract
- 1. Position
- 2. Change
- 3. Pull request
- Pull request as the subject
- 4. Tickets
- 5. Conventions
- 6. Prior conversations
- Evidence discipline

## Read-only contract

The one contract for every situate skill. Reading files, git history,
and `gh` views is allowed. Never commit, push, edit files, stash, switch
branches, or run `git fetch`: it rewrites remote-tracking refs, which
changes what every other command sees. Work from the refs already in the
repository; the position script reports the trunk ref's age as
`trunk_age`. If it is old, say the comparison against trunk may be stale
and let the user decide whether to fetch.

## 1. Position

Run the position script. It only reads git, never fetches, and prints
JSON with no paths; the path resolves from the skill directory like the
other bundled files:

```console
$ python3 references/position.py
```

Add `--trunk origin/<baseRefName>` when a pull request is the subject.
A non-zero exit means the directory is not a git repository: say so and
ask which directory holds the project.

Read its fields:

- `dotfile_repo` true (the root is the home directory or contains it) or
  `has_commits` false: report that in the hero line, name no untracked
  files, and stop with one result sentence, then ask which directory
  holds the project. The script prints nothing else in these cases.
- `trunk`, `trunk_source`, `trunk_age`: the remote's own HEAD, else
  `origin/main` or `origin/master`. When `trunk_source` starts with
  "assumed", say which was assumed. A null `trunk` means no trunk ref.
- `ahead`, `behind`, `branch` (null is a detached HEAD), `staged`,
  `modified`, `untracked`, `stashes`: work in flight that no commit
  records is what a new session cannot see. `untracked` already omits
  editor and shell files; `ignored_untracked` only counts them, so
  never list them.
- `on_trunk` true with nothing ahead: there is no branch story to tell;
  report recent trunk activity and the open pull requests instead, and
  say so.

## 2. Change

The script's `base` is where this branch diverged from what it will
merge into. `base_source` says which it is: `trunk` in the ordinary
case, `upstream` only for a stacked branch whose upstream is a
*different* branch (the branch's own `origin/<branch>` is ignored: its
merge-base is the last pushed commit and would hide what is already on
the remote).

A null `base` means the layer is unavailable: say which lookups
`failed` lists, and never substitute `HEAD` and log an empty range,
which reports a branch with commits as having none.

With `base` in hand:

```console
$ git log --no-merges --format='%h %s' <base>..HEAD
```

Read the diff, not just the stat: report what behavior changed, what the
commits were building toward, and whether the sequence is coherent or
abandoned an approach partway. Group by area rather than listing paths.
Note the history's shape: fixups pending autosquash, a revert, a merge
from trunk mid-branch.

## 3. Pull request

```console
$ gh pr view --json number,title,state,isDraft,url,headRefName,headRefOid,baseRefName,body,statusCheckRollup,reviewDecision
```

No pull request means the work has not been proposed yet. With no remote,
none can exist or be checked.

`gh pr view` cannot return review threads. Read them with one GraphQL
call, taking `<number>` from the output above (`-F` sends it as an
integer and fills `{owner}` and `{repo}` from the repository):

```console
$ gh api graphql -F owner='{owner}' -F repo='{repo}' -F number=<number> -f query='query($owner: String!, $repo: String!, $number: Int!) { repository(owner: $owner, name: $repo) { pullRequest(number: $number) { reviewThreads(first: 100) { nodes { isResolved isOutdated path comments(first: 1) { nodes { author { login } body } } } } } } }'
```

Keep the nodes where `isResolved` is false. A repository with more
than 100 threads needs `--paginate` and an `after` cursor; say the
list is partial instead.

Report failing checks by job name, and unresolved review threads by
what they ask for. A green rollup on a run from before the last push is
not a passing branch. Compare `headRefOid` with the local `HEAD`, and
list the runs on that commit:

```console
$ gh run list --commit <headRefOid> --json name,status,conclusion
```

No run on that commit means the checks have not run against it. Review
comments are the highest-value layer: another person's opinion, and what
a resumed session most often forgot.

## Pull request as the subject

A positional pull request number or URL replaces layers 1-2's local
`HEAD` with the pull request's head. Never check it out. Add `<n>` after
`gh pr view` in layer 3, and read the change and base from the pull
request:

```console
$ gh pr view <n> --json commits,headRefName,baseRefName
```

```console
$ gh pr diff <n> --name-only
```

Read the diff of the files that matter with `gh pr diff <n>`; a pull
request touching many files gets its names first and the diff by area.

The base is `origin/<baseRefName>`. Local ahead/behind, uncommitted work,
and stashes describe a different branch, so report them as not applying
unless the current branch is the pull request's head; then run the
position script with `--trunk origin/<baseRefName>`.

## 4. Tickets

Extract IDs from three places only: commit subjects and bodies on this
branch, the branch name, and the pull request body. Code comments and
documentation are out of scope.

Recognize `#123`, `owner/repo#123`, `Fixes`/`Closes`/`Refs` trailers,
Linear-style keys (`ENG-123`), and full issue URLs.

Resolve GitHub issues:

```console
$ gh issue view <n> --repo <owner/repo> --json number,title,state,labels,body,url
```

Omit `--repo` for a bare `#123`, which belongs to the current repository.

Resolve Linear and other trackers through whatever MCP server the
session has connected. When none is available, report the ID unresolved,
never a guess at what it means. Never invent a link: an ID that appears
nowhere in the evidence does not go in the report.

## 5. Conventions

Read `AGENTS.md`, `CLAUDE.md`, and any nested equivalents that cover the
directories the branch touched; nested files override the root for their
subtree.

Report only the rules that bear on the current change: the commit
message format, the quality gates that must pass before a commit,
constraints on the files being edited, and the lint, format, type-check,
and test commands those files or the project's manifest name.

## 6. Prior conversations

Opt-in only, through `--with-agentgrep` or an explicit request.

## Evidence discipline

"Three commits refactor the parser" is read. "This branch is close to
done" is inferred: mark it or leave it out.

Report absence explicitly; a section that silently disappears is
indistinguishable from one never checked.

Orient, do not fix. Failing checks, unresolved threads, and dirty files
get surfaced, not repaired, and the sweep proposes no plan for them
beyond the closing panel.
