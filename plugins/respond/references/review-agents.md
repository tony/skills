# Automated Review Agents

A loop that pushes and immediately declares itself done has not run a
review loop — it has skipped the review. This is how to find out which
machines review this repository, how to tell when they have looked at
the current head, and how to wait for them without hanging.

## Detection

**Past behavior first.** What has actually commented on this
repository's pull requests beats any configuration file, because a
configured app that never fires is not a reviewer:

```console
$ gh pr list --state all --limit 20 --json reviews,comments --jq '[.[] | (.reviews[]?.author.login, .comments[]?.author.login)] | unique'
```

A login ending in `[bot]` is an automated reviewer. `gh` JSON often
drops that suffix, so also test each remaining login:

```console
$ gh api users/<login> --jq .type
```

`Bot` marks an app account; `User` is a person. Note which ones post
*reviews* and which post plain comments — that changes how their
arrival is detected below.

**Configuration second**, for agents installed but not yet seen: a
CodeRabbit config, a Cursor Bugbot instruction file, a Greptile or
Sourcery config, Copilot instructions, or a workflow under
`.github/workflows/` that runs a review action on `pull_request`.

**Required checks third.** A review agent that reports as a status
check appears in `gh pr checks`, and its verdict gates the merge
whether or not it writes prose.

Record the result as a short roster: who reviews, by which surface, and
whether their arrival is observable. An empty roster is a finding, not
an error — it means the loop waits on CI alone and finishes sooner.

## Knowing an agent has seen the current head

Reviews carry the commit they were submitted against, which is the
only reliable "has looked at this" signal:

```console
$ gh api repos/{owner}/{repo}/pulls/<n>/reviews --paginate --jq '.[] | {login: .user.login, commit: .commit_id, at: .submitted_at}'
```

An agent has weighed in on the current head when a review of theirs
carries the head SHA. For agents that post plain issue comments and
never submit reviews, there is no SHA to match: compare the comment
timestamp against the moment the push landed, and treat anything older
as belonging to a previous round.

Never treat "no new comment yet" as approval. Absence during the wait
window is absence, and the report says which agent never arrived.

## Waiting

Two waits, in this order, both bounded, both run by
the plugin's `wait_pr.py`, with the commands in `/respond:goal` steps 5
and 6.

**CI**, which has a completion signal but no cap of its own. Right
after a push `gh pr checks` can list nothing, which is not "none
pending"; the script waits for a first check, then for none pending,
and stops at the first failure or at the cap.

**The agents**, which have none. The script polls reviews and issue
comments and stops the moment every named login has weighed in on the
head SHA or commented since the push, or at the cap, and prints the
logins still missing. Roster logins match with or without `[bot]`.

The cap (`--wait` in `/respond:goal`) is not optional. Past it, the
loop is holding a session open in the hope of an event that
has already failed to happen. Report who was still missing and move on
— an agent that arrives later is picked up by the next round, and the
loop can be re-entered at any time.

## Ordering

Wait for CI before screening the agents' comments. A red check is a
fact and usually explains anything the agents are about to say about
the same code; screening prose against a build that is already known to
be broken produces findings that evaporate when the build is fixed.
