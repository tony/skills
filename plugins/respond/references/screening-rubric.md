# Screening Rubric

Every claim a reviewer makes — human or machine — passes six gates
before a single file is edited. `/respond:check` runs them and writes
the ledger; `/respond:action` reads that ledger and does not
re-litigate it.

Both failure modes are expensive. Fixing everything a reviewer says
produces sprawling branches, tests nobody needed, and comments that
will confuse a reader in three years. Dismissing what a reviewer says
ships bugs. Neither compliance nor reflex is a screening method —
evidence is, and every verdict below carries some.

## The gates

Run them in order and stop at the first one that settles the finding.
A finding that clears all six is accepted for fixing.

### 1. Locate

Tie the claim to a specific place in the code — file and symbol, not a
line number that the next commit invalidates. A finding whose target
cannot be found is `unlocatable`: report it, ask the reviewer what they
meant, and never guess at a fix for it.

### 2. Truth

Is the claim true of the code as written? Read the code and its
callers. Reviewers assert; the ledger records what you verified.

A claim is `wrong` when the code already does the thing, when the path
the claim depends on is unreachable, when it rests on a misread of an
API's contract, or when it describes a version of the file that no
longer exists. Automated reviewers produce this class constantly:
their confidence is a rendering choice, not a measurement.

### 3. Provenance

```
NO FIX WITHOUT PROVENANCE
```

Resolve the base: `--base=<ref>` if given, else the merge-base with the
remote trunk:

```console
git merge-base origin/<trunk> HEAD
```

With no remote, fall back to the local trunk (`main` or `master`); when
neither resolves, ask for the base rather than guessing.

Then test whether this branch introduced or last touched the flagged
code — `git diff <base>...HEAD -- <file>` for the region, and
`git log -L<range>:<file> <base>..HEAD` or blame when the diff is
ambiguous. Classify:

- `in-branch` — this branch added or changed it. Proceeds.
- `pre-existing` — present at the base. Deferred by default.
- `mixed` — the branch touched part of it. Split at that boundary: the
  branch's part proceeds, the remainder defers.
- `disputed` — settled at gate 2 already.

A reviewer flags; the branch owner scopes. Pre-existing findings are
real work, and real work deserves its own branch and its own review
rather than a ride on this one.

### 4. Alignment

Correct is not the same as correct *for this project*. A finding is
`misaligned` when the change it asks for contradicts a decision the
project has already made: a rule in `AGENTS.md` / `CLAUDE.md` or a
nested equivalent, the purpose the branch states in its pull request or
commits, a design the surrounding code visibly and deliberately
encodes, or the convention every sibling module follows.

The guard against abusing this verdict: **a misaligned verdict must
cite a written or demonstrated project decision.** A preference
invented while screening is not a decision. If the citation cannot be
produced, the finding has not been declined — it has been resisted, and
it goes back to gate 5 on its merits.

The reply for a misaligned finding names the decision, so the reviewer
can argue with the decision itself rather than with the triage.

### 5. Odds

How often does the scenario actually fire? Classify the trigger it
needs and the damage it does; do not invent a probability.

| Trigger | Meaning |
|---|---|
| Routine | Reachable on a path users take, with ordinary inputs. |
| Occasional | Needs an unusual but attainable combination — a rare flag, an empty collection, a slow network, a specific platform the project supports. |
| Remote | Needs a combination nobody has produced: a race with a microsecond window on a single-threaded path, an input no caller can construct, a platform the project does not support. |

| Damage | Meaning |
|---|---|
| Severe | Security, data loss, corruption, or a silently wrong result a user would act on. |
| Visible | A crash, an error, a wrong render — the user notices and can report it. |
| Cosmetic | Style, an internal log line, a message no user reads. |

Severe damage clears this gate at any trigger — a remote security bug
is still a security bug, and the cost of being wrong is unbounded.
Otherwise: routine and occasional triggers clear the gate; a **remote
trigger with non-severe damage is declined as `improbable`.**

The ledger records the trigger the scenario requires, in one clause.
That is what makes the verdict falsifiable: a reviewer who knows a
caller that produces it says so, and the finding comes straight back.

### 6. Cost

What does the fix add, beyond the fix? Count what a future reader
inherits: a branch, a test file, a fixture, a comment, a dependency, an
abstraction with one caller, a configuration knob, or a concept they
must learn to follow the function.

Weigh that against the damage from gate 5. A guard against a cosmetic
remote scenario that costs a new code path and a test to hold it up is
declined as `cost-exceeds-value`. So is a defensive wrapper with no
reachable failure mode — that is the same claim gate 5 already
rejected, wearing a fix's clothes.

Cost is measured against the smallest fix that would work, not the one
the reviewer proposed. Reviewers routinely propose a mechanism when
the defect only needed a condition. Cost the smaller fix and offer it.

## Verdicts

Every finding leaves screening with exactly one:

- **`fix`** — cleared all six gates. Goes to `/respond:action` with the
  intended fix shape recorded.
- **`defer`** — true and worth doing, but not this branch's work.
  Pre-existing findings land here, with a follow-up recommendation.
- **`decline`** — with a reason: `wrong`, `misaligned`, `improbable`,
  `cost-exceeds-value`, or `duplicate` (another finding or an existing
  test already covers it). Each carries the evidence and a drafted
  reply.
- **`ask`** — screening genuinely cannot settle it: the truth depends
  on intent only the author has, or the alignment citation is
  contested. Goes to the user, not to a coin flip.

Severity labels supplied by the reviewer are inputs, not verdicts. A
bot's "critical" and a human's "nit" both enter the rubric and leave
with whatever the six gates produced.

## The ledger

One record per finding, and the whole artifact is keyed by the branch,
`HEAD`, and a digest of the feedback it screened. `/respond:action`
recomputes that key; when the key does not match, the ledger is stale
and screening runs again rather than acting on an old picture.

Each record carries:

- **id** — stable within the run; the reviewer's own id when it has
  one.
- **source** — who said it and where: the author's login, whether that
  author is a bot, and the thread or review it came from. A defect
  three reviewers reported is **one** record with three sources.
- **claim** — the reviewer's words, quoted and trimmed to the assertion.
- **location** — file and symbol.
- **gates** — the result of each gate that ran, with its evidence: the
  commit or diff that settled provenance, the citation that settled
  alignment, the trigger that settled odds.
- **verdict** — one of the four above, with its reason.
- **fix shape** — for `fix`: the minimal change, and whether it lands
  as a forward commit or a `fixup!`.
- **reply** — for `decline` and `defer`: the text a reviewer would find
  answerable.

## Rationalizations

| Thought | Reality |
|---|---|
| "The reviewer asked for it, so I should fix it" | The reviewer flags; the owner scopes. Compliance is not review. |
| "Three bots flagged it, so it must be real" | Bots share training data and prompt shapes. Three agreements are one opinion; the code is the evidence. |
| "It's a real bug, declining feels wrong" | Declining `improbable` is a recorded, falsifiable claim about the trigger, published to the reviewer. Ignoring is silence; this is not that. |
| "It's a one-line guard, the cost is nothing" | The line is one; the test that holds it up, the comment explaining it, and every future reader's second of confusion are not. |
| "Provenance is obvious here" | Skipping the diff is how a branch ends up fixing trunk code and burying that fix inside an unrelated review. Run it. |
| "It contradicts how I'd have built it" | That is not an alignment citation. Find the written decision or drop the objection. |
| "I'll note the reasoning in a comment" | Screening reasoning belongs in the ledger and the reply. Code carries invariants, not review history. |
