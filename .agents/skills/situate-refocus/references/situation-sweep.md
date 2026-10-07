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
repository and say how old they are:

```console
$ git log -1 --format='%cr' "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)" 2>/dev/null || echo "(unknown)"
```

If that date is old, say the comparison against trunk may be stale and
let the user decide whether to fetch.

## 1. Position

Check the repository root first:

```console
$ git rev-parse --show-toplevel
```

A root equal to `$HOME`, or one that contains it, means a dotfile
repository, not the project. Report that in the hero line, name no
untracked files, and stop: one result sentence, then ask which directory
holds the project. The same stop applies when `HEAD` has no commits.

Resolve trunk from the remote's own HEAD rather than assuming `main`:

```console
$ git symbolic-ref --short refs/remotes/origin/HEAD
```

When that ref is absent (a fresh clone, `--single-branch`), fall back to
whichever of `origin/main` or `origin/master` exists, and say which was
assumed.

Then the merge-base, the ahead/behind counts, the uncommitted state,
and any stashes: work in flight that no commit records is what a new
session cannot see.

On trunk itself with nothing ahead, there is no branch story to tell;
report recent trunk activity and the open pull requests instead, and say
so.

## 2. Change

Resolve the base commit, where this branch diverged from what it will
merge into, before logging anything. Trunk is the base in the ordinary
case; an upstream is better only when it names a *different* branch, a
stacked branch whose upstream is its parent. Check which:

```console
$ git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null
```

When that is the branch's own remote counterpart (`origin/<branch>`, what
`git push -u` sets), ignore it: its merge-base is the last pushed commit,
so the range would hide everything already on the remote.

For a stacked branch, take the parent:

```console
$ git merge-base HEAD '@{upstream}' 2>/dev/null
```

Otherwise, and whenever that lookup fails or returns `HEAD`, take
trunk. Shell state does not persist between Bash calls, so substitute
the trunk name from the Position layer for `<trunk>`:

```console
$ git merge-base HEAD <trunk> 2>/dev/null
```

Guard both lookups: a branch pushed with no upstream, or a clone whose
`refs/remotes/origin/HEAD` was never populated, fails hard otherwise.
When neither resolves, report the layer unavailable and say which lookups
failed; never substitute `HEAD` and log an empty range, which reports a
branch with commits as having none.

With the base commit printed by that command in hand:

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
$ gh pr diff <n>
```

The base is `origin/<baseRefName>`; local ahead/behind, uncommitted work,
and stashes describe a different branch, so report them as not applying
unless the current branch is the pull request's head.

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
