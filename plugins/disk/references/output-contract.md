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
labels on bullets, no recap ending. The first line of the reply is the hero
or result sentence; nothing precedes it, including a note on which tool,
skill, or process ran.

A blocked or halted run (any layer or path that cannot be read, a failed
proof, a declined approval) uses the blocked shape and no `##` sections:
four sentences total: one result sentence, then exactly three plain
bullets, one sentence each: `Measured`, `Not measured`, and `To continue`;
put any necessary command after the last bullet. Fill `Measured` from
the survey's `filesystem` fields and classified in-scope directories;
leave rejected probe inventory out. Fill `Not measured` from `errors`
or a recorded command failure, naming only paths that were attempted and
failed; a parent that failed does not make its children, or the default
locations of a requested category, unreadable. A path under `skipped` was
not attempted: write "not surveyed", never "could not be read". Unknown usage stays unknown,
with no guessed location. No unrelated cleanup,
TRIM findings, or recap. Never estimate what was not measured,
and never attribute unmeasured space to a path or directory. Give no
size for what was not read, including used-minus-measured arithmetic,
and do not guess which layer is the cause ("probably", "more likely").
Say "could not be read" about the layer.

A blocked usage report opens: "The survey is incomplete; the location of
unmeasured usage is unknown." A blocked reclaim opens: "No cleanup ran:
no in-scope candidate passed its checks." Keep the opening separate from
the measured figures. `To continue` asks for the missing measurement or
a readable path; it does not explain where the missing usage might be.

A refused guard opens with the blocked-reclaim sentence and uses the same
three bullets; print no command, since the guard call stays in the
transcript. After an incomplete open-handle probe, `To continue` is: "Resolve the
reported lsof error and retry the same guard; if it refuses again, leave
the target in place." This checks caller-visible handles, not every
process on the machine.

A search target is not a finding: an unreadable home directory does not
establish that caches live there, and a size-floor survey does not prove
the readable filesystem contains no caches.

A `/disk:reclaim` plan awaiting approval uses the same section order, with
the hero line first and no heading of its own such as "Plan". It ends
with the approval question, and states projected figures as projections.

A declined environment halt (the user asked the agent to run
`wsl --shutdown` itself) uses the same shape. Say what the shutdown
interrupts in `To continue`, then put the command in a `powershell` fence for the
user to run. The user's host-space request permits this handoff even
when its payoff is unknown. Say "not yet known" when host recovery
has not been measured; an apparent size gap does not establish it.

The same test governs the hand-off after `/disk:reclaim`: print the
commands only when an apparent size gap was measured or the user asked
about host space. Otherwise write one sentence, "Host recovery is
unmeasured; run /disk:usage to measure the vhdx", with no commands and no
claim that none are needed.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

````text
No cleanup ran: no in-scope cache was verified.

- Measured: the WSL guest, 61% used, 344 GiB available.
- Not measured: the home directory could not be read.
- To continue: share a readable cache path or run the command below in
  your own shell and share its output.

```console
$ du -xh -d 2 ~
```
````

The last bullet is the ask. Add no separate closing question and no
`AskUserQuestion` panel to a blocked run.

## Single-path question

When the user asks about one path ("is X safe to delete?") and the run
is not blocked, skip the sections. Open with one sentence giving the
verdict and the measurement behind it, with no `✓` or `⚠` prefix, then
bullets for the proof outcome, the size and its layer, and the decision
that is the user's. Open with what the path holds ("holds two files that
notes lacks"), never "it isn't a copy of notes". End on the last bullet, with no recap of what was or
was not changed.

Reply in this shape, as plain text outside any code fence, with plain
bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Do not delete notes-backup-2026: it holds two files that notes lacks, and
the root filesystem has 344 GiB free.

- Proof: the two trees share no paths; no other copy was established.
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
percentage. For virtual disks, show backing-file apparent size beside
guest used space. Label their difference an apparent gap, not recoverable
host space; host allocation or free-space measurements are separate.

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

`## Needs a decision` — data without a proved replacement and anything that
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
  apparent size 780 GiB; apparent gap 168 GiB, host recovery unmeasured.

## Biggest consumers

- ~/.cache: 38 GiB, guest.
- ~/study: 71 GiB, guest.

## Regenerable

- npm and uv caches: 22 GiB; rebuilt by the next install.

## Protected

- Agent transcripts: 14 GiB, kept; no native compression found.
```

## After execution

The completion report uses this order, omitting empty sections:
`## Protected`, `## Needs a decision`, `## Reclaimed`, `## Left alone`,
then `## Only you can run this`. Put the deletion result in the hero;
do not move `## Reclaimed` ahead of the pending decisions.

Do not replay the survey in a completion report. Include each finding
once; omit unchanged inventory. Data excluded from the approved plan
belongs under `## Needs a decision` or `## Protected`, not `## Left alone`.

`## Reclaimed` — what was actually deleted or merged, with the
measured free-space delta per layer, one bullet per item. Leave out how
the guard was invoked (PATH, fixture or output files). When measured and predicted
disagree, state both. Give a cause only if checked; otherwise say
"cause not checked" without speculating about concurrent writers.

`## Left alone` — what the plan covered but execution skipped, with
the reason. A failed proof, a repository with unpushed work, or a
declined approval each belong here.

Fill this completion shape from the guard result and candidate inventory.
Copy the guard's observed delta; another `df` reading is a later sample,
not a replacement for that observation. Omit an unproved cause or copy
location, not the uncertainty. Add other nonempty sections in the order
above, and omit the host sentence when this is not a virtual disk.

```text
Deleted <approved cache>, <measured size> on <measured filesystem>.

## Needs a decision

- <path>: <measured size and age>, kept; no replacement was proved.

## Reclaimed

- <approved cache>: <measured size> removed; filesystem free-space delta
  <guard's signed delta>; cause not checked.

Host recovery is unmeasured; run /disk:usage to measure the vhdx.

Keep <decision path>, or delete it?
```

## Rules

Report findings about the machine, never about the session's sandbox: no
stand-in home directories, scratch totals, or tool limits. Say "could not
be read" about a layer, never "this session is not allowed", "the
sandbox blocks", "it is mounted read-only", or a request to be given
write access. Ask the user to run a command "in your own shell", never
"outside this session".
Describe what a halt interrupts as "every shell, server, and container",
never "this session", and never call a path "read-only to me".

Name a path or layer as holding space only from a measurement in this
run. Never characterize an unmeasured path ("these are system packages
and logs").

State the rebuild command and its observed requirements, such as local
CPU time or a download. Duration and download size stay unknown unless
measured; deleting a regenerable item never "costs nothing".

Emit a command the user runs as a `console` fence with a `$ ` prefix,
one command per fence; a Windows command uses a `powershell` fence.

Attach every figure to a layer. Separate guest cleanup, backing-file
apparent gap, and measured host recovery. Mark missing measurements
unknown; never turn an apparent gap into projected host recovery. A
guest-side number presented as machine-wide recovery is wrong even when
the arithmetic is right.

Give a cause only when a command measured it; otherwise say what was
observed and that the cause was not checked. Describe a file by what you
read in it, not by its name or age. Write what a thing is, not what it
is not (no "it isn't X: it is Y").

Distinguish measured from projected in the words themselves. Do not
promise a compaction yield from guest free space or apparent file size.
Say "currently unallocated", never "never allocated" or "never took host
space". Name the host drive only when a measurement named it.

State a claim about what a tool supports (for example, that it reads
compressed transcripts) only with help text, documentation, or a
disposable-fixture test. Binary strings are clues, not capability proof.

A comparison proves uniqueness only relative to its named keeper. Without
a wider search, say "no other copy was established", not "your only copy"
or "I found no other copy" with or without "anywhere". Name the actual
search scope when reporting that a search found no copy. In a
single-path or `## Needs a decision` entry, write the proof as "compared
against <keeper> only; no other copy was established" or "no replacement
was proved".

Use GiB at or above 1 GiB and MiB or KiB below it (`6 MiB`, never
`0.0061 GiB`), one unit per figure, converting what a tool printed
(`1007G`, `14 GB`, `3 MB`); never write MB, GB or KB; do not repeat raw byte counters, including one read from a script, file,
or fixture (write `2.9 MiB`, not `3,000,000 bytes`).

Write every path in the reply relative to the approved scope, or as `~/…`
only for a path inside the real home directory, and a Windows profile as `/mnt/c/Users/<account>/…`; no absolute path or
account name appears in it. Literal absolute installed script paths belong
in internal tool calls, not in the final reply.

Name what was skipped. A report that silently omits protected history
reads as having missed it rather than having preserved it.

End a sectioned report with an `AskUserQuestion` panel offering the next
step, unless already inside plan mode. Without an interactive question
tool, print the question and stop. A blocked run and a single-path
answer end on their last bullet instead. Run standalone, `/disk:usage`
ends by offering `/disk:reclaim`; run through the `disk` router it does
not. After `/disk:reclaim`, it is the handoff steps or a narrower
follow-up pass.
