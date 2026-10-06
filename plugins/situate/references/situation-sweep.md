# The situation sweep

Shared by `/situate` and the `situational-awareness` skill.

Six layers, gathered in order. Each one degrades on its own — a repo
with no remote still has commits, a branch with no pull request still
has a diff. A layer that cannot be gathered is reported as unavailable,
never dropped.

Two different findings, never blurred: nothing found is stated as
"none" (`none is open`, `none is referenced`); a lookup that could not
run is stated as `unavailable` with the reason. A repository with no
remote has no pull request to check, so write `no remote, so no pull
request is open or checkable`.

## Contents

- Read-only contract
- 1. Position
- 2. Change
- 3. Pull request
- 4. Tickets
- 5. Conventions
- 6. Prior conversations
- Report shape
- Evidence discipline

## Read-only contract

This is the one contract for every situate skill and command. Reading
files, git history, and `gh` views is allowed. Never commit, push, edit
files, stash, switch branches, or run `git fetch`.

`git fetch` rewrites remote-tracking refs, which changes what every
other command in the session sees: a mutation dressed as a read. Work
from the refs already in the repository and say how old they are:

```console
$ git log -1 --format='%cr' "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)" 2>/dev/null || echo "(unknown)"
```

If that date is old, the comparison against trunk may be stale. Say so
and let the user decide whether to fetch.

## 1. Position

Where the working tree sits relative to trunk.

Resolve trunk from the remote's own HEAD rather than assuming `main`:

```console
$ git symbolic-ref --short refs/remotes/origin/HEAD
```

When that ref is absent — a fresh clone, a repo cloned with
`--single-branch` — fall back to whichever of `origin/main` or
`origin/master` exists, and say which was assumed.

Then the merge-base, the ahead/behind counts, the uncommitted state,
and any stashes. A dirty tree is part of the situation: work in flight
that no commit records yet is exactly what a new session cannot see.

Detect the degenerate case early. On trunk itself with nothing ahead,
there is no branch story to tell — report recent trunk activity and the
open pull requests instead, and say that is what happened.

## 2. Change

What the branch does, not which files it touched.

Resolve the base commit before logging anything. The base is where this
branch diverged from what it will merge into.

Trunk is that base in the ordinary case. An upstream is a better base
only when it names a *different* branch — a stacked branch whose
upstream is its parent. Check which one it is:

```console
$ git rev-parse --abbrev-ref '@{upstream}'
```

When that comes back as the branch's own remote counterpart —
`origin/<branch>`, what `git push -u` sets — ignore it. Its merge-base
is the last pushed commit rather than the divergence point: a fully
pushed branch resolves a base equal to `HEAD`, and a branch carrying
unpushed work narrows the range to only those commits, hiding
everything already on the remote.

For a stacked branch, take the parent:

```console
$ git merge-base HEAD '@{upstream}' 2>/dev/null
```

Otherwise, and whenever that lookup fails or returns `HEAD`, take
trunk. Shell state does not persist between Bash calls, so substitute
the trunk name found in the Position layer (for example `origin/main`)
for `<trunk>`:

```console
$ git merge-base HEAD <trunk> 2>/dev/null
```

Guard both lookups. Both fail in practice — a branch pushed with no
upstream set, and a clone whose `refs/remotes/origin/HEAD` was never
populated — and an unguarded `origin/HEAD` fails hard rather than
falling through.

When neither resolves there is no base to compare against. Report the
layer unavailable and say which lookups failed. Do not substitute
`HEAD` and log an empty range: that reports a branch with commits as
having none, which is worse than reporting nothing at all.

With the base commit printed by that command in hand:

```console
$ git log --no-merges --format='%h %s' <base>..HEAD
```

Read the diff, not just the stat. A file list is an inventory; the
reader wants the intent — what behavior changed, what the commits were
building toward, and whether the sequence tells a coherent story or
shows an approach that was abandoned partway.

Group by area rather than listing every path. Twelve files under one
directory is one fact, not twelve.

Note the shape of the history too: fixup commits pending autosquash, a
revert, a merge from trunk mid-branch. Each says something about where
the work stands.

## 3. Pull request

```console
$ gh pr view --json number,title,state,isDraft,url,headRefName,body,statusCheckRollup,reviewDecision
```

No pull request for the branch is a finding, not an error — it means
the work has not been proposed yet. With no remote, no pull request can
exist or be checked.

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
not a passing branch; check that the run covers the current head.

Review comments are the highest-value layer here. They are the only
part of the situation containing another person's opinion, and they are
what a resumed session most often has no memory of.

## 4. Tickets

Extract IDs from three places only: commit subjects and bodies on this
branch, the branch name, and the pull request body. Code comments and
documentation are out of scope — a `TODO(#42)` in a file the branch
never touched is not this branch's ticket.

Recognize `#123`, `owner/repo#123`, `Fixes`/`Closes`/`Refs` trailers,
Linear-style keys (`ENG-123`), and full issue URLs.

Resolve GitHub issues:

```console
$ gh issue view <n> --repo <owner/repo> --json number,title,state,labels,body,url
```

Omit `--repo` for a bare `#123`, which belongs to the current repository.

Resolve Linear and other trackers through whatever MCP server the
session has connected. When no such server is available, report the ID
unresolved. An unresolved reference is information; a guess at what it
means is not.

Never invent a link. An ID that appears nowhere in the evidence does
not go in the report.

## 5. Conventions

What this project requires of the work in flight. Read `AGENTS.md`,
`CLAUDE.md`, and any nested equivalents that cover the directories the
branch touched — nested files override the root for their subtree.

Report only the rules that bear on the current change: the commit
message format, the quality gates that must pass before a commit,
constraints on the specific files being edited. A branch touching one
plugin does not need the whole document restated.

Note the toolchain the gates actually run through, discovered from the
repo rather than assumed — the lint, format, type-check, and test
commands named in those files or in the project's manifest.

## 6. Prior conversations

Opt-in only, through `--with-agentgrep` or an explicit request.

## Report shape

One hero line, then these sections in this order, then a next-step
panel. No other headings, no bold label on every bullet, no recap ending.

The hero is `✓ <branch>: <what it does> · <n> commits · PR #<n> <state>`,
or `⚠ <what is blocking or unclear>`. A run that stops early gets one
result sentence, then what the user needs to do.

1. `## Position` — branch, trunk, ahead/behind, uncommitted work,
   stashes, and how stale the trunk ref is.
2. `## Change` — what the branch does and how far along it is, grouped
   by area, with the commit sequence's shape.
3. `## Pull request` — state, checks by job name, unresolved review
   threads and what they ask for; or `none is open`.
4. `## Tickets` — each linked issue with its state and what it asks
   for; or `none is referenced`.
5. `## Conventions` — the rules that bear on this change and the gates
   it must pass.
6. `## Prior work` — only when the prior-conversations layer ran: what
   was decided earlier, when, and whether the repository agrees.
7. `## Open questions` — what is unresolved, mid-flight, or
   contradictory, and what a resumed session would most likely get
   wrong. Anything decided in an earlier conversation and still open
   belongs here, with its date.

Mark an inference with one hedging word ("probably", "appears"); an
unmarked statement was read. Do not state a blocker unless something is
actually blocked: an undecided question that blocks nothing is not one.

The panel is an `AskUserQuestion` offering next steps (continue the
work, address the review threads, open a pull request, widen the sweep
to prior conversations). Skip it in plan mode. When the tool is absent,
end with numbered options instead.

## Evidence discipline

Distinguish what was read from what was inferred. "Three commits
refactor the parser" is read. "This branch is close to done" is
inferred, and must be marked as such or left out.

Report absence explicitly. A section that silently disappears because
nothing was found is indistinguishable from a section that was never
checked, and the reader has no way to tell which.

Orient, do not fix. Failing checks, unresolved threads, and dirty files
get surfaced, not repaired, and the sweep proposes no plan for them
beyond the closing next-step panel.
