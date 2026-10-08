# Output contract

## Contents

- Hero block
- Single-path question
- Sections
- After execution
- Rules

Every command reports in the same fixed order. A hero block may precede
it. Omit a section that has no findings rather than writing that it is
empty; that includes `## Protected` when no history was found. No bold
labels on bullets, no recap ending.

A blocked or halted run (any layer or path that cannot be read, a failed
proof, a declined approval) uses the blocked shape and no `##` sections:
one sentence stating the result, then what was measured, what was not,
and what the user needs to do next. Never estimate what was not measured,
and never attribute unmeasured space to a path or directory. Give no
size for what was not read, including used-minus-measured arithmetic,
and do not guess which layer is the cause ("probably", "more likely").
Say "could not be read" about the layer.

A this skill plan awaiting approval uses the same section order, with
the hero line first and no heading of its own such as "Plan". It ends
with the approval question, and states projected figures as projections.

A declined environment halt (the user asked the agent to run
`wsl --shutdown` itself) uses the same shape. Add a line saying what the
shutdown interrupts, then the command in a `powershell` fence for the
user to run. Print it when the balloon is measured above zero, since
compaction returns space without any deletion. Say "not yet known" when
the backing file could not be read, and say no shutdown is needed only
when the balloon was measured near zero.

The same test governs the hand-off after this skill: print the
commands only when the balloon is measured above zero or the user asked
about host space. Otherwise write one sentence, "Host recovery is
unmeasured; run the `disk-usage` skill to measure the vhdx", with no commands and no
claim that none are needed.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Nothing was reclaimed: the host drive could not be read, so no layer is
confirmed as the binding constraint.

- Measured: the WSL guest, 61% used, 344 GiB available.
- Not measured: C: (host) and the ext4.vhdx backing file; both could not
  be read.
- To continue: run the command below and share the output.

```console
$ df -h /mnt/c
```
```

The last bullet is the ask. Add no separate closing question and no
`ask-user-choice` panel to a blocked run.

## Single-path question

When the user asks about one path ("is X safe to delete?") and the run
is not blocked, skip the sections. Open with one sentence giving the
verdict and the measurement behind it, with no `✓` or `⚠` prefix, then
bullets for the proof outcome, the size and its layer, and the decision
that is the user's. End on the last bullet, with no recap of what was or
was not changed.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Do not delete notes-backup-2026: it holds two files that notes lacks, and
the root filesystem has 344 GiB free.

- Proof: the two trees share no paths, so the backup is unique.
- Size: 8 KiB on the guest ext4 filesystem, of 344 GiB free.
- Your call: keep it, or move the two files into notes and re-run the
  comparison.
```

## Hero block

One to four lines naming the binding constraint. Prefix with `⚠` when
a layer is 90% used or more, `✓` otherwise. No prose paragraphs. When
the reply opens with a one-sentence verdict, that sentence is the hero;
add no second prefixed line. Name a
host layer as the constraint only from a measurement.

The binding constraint is the filesystem closest to full, which may not be
the one the user asked about: among the layers measured, a full host
beats a comfortable guest. When the user scoped one path and the other
layers were left out, name the constraint among the layers measured.

## Sections

Use these level-2 headings verbatim, in this order.

`## Layers` — every filesystem with size, used, available, and use
percentage. For virtual disks, the backing file's apparent size beside
the guest's used space, with the balloon called out as its own figure.

`## Biggest consumers` — ranked by size, with the layer each sits on.
Report the measured number; do not round toward a more impressive
total.

`## Regenerable` — caches, stores, and build artifacts, with the
command that rebuilds each. Aggregate per ecosystem rather than listing
every directory.

`## Redundant` — candidate copies with their proof outcome:
redundant, mergeable, conflicted, or unique. Every entry names the
keeper it was compared against. An entry without a proof outcome does
not belong in this section.

`## Protected` — agent history and other irreplaceable data, with
what makes each protected. Include the total so the user can see what
was deliberately not reclaimed. State each tool's compression support
where it bears on a proposal.

`## Needs a decision` — stale-but-unique data and anything that
resisted classification, each with size and age. These are
questions, not candidates.

`## Only you can run this` — commands requiring the environment to be
halted, or a host-side administrator shell. One command per block, with
what it interrupts stated before it. Present these as pending.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
⚠ C: (host) is 94% full; the WSL guest is 61% used.

## Layers

- C: 931 GiB, 876 used, 55 available, 94%.
- WSL guest ext4: 1007 GiB, 612 used, 344 available, 61%; ext4.vhdx
  apparent size 780 GiB, so 168 GiB is balloon.

## Biggest consumers

- ~/.cache: 38 GiB, guest.
- ~/study: 71 GiB, guest.

## Regenerable

- npm and uv caches: 22 GiB; rebuilt by the next install.

## Protected

- Agent transcripts: 14 GiB, kept; no native compression found.
```

## After execution

this skill adds two sections after `## Needs a decision` and moves
`## Only you can run this` to the end, after `## Left alone`.

`## Reclaimed` — what was actually deleted or merged, with the
measured free-space delta per layer. When measured and predicted
disagree, state both and explain the gap.

`## Left alone` — what the plan covered but execution skipped, with
the reason. A failed proof, a repository with unpushed work, or a
declined approval each belong here.

## Rules

Report findings about the machine, never about the session's sandbox: no
stand-in home directories, scratch totals, or tool limits. Say "could not
be read" about a layer, never "this session is not allowed", "the
sandbox blocks", "it is mounted read-only", or a request to be given
write access. Ask the user to run a command "in your own shell", never
"outside this session".

Name a path or layer as holding space only from a measurement in this
run. Never characterize an unmeasured path ("these are system packages
and logs").

Say what rebuilding a regenerable item costs (time, bandwidth); never
write that deleting it "costs nothing".

Emit a command the user runs as a `console` fence with a `$ ` prefix,
one command per fence; a Windows command uses a `powershell` fence.

Attach every figure to a layer. State three numbers for a virtual disk:
what the cleanup frees inside the guest, what the balloon already holds,
and what the host gains once the user completes the steps only they can
run. A guest-side number presented as machine-wide recovery is wrong even
when the arithmetic is right.

Give a cause only when a command measured it; otherwise say what was
observed and that the cause was not checked. Describe a file by what you
read in it, not by its name or age. Write what a thing is, not what it
is not (no "it isn't X: it is Y").

Distinguish measured from projected in the words themselves. "Frees
40 GiB once you compact" and "freed 40 GiB" are different claims.

State a claim about what a tool supports (for example, that it reads
compressed transcripts) only with the help text, docs page, or binary
string you read; otherwise say it was not checked.

Use GiB at or above 1 GiB and MiB or KiB below it (`6 MiB`, never
`0.0061 GiB`), one unit per figure, converting what a tool printed
(`1007G`, `14 GB`). Write `~` instead of the home path in commands.

Name what was skipped. A report that silently omits protected history
reads as having missed it rather than having preserved it.

End a sectioned report with an `ask-user-choice` panel offering the next
step, unless already inside plan mode. Without an interactive question
tool, print the question and stop. A blocked run and a single-path
answer end on their last bullet instead. Run standalone, the `disk-usage` skill
ends by offering this skill; run through the `disk` router it does
not. After this skill, it is the handoff steps or a narrower
follow-up pass.
