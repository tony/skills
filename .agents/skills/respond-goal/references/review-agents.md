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
gh pr list --state all --limit 20 --json reviews,comments --jq '[.[] | (.reviews[]?.author.login, .comments[]?.author.login)] | unique'
```

Logins ending in `[bot]`, plus the app accounts that do not use the
suffix, are the repository's automated reviewers. Note which ones post
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
gh api repos/{owner}/{repo}/pulls/<n>/reviews --jq '.[] | {login: .user.login, commit: .commit_id, at: .submitted_at}'
```

An agent has weighed in on the current head when a review of theirs
carries the head SHA. For agents that post plain issue comments and
never submit reviews, there is no SHA to match: compare the comment
timestamp against the moment the push landed, and treat anything older
as belonging to a previous round.

Never treat "no new comment yet" as approval. Absence during the wait
window is absence, and the report says which agent never arrived.

## Waiting

Two waits, in this order, both bounded.

**CI**, which has a completion signal and can be blocked on directly:

```console
gh pr checks --watch --fail-fast
```

**The agents**, which have none. Record the head SHA and the time
before pushing, then poll for new reviews and comments at a steady
interval. Stop early the moment every agent on the roster has weighed
in on the head SHA; otherwise stop at the cap.

The cap is not optional and it is not generous. Ten minutes and a
handful of polls covers the agents that were going to answer; past
that, the loop is holding a session open in the hope of an event that
has already failed to happen. Report who was still missing and move on
— an agent that arrives later is picked up by the next round, and the
loop can be re-entered at any time.

Poll politely. A tight loop against the API burns the rate limit that
the next round needs.

## Ordering

Wait for CI before screening the agents' comments. A red check is a
fact and usually explains anything the agents are about to say about
the same code; screening prose against a build that is already known to
be broken produces findings that evaporate when the build is fixed.
