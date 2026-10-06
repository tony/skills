# Feedback Sources

Where review feedback comes from, how each channel is read, and how the
same defect reported four times becomes one finding. Every channel
produces the same record shape, so screening never has to know which
reviewer it is arguing with.

## Channels

### Pasted text or a file

Non-flag `$ARGUMENTS`, or a path to a file holding the findings. The
lowest-ceremony channel and the one to fall back on when `gh` is
unavailable. Text with no structure is still parsed into findings — one
per assertion, not one per paragraph.

### This session

A review skill that already ran in the conversation is a source: the
host's own code-review command, `/codex:review`, the `weave-review` skill, a
security review, a subagent's report. Read its structured findings if
it emitted any; otherwise read its report as text.

This is the channel that makes screening cheap — the findings are
already in context, and the code they describe usually is too.

### The pull request

Three GitHub surfaces carry three different things, and reading only
one loses findings:

Reviews and their verdicts:

```console
gh pr view <n> --json number,title,headRefOid,reviewDecision,statusCheckRollup,reviews,comments
```

Inline review comments, which carry the file and the diff hunk:

```console
gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate
```

Thread state, which says what has already been settled:

```console
gh api graphql -F owner={owner} -F repo={repo} -F number=<n> -f query='query($owner: String!, $repo: String!, $number: Int!) { repository(owner: $owner, name: $repo) { pullRequest(number: $number) { reviewThreads(first: 100) { nodes { isResolved isOutdated path comments(first: 20) { nodes { author { login } body createdAt } } } } } } }'
```

Resolved and outdated threads are skipped by default — someone already
decided. `--include-resolved` reads them anyway, for the case where the
resolution is what is being questioned.

### Continuous integration

A failing check is feedback with no opinion in it. Pull the failure
itself rather than the summary:

```console
gh run view <run-id> --log-failed
```

A red check enters the ledger as a finding whose truth gate is already
settled by the log. It still passes provenance: a job that was red
before this branch existed is `pre-existing`, and the branch is not
where that gets fixed.

## Normalizing

Each finding becomes one record: source (author login, whether the
author is a bot, and the thread or run it came from), the claim quoted
and trimmed to its assertion, the location it names, and the severity
the reviewer gave it. Severity is recorded as given and re-derived by
the rubric — a bot's "critical" buys no priority.

Split a comment that makes several claims into several findings. A
reviewer who writes one paragraph about a null check and a naming
preference has made two claims with two different fates.

Drop what is not a claim: approvals, summaries, walkthroughs, "LGTM",
diagrams, and the coverage tables bots emit. A comment with no
assertion about the code produces no finding.

## Merging duplicates

The same defect from four reviewers is **one** record with four
sources. Merge on location plus claim shape, not on wording — bots
paraphrase each other constantly.

Merging is what keeps the loop from inflating: without it, a round with
three bots produces three commits for one fix, three replies, and a
ledger that looks three times as busy as the branch is.

Where merged sources disagree on severity, keep the highest as input
and let the rubric settle it.

## Re-posts across rounds

Automated reviewers re-post on every push. A finding that a previous
round declined stays declined unless the code at that location changed
since the decline — in which case it is genuinely new and screens
again.

Carry declines forward across rounds by location plus claim shape. A
loop that re-screens the same rejected finding every round never
terminates, and a reviewer who reads four identical replies learns
nothing from any of them: reply once, then let the ledger remember.

## Nitpicks and collapsed sections

Bots hide low-confidence findings in collapsed `<details>` blocks and
"nitpick" sections. Read them — they occasionally hold the only real
bug in the review — but they enter screening in the same rubric as
everything else, where a cosmetic remote-trigger nitpick that costs a
code path dies at the cost gate like any other.
