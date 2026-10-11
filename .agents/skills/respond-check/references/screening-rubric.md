# Screening Rubric

Contents: The gates, Verdicts, The ledger.

Every claim a reviewer makes, human or machine, passes six gates
before a single file is edited. this skill runs them and writes
the ledger; the `respond-action` skill reads that ledger and does not
re-litigate it. Every verdict carries evidence.

## The gates

Run them in order and stop at the first one that settles the finding.
A finding that clears all six is accepted for fixing.

### 1. Locate

Tie the claim to a specific place in the code: file and symbol, not a
line number that the next commit invalidates. A finding whose target
cannot be found is `unlocatable`: report it, ask the reviewer what they
meant, and never guess at a fix for it.

With no repository or no readable code (findings pasted into a bare
session), every gate past Locate fails for lack of evidence. Each
finding gets `ask` with the reason "code not available" and one line
naming what is missing, no fix shape, no `fixup!`, and no hypothetical
about what the code might do. Merging duplicates and dropping non-claims still apply.

### 2. Truth

Is the claim true of the code as written? Read the code and its
callers. Reviewers assert; the ledger records what you verified. Three
bots agreeing is one opinion; the code is the evidence.

A claim is `wrong` when the code already does the thing, when the path
the claim depends on is unreachable, when it rests on a misread of an
API's contract, or when it describes a version of the file that no
longer exists.

### 3. Provenance

```
NO FIX WITHOUT PROVENANCE
```

Write each `../scripts/` path in this file as an absolute path. Resolve
the base with the script, which prints JSON with `ref`, `sha` (the
merge-base with `HEAD`), `source`, and `fetched`:

```console
$ python3 ./repo_state.py base \
    --pr <n> \
    --base <ref>
```

It takes `--base` first; else the pull request's base branch from
`gh pr view --json baseRefName`, looked up on `upstream`, `origin`, other
remotes, then locally; else the remote's `HEAD`; else `main` or `master`.
the `respond-action` skill and the `respond-goal` skill add `--fetch`, which refreshes the
first remote before resolving. this skill does not fetch, so its
provenance may be stale, and the report says so. Exit 1 means nothing
resolved: ask for the base rather than guessing. Exit 4 means the named pull
request could not be read, so no base is assumed. Report `source` whenever it
is not `pr` or `flag`: the base was a guess.

Then test whether this branch introduced or last touched the flagged
code: `git diff <base>...HEAD -- <file>` for the region, and
`git log -L<range>:<file> <base>..HEAD` or blame when the diff is
ambiguous. Classify:

- `in-branch`: this branch added or changed it. Proceeds.
- `pre-existing`: present at the base. Deferred by default.
- `mixed`: the branch touched part of it. Split at that boundary: the
  branch's part proceeds, the remainder defers.
- `disputed`: settled at gate 2 already.

A reviewer flags; the branch owner scopes. Pre-existing findings get
their own branch and review.

### 4. Alignment

Correct is not the same as correct *for this project*. A finding is
`misaligned` when the change it asks for contradicts a decision the
project has already made: a rule in `AGENTS.md` / `CLAUDE.md` or a
nested equivalent, the purpose the branch states in its pull request or
commits, a design the surrounding code visibly and deliberately
encodes, or the convention every sibling module follows.

**A misaligned verdict must cite a written or demonstrated project
decision.** A preference invented while screening is not a decision;
without a citation the finding goes back to gate 5 on its merits. The
reply names the decision, so the reviewer can argue with it.

### 5. Odds

How often does the scenario fire? Classify the trigger it
needs and the damage it does; do not invent a probability.

Trigger:

- **Routine.** Reachable on a path users take, with ordinary inputs.
- **Occasional.** Needs an unusual but attainable combination: a rare
  flag, an empty collection, a slow network, a specific platform the
  project supports.
- **Remote.** Needs a combination nobody has produced: a race with a
  microsecond window on a single-threaded path, an input no caller can
  construct, a platform the project does not support.

Damage:

- **Severe.** Security, data loss, corruption, or a silently wrong
  result a user would act on.
- **Visible.** A crash, an error, a wrong render; the user notices and
  can report it.
- **Cosmetic.** Style, an internal log line, a message no user reads.

Severe damage clears this gate at any trigger. Otherwise routine and
occasional triggers clear it; a **remote trigger with non-severe damage
is declined as `improbable`.**

The ledger records the trigger the scenario requires, in one clause, so
a reviewer who knows a caller that produces it can say so and the
finding comes straight back.

### 6. Cost

What does the fix add, beyond the fix? Count what a future reader
inherits: a branch, a test file, a fixture, a comment, a dependency, an
abstraction with one caller, a configuration knob, or a concept they
must learn to follow the function.

Weigh that against the damage from gate 5. A guard against a cosmetic
remote scenario that costs a new code path and a test is declined as
`cost-exceeds-value`, as is a defensive wrapper with no reachable
failure mode.

Cost the smallest fix that would work, not the one the reviewer
proposed: a reviewer may propose a mechanism when the defect only
needed a condition. Offer the smaller fix.

## Verdicts

Every finding leaves screening with exactly one, never a conditional
("fix if X"):

- **`fix`**: cleared all six gates. Goes to the `respond-action` skill with the
  intended fix shape recorded.
- **`defer`**: true and worth doing, but not this branch's work.
  Pre-existing findings land here, with a follow-up recommendation.
- **`decline`**: with a reason: `wrong`, `misaligned`, `improbable`,
  `cost-exceeds-value`, or `duplicate` (another finding or an existing
  test already covers it). Each carries the evidence and a drafted
  reply.
- **`ask`**: screening genuinely cannot settle it: the truth depends
  on intent only the author has, or the alignment citation is
  contested. Goes to the user, not to a coin flip.

Reviewer-supplied severity labels are inputs, not verdicts.

## The ledger

One record per finding. The whole ledger is keyed by three values,
printed in the report's `## Ledger key` section and read back from the
session by the `respond-action` skill:

- **branch**: `git branch --show-current`; `none` when empty or
  outside a repository.
- **`HEAD`**: `git rev-parse --short=7 HEAD`; `none` when it fails (no commits,
  no repository).
- **digest**: the first 12 hex characters of the SHA-256 of the
  collected feedback as the reviewers wrote it: one line per comment,
  review body, or pasted block, `<id>` TAB `<original text>`, whitespace
  collapsed, sorted bytewise, newline-terminated. The id is the one the
  source returns; pasted text and a session's review output have none, so
  the id is `paste` or `session` and the text is the whole block, without
  the instruction wrapped around it ("Fix the findings below"). A run that
  reuses a ledger hashes the source that ledger screened, not its own
  argument text, so typed and screened runs match. Never
  hash a claim you trimmed or paraphrased: two runs would differ. It
  covers every comment before splitting, dropping, or merging, so new or
  edited feedback changes it.

`ledger_key.py` computes the digest. For a pull request it fetches the
reviews, issue comments, and inline review comments itself; `current` names
the current branch's pull request. A failed `gh` call exits 4 and prints no
digest:

```console
$ python3 ./ledger_key.py \
    --pr <n|url|current>
```

For pasted text or a session's review output, never use a shell heredoc: a
line equal to its delimiter ends it and the rest runs as shell. Make a file,
write the findings into it with the file tool, and hash it as one block
under the id `paste` or `session`:

```console
$ mktemp "${TMPDIR:-/tmp}/respond-feedback.XXXXXX"
```

```console
$ python3 ./ledger_key.py \
    --block paste \
    <path-printed-above>
```

Delete that file afterwards with `rm -- <path-printed-above>`.

the `respond-action` skill recomputes all three from the feedback it collects.
Any mismatch means the ledger is stale, and screening runs again rather
than acting on an old picture. When the report is no longer in the
session, there is no ledger.

Each record carries:

- **id**: stable within the run; the reviewer's own id when it has
  one.
- **source**: the author's login, whether that author is a bot, and the
  thread or review it came from.
- **claim**: the reviewer's words, quoted and trimmed to the assertion.
- **location**: file and symbol.
- **gates**: each gate that ran, with its evidence.
- **verdict**: one of the four above, with its reason.
- **fix shape**: for `fix`: the minimal change, forward commit or
  `fixup!`.
- **reply**: for `decline` and `defer`: text a reviewer can answer.
