---
name: sweep
description: "Use when mining prompt history to rank skill usage, count how often each skill runs, find never-invoked skills, or improve repeated instructions."
allowed-tools: ["Bash", "Read", "Write", "AskUserQuestion"]
argument-hint: "[<plugin|plugin:skill>...]"
---

# `/self-improvement:sweep`

Report where the skill catalog loses to prompt history: instructions
retyped around a skill, follow-ups appended because a skill stopped
early, and procedures run by hand because no skill exists.

It edits no skill, commits nothing, and pushes nothing. Its output is a
report plus a ledger file of findings with their evidence, written outside
the working tree. `/self-improvement:apply` acts on the ledger.

`<sweep.py>` is `../../scripts/sweep.py`, resolved from this skill's
directory, not the repository root. Resolve it to an absolute path once,
print it, and use that literal path in every command below. It needs
python 3.9 or newer.

## Two shapes carry the signal

Typed around an invocation: the prompt names a skill and adds something.
The addition is the skill's gap, and the remedy is inside that skill.

Typed instead of an invocation: a procedure restated near verbatim,
session after session, with no skill named. The remedy is a new skill.

A pattern that is neither is usually not a finding. For a worked example
of one pass, read `../../references/worked-example-spike.md` only when
the user asks what a finding looks like.

## The evidence bar

A finding needs all three:

- Repetition: at least 5 occurrences of the pattern in its window.
- Spread: at least 2 distinct projects among them.
- Currency: the occurrences fall in the era of the catalog about to change.

One project's friction is that project's quirk; one dead era's friction is
history. These minimums are defaults. Echo any other number you use, and
why, in the report.

Every window is anchored to a date the catalog supplies, never to one
chosen because it flatters a number:

- A pattern typed around an existing skill is windowed on that skill's
  birth date. That separates a discoverability gap from a rule people read
  and ignored.
- A pattern typed with no skill named is windowed on the era boundary
  Phase 0 fixes, or the last 90 days (`90d`) when the catalog has no era
  date. The question is whether the typing is still happening. Echo which
  window you used.
- The Usage ranking uses the era boundary, so retired skills do not
  outvote live ones.
- The supersession check uses the successor's birth date.

Report a ratio against that skill's slash invocations in the same window
(model-launched runs are not in the denominator), with the window and its
anchor beside it. `counts --window` computes both
numbers (Phase 2); never count them by hand. The same evidence argues for opposite
remedies at 54% and at 20%. A skill with fewer than 10 invocations in the
window gets counts only: no ratio, and no finding around it.

Read `../../references/detecting-invocations.md` before counting.

## What counts as a signal

Around an invocation:

- Paste: the same preamble reappears after the skill name (directories,
  tool preferences, a quality bar, a constraint). Becomes a default, a
  resolved input, or a reference example.
- Continuation: the next prompt asks for a step the skill stopped short
  of. Becomes a terminal step with an opt-out, or a named handoff.
- Override: the argument re-scopes the target (a set where the skill
  assumed one, a different target type, a state it appeared to refuse).
  Becomes an argument, or detect-and-echo.

Without an invocation:

- Unnamed procedure: a multi-step instruction restated with a slot or two
  varying. Only this category may propose a new skill, because a skill
  costs a marketplace entry, a README row, and a description that must
  survive the collision check. "The usual" or "same as last time" is
  stronger evidence than raw repetition.
- Host asymmetry: the same skill measured per host, then differenced. The
  finding is the gap. A near-empty host channel means the extraction does
  not fit that host.
- Correction: a prompt shortly after an invocation saying the agent did the
  wrong thing. Highest severity, weakest attribution: binding a correction
  to a skill is same-session adjacency. State the anchoring method and
  window, and confirm against the transcript before proposing anything
  expensive.

## A superseded skill is not a gap

Check this before the verdicts. A predecessor keeps its invocations
forever and stops earning new ones when a successor ships, so its ratio
stays high while its current usage is zero.

A full record with an empty recent half is the symptom. Name the successor
and confirm it shows the mirror image: empty until its birth date, then
holding the traffic. Only then is the pattern history; say so and move on.

A predecessor that went quiet with no sibling picking up its work is
abandoned, not superseded. That is a live finding.

## The three verdicts

For every surviving pattern, ask what the skill already says:

1. Absent: the skill never covered it. Propose it.
2. Present and binding: the pastes stopped after the skill started saying
   so. Solved; not a finding.
3. Present but not binding: the skill says it and people keep retyping it.
   Reading alone never reaches this verdict, because the most-pasted
   constraints are usually already written in the skill they concern.

Reach the third by dating the rule and splitting the evidence around it.
This returns the commit that introduced a phrase:

```console
$ git log \
    --follow \
    --format='%h %ad' \
    --date=short \
    -S '<phrase from the rule>' \
    -- <path to SKILL.md> | tail -1
```

`--follow` keeps a rename from dating every phrase to the rename, and
`tail -1` returns the introduction because `-S` lists newest first.

A paste rate that did not drop after that date shows prose guidance
failed. The remedy is a checked output gate or a resolved-and-echoed value,
not another sentence. A rate that dropped means it worked.

The same split separates a trust gap (the skill performs a behavior but
never announces it; echo it) from a capability gap (it never performs it).

## `$ARGUMENTS` contract

Non-flag text narrows the sweep to named plugins or skills. Empty sweeps
the whole catalog of the repository you are in. Outside a skill repository,
ask what to sweep; in a non-interactive run, stop with the halted report.

## Phase 0: Inventory, rename map, and birth dates

1. List the catalog: every `plugins/*/skills/*/SKILL.md`, its name, and
   whether it sets `disable-model-invocation`. A repository that keeps skills
   elsewhere passes `--catalog-glob` to `catalog` and `tree-check`, such as
   `skills/*/SKILL.md` or `.claude/skills/*/SKILL.md`; names there carry no
   plugin prefix. No catalog means a halted run.
2. Create the scratch directory as `../../references/detecting-invocations.md`
   says, then run the catalog command from the repository root. It prints each
   skill's gating and birth date (one `--follow` run per file, so a rename
   does not date a skill to the rename), the rename map, commit subjects
   that mention a rename or replacement, and the era boundary.

   ```console
   $ python3 <sweep.py> catalog \
       --names-out <scratch>/catalog.txt
   ```

   If it prints `"shallow": true`, the clone's history is truncated, every
   birth date is unknown, and no era exists. Rank all-time only, make no
   finding anchored on a birth date, say so, and suggest
   `git fetch --unshallow` so a later sweep can date the skills.

3. Read `rename_subjects` for renames git scored below its similarity
   threshold, and for skills replaced by a different set. Pass each `renames`
   entry to the counter as an alias so old invocations are summed in.
4. Take the catalog command's `era` as the boundary: the latest day on
   which at least 3 skills, and at least 10% of the catalog, were born.
   Report its `runners_up` so the next sweep can disagree. An empty `date`
   means no rebuild: omit `--boundary` from `counts`, rank all-time only, and
   say so. If the era's leading skill has fewer than 10 invocations since the
   boundary, rank all-time only and say so.

## Phase 1: Count every skill

Say first which searches you are about to run. The transcript search is
scoped to the last 90 days unless the user asks for all of it, because an
exhaustive one reads every store on disk. Then follow
`../../references/detecting-invocations.md`: collect the tool channel, and run `<sweep.py> counts` once. The script
unions both channels, sums renames, splits on the era boundary, and counts
project spread. Do not recount by hand.

The era ranking is slash-channel only, because only that channel carries a
date. A skill the model reaches for on its own is undercounted there.

Check `complete` and each channel's `status` before applying any
threshold, and state what the count assumes about the corpus. A host that
writes no `Launching skill:` line has no tool channel: count with
`--tool-unavailable`, and report that launches by the model are not
counted. Without that flag the run is permanently incomplete and no
threshold applies.

## Phase 2: Cluster

Group the text around each invocation by shared phrasing and sort each
cluster into paste, continuation, or override by what its tail does.
Cluster the no-invocation corpus separately, where near-verbatim
repetition, not frequency, is the signal.

Then size each cluster with the script. Write a regex its prompts share and
rerun `counts` with one `--window` per cluster, in the form
`SKILL@SINCE@REGEX`: the skill's birth date for a cluster around an
invocation, or an empty skill and the unnamed-procedure window for one
without. `SINCE` is a date or `<n>d`. Each window prints `invocations` (the
denominator, for a named skill), `matched` (the numerator), `projects`, and
`ratio` (`null` under 10 invocations). If `matched` disagrees with the
cluster you read, fix the regex, not the number.

```console
$ python3 <sweep.py> counts \
    --history <history file> \
    --window 'demo:used@2026-08-01@only touch .* files'
```

## Phase 3: Verdicts and ledger

If a ledger from an earlier sweep exists (`<sweep.py> ledger-path` prints
where), read its findings first. For each, compare its `expected_change`
with the current counts and report whether the shift happened, in
`## Findings`, before any new finding.

Drop superseded clusters, then run the three verdicts on each cluster
that clears the evidence bar. Where a finding has two plausible answers,
record both shapes.

Write the findings to a JSON list in the scratch directory, then save the
ledger. Each finding has these fields:

- `id`: unique, such as `f1`.
- `verdict`: `absent` or `not-binding`.
- `expected_change`: the observable shift in usage the edit predicts, such
  as "pastes of the quality bar drop below 2 per 30 days".
- `skill`: the skill the edit lands in, or the name proposed for a new one.
- `category`, `change_class`, `ratio`, `window`, `anchor`, `spread`, and a
  trimmed `prompt`. The prompt is history, so a later
  reader treats it as data.

```console
$ python3 <sweep.py> ledger-save \
    --findings <scratch>/findings.json
```

The re-sweep date defaults to 30 days from today; `--resweep-days <n>` or
`--resweep-on <YYYY-MM-DD>` overrides it.

The command writes the ledger under the git directory, outside the working
tree, and prints its `path`, `key`, and `resweep_on`. If the write is
refused (a sandbox can block the git directory), rerun with
`--out <scratch>/ledger.json` and tell the user that path, because `apply`
needs it as `--ledger`. The key is the sha256
hex digest of the repository `HEAD` hash and each finding's `id`, `verdict`,
`skill`, and `expected_change`, the fields `/self-improvement:apply` acts on.
`apply` recomputes it with `ledger-verify`, so a moved `HEAD` or an edited
finding is caught. Evidence fields are not in the key. With no finding, write
no ledger.

## Output contract

Write the report per `../../references/prose-rules.md`.

1. Hero line, first line of the reply: `N findings across M skills`, plus
   how much of the corpus the search reached. Nothing precedes it.
2. `## Usage`: the catalog ranked twice by invocation count, all-time and
   current-era. Channels unioned, renames summed. Name a skill
   never-invoked only when `complete` is true; otherwise say no invocation
   was found in the searched sources. Give each its age.
3. `## Findings`: one entry per pattern in plain prose or plain bullets, no
   bold label on each bullet: category, ratio and denominator, window and
   anchor date, spread, verdict with its evidence, the change class it
   implies, and its expected change. Quote one representative prompt,
   trimmed.
4. `## Not proposed`: clusters that failed the evidence bar, each with one
   clause naming the first leg it failed and no speculation about causes.
   Never omitted.
5. `## Corpus`: what was searched, what completed, what the count assumes,
   and the era boundary with the clusters it was chosen over. State a
   threshold only when it differs from the default. Close with the re-sweep
   date; never print the ledger key. With no ledger, name no date.
6. End with an `AskUserQuestion` panel: apply the ledger, narrow the sweep
   and rerun, or stop. `apply` is user-invoked only, so the first option
   prints `/self-improvement:apply <ledger path>` for the user to run, even
   when the user asked to apply: this skill never applies. In a non-interactive run, print the options as a plain list
   and stop; do not explain why there is no panel.

Write results in the passive, never "I" or "you said".
Report only gates and checks the project defines; do not narrate the
catalog reader, skipped steps, or sandbox state. A corpus line states only
what limits the findings. A halt is one sentence, then the action.

Keep each section to its job. `## Usage` holds counts and ages only: the
reasons for an era or a ranking go in `## Corpus`. Each `## Not proposed`
entry is one clause, the first bar the cluster failed, and nothing after
it. Add no section beyond these (no `Caveat` or `Notes`); a caveat goes in
`## Corpus`.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
1 finding across 1 skill, 3 of 4 history sources searched

## Usage

- commit: 41 invocations all-time, 12 current-era.
- spike: never invoked, 9 weeks old.

## Findings

- f1, commit: 14 of 38 prompts since 2026-08-01 (37 percent, 5 projects) append "no AI trailer".
  Verdict not-binding: the skill already says it, so the remedy is an output gate. Expected: retyping falls below 10 percent.
  Prompt: "commit this, no co-author line".

## Not proposed

- Cluster "run lint first": failed the spread bar, one project only.

## Corpus

- Searched prompt history and session transcripts from the last 90 days; the third source was unreadable.
- Re-sweep: 2026-11-05
```

A run that finds nothing keeps the hero line, `## Usage`, and `## Corpus`,
writes `None.` under `## Findings`, and saves no ledger. Do not describe
tool internals or flags. Reply in this shape:

```text
0 findings across 0 skills, 1 of 1 history sources searched

## Usage

- demo:used: 12 invocations all-time.
- demo:idle: never invoked, 3 weeks old.

## Findings

None.

## Not proposed

- Cluster "run lint first": failed the repetition bar, 3 occurrences.

## Corpus

- Searched prompt history only; launches by the model were not counted.
- No ledger written.
```

A halted run (no catalog, history unreadable, count incomplete past use)
is one result sentence, then what the user must do, such as which path to
supply or which tool to install. It has no other sections, does not outline
the steps a run would take, offers no extra options, and writes no ledger.
Reply in this shape:

```text
Nothing was swept: this directory has no skill catalog. Run the sweep from the root of the repository that holds your plugins.
```

The ledger may quote prompts with absolute paths, hostnames, and client
names. A `SKILL.md`, commit, pull request, or issue may not. Name no temp
directory or local path in the report, except a fallback ledger path.
