---
name: check
description: "Use when asked to address review feedback, reply to review comments, or screen bot findings: decide fix, defer, or decline; draft replies."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[findings text] [<pr-number|url>] [--base=<ref>] [--include-resolved]"
user-invocable: true
---


# `/respond:check`

Screen review feedback and decide what deserves a fix: every claim, from
a colleague, a bot, or a review run earlier in this session, passes the
six gates in `../../references/screening-rubric.md` and leaves with a
verdict, its evidence, and a reply the reviewer can argue with.

This skill changes nothing: no edits, commits, posted comments, or
resolved threads. Acting on the ledger is `/respond:action`'s job.

Paths under `../../scripts/` resolve from this skill's directory: print the absolute path once and write it literally in each command, since shell variables do not persist between Bash calls.

## `$ARGUMENTS` contract

A leading pull request number or URL names the PR to collect from
(default: the current branch's PR when one exists); other non-flag text
is the findings list. With no arguments and no PR,
look for review output already in this session; if there is none, ask
for the feedback rather than inventing a review.

| Flag | Default | Effect |
|---|---|---|
| `--base=<ref>` | merge-base with `origin/<trunk>` | Override the provenance baseline (a stacked branch's parent, for instance). |
| `--include-resolved` | off | Screen resolved and outdated threads too, instead of treating them as already settled. |

## Phase 0: What this project has already decided

The alignment gate needs citations, so gather them before reading a
single finding: `AGENTS.md` / `CLAUDE.md` and any nested equivalents
covering the touched directories, `.github/CONTRIBUTING.md`, and the
branch's own stated purpose (pull request body, commit messages,
ticket). A project with nothing written down has no decisions to cite;
never substitute a preference for a citation.

Resolve the provenance base here too (see the rubric's Provenance
gate), and note the branch's push state with `git status -sb`. This
skill does not fetch, so `origin/<trunk>` is read as last fetched; say
in the report that provenance may be stale when the remote has moved.

## Phase 1: Collect

Gather from every channel `../../references/feedback-sources.md`
describes that applies to this run: pasted text, this session's earlier
review output, the pull request's three comment surfaces, and failing
CI.

Normalize, split, drop, and merge per that file, including its rule
for re-posts of findings declined earlier in this session.

## Phase 2: Screen

Run the six gates on every finding, in the rubric's order, stopping at
the first gate that settles it. Record each gate's evidence as you go; a
verdict with no evidence behind it is not a verdict, and the report must
not contain one.

- Read the code, do not trust the claim: automated reviewers may assert
  with full confidence and be wrong.
- One verdict per finding. "Fix if X" is not a verdict; when the code
  cannot be read, the verdict is `ask`.
- Decline on evidence only: a cited decision, a code path read, a
  trigger named. "That isn't long" is a preference, not evidence.
- Add no standards, library functions, or rationale you have not
  verified, per `../../references/prose-rules.md`.

Use `AskUserQuestion` for `ask` verdicts only: findings where the
truth depends on intent only the author has, where the alignment
citation is genuinely contested, or where the code is not available.
Everything else is decided here. In a non-interactive run, leave them
as `ask` in the ledger.

## Phase 3: Report — the output contract

Write the report and replies per `../../references/prose-rules.md`. Use
exactly the headings below, in this order, and no others. The hero line
is the first line of the reply; nothing precedes it, including a run
with no readable code. Never name local absolute paths or temp files.

1. Hero block (1–3 lines): `N to fix, M deferred, K declined`, then
   `, J ask` when any finding is an `ask`, plus the branch name and the
   feedback sources screened.
2. `## Ledger` — one entry per finding: id, source (author, and whether
   it is a bot), the claim quoted, location, the gate results with
   their evidence, and the verdict with its reason, as one inline-prose
   bullet (no labeled sub-bullets). Merged duplicates
   list all their sources on one entry. When the code is unreadable,
   every finding is an `ask` entry here, never under
   `## Deferred & declined`.
3. `## To fix` — omitted when nothing is accepted; else the accepted findings in the order they should land,
   each with the minimal fix and whether it wants a forward commit or a
   `fixup!`. Name a `fixup!` target only when the branch's log shows
   the causal commit; otherwise it is a forward commit.
4. `## Deferred & declined` — omitted when empty; else the follow-up
   recommendation or the drafted reply. A declined `improbable` reply states the trigger the
   scenario needs, so a reviewer who knows a caller that produces it
   can say so.
5. `## Ledger key` — branch, `HEAD` (7-character SHA, the only place a
   SHA appears), and the feedback digest, as the rubric's ledger section
   defines them. A second bullet says provenance may be stale when the
   remote has moved. `/respond:action` checks this key to know the
   screening still describes the current tree.
6. End with an `AskUserQuestion` panel: run `/respond:action` on the
   accepted findings, run it with `--reply` so the drafted replies get
   posted too (both omitted when `## To fix` is empty), re-screen with the
   deferred findings opted in, or stop.
   In a non-interactive run (CI, subagent), list the panel's options as
   plain numbered lines after `## Ledger key`, with no heading, and stop.
   Invoked by `/respond:goal`, skip the panel.

Compute the digest from the reviewers' original text, one
`<id>` TAB `<text>` line per comment, review body, or pasted block, as
the rubric's ledger section defines. `/respond:action` runs the same
commands, so the keys compare. For a pull request, one command covers
the three comment surfaces:

```bash
{
  gh api repos/{owner}/{repo}/pulls/<n>/reviews --paginate \
    --jq '.[] | [.id, .body] | @tsv'
  gh api repos/{owner}/{repo}/issues/<n>/comments --paginate \
    --jq '.[] | [.id, .body] | @tsv'
  gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate \
    --jq '.[] | [.id, .body] | @tsv'
} | python3 ../../scripts/ledger_key.py
```

For pasted text or a session's review output, give each whole block the
id `paste` or `session`; a quoted heredoc needs no escaping:

```bash
python3 ../../scripts/ledger_key.py <<'EOF'
paste	alex: parse_retry_after throws on a non-numeric header
session	lint-bot: session.token is read before the None check
EOF
```

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
2 to fix, 1 deferred, 1 declined on feat/retry-after. Screened 4 comments from the PR and 1 bot.

## Ledger

- #1 alex: "parse_retry_after throws on a non-numeric header". Location: parse_retry_after in client.py. Provenance in-branch (added in the branch's second commit); truth confirmed by reading the code. Verdict fix.
- #2 lint-bot and alex: "session.token is read before the None check". Location: refresh_session in auth.py. Provenance in-branch. Verdict fix.
- #3 style-bot: "split this 45-line function". Location: sync_all in sync.py. Provenance pre-existing at the base. Verdict defer.
- #4 alex: "wrap the cache read in a lock". Location: Cache.get in cache.py. Trigger: needs two writers on a single-threaded path; damage cosmetic. Verdict decline, improbable.

## To fix

- #1: fall back to the default delay when the header is not numeric; forward commit.
- #2: return early when `session` is None; fixup! of the commit that added refresh_session.

## Deferred & declined

- #3: open a follow-up to split sync_all; it predates this branch.
- #4: "This needs two concurrent writers, and Cache is only called from the main loop. If you know a caller that writes from another thread, say so and it comes back."

## Ledger key

- Branch feat/retry-after, HEAD 4f2a9c1, digest 9b3e07a1c4d2.
- Provenance may be stale: this skill did not fetch, so origin/main is as last fetched.

1. Run /respond:action on the accepted findings
2. Run it with --reply to post the drafted replies
3. Re-screen with the deferred findings included
4. Stop
```

A `## Deferred & declined` entry holds the follow-up or the drafted
reply and nothing else: no speculation about how the fix should look.

A stopped run (no findings to screen, no readable feedback) reports one
result sentence, then what the user needs to provide.

When the code is not readable, the reply is the hero line, `## Ledger`
with one `ask` entry per finding, and `## Ledger key`. Each entry says
what is missing in one line. Add no hypothetical, no "if X then fix"
branch, no claim about code you have not read, and no extra heading.
Reply in this shape, with the same plain bullets:

```text
0 to fix, 0 deferred, 0 declined, 4 ask on main. Screened 4 pasted comments; no code is available.

## Ledger

- #1 alex: "parse_retry_after throws on a non-numeric header". Verdict ask: code not available; need the file that defines parse_retry_after.
- #2 lint-bot and alex: "session.token is read before the None check". Verdict ask: code not available; need the function that reads session.token.
- #3 style-bot: "split this 45-line function". Verdict ask: code not available; need the function and the branch diff.
- #4 alex: "recieved should be received in the log message". Verdict ask: code not available; need the file with the log line.

## Ledger key

- Branch main, HEAD none, digest 1f12e2f93174.
- Provenance may be stale: no code or remote was available.

1. Run this from the pull request's checkout, or paste the code
2. Stop
```

If a fix seems obvious enough to just do, write it in `## To fix` and
hand off.
