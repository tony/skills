# Output contract

## Contents

- Hero block
- Sections
- After execution
- Rules

Every command reports in the same fixed order. A hero block may precede
it. Omit a section that has no findings rather than writing that it is
empty; that includes `## Protected` when no history was found. No bold labels on bullets, no recap ending.

A blocked or halted run (any layer or path that cannot be read, a failed
proof, a declined approval) skips the sections: one sentence stating the
result, then what was measured, what was not, and what the user needs to
do next. Never estimate what was not measured, and never attribute
unmeasured space to a path or directory.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Nothing was reclaimed: the host drive could not be read, so no layer is
confirmed as the binding constraint.

- Measured: the WSL guest, 61% used, 344 GiB available.
- Not measured: C: (host) and the ext4.vhdx backing file.
- To continue: run `df -h /mnt/c` and share the output, or grant access
  to /mnt/c.
```

## Hero block

One to four lines naming the binding constraint. Prefix with `⚠` when
a layer is 90% used or more, `✓` otherwise. No prose paragraphs. Name a
host layer as the constraint only from a measurement.

The binding constraint is the filesystem closest to full, which may not be
the one the user asked about: a full host beats a comfortable guest.

## Sections

Use these level-2 headings verbatim, in this order.

**## Layers** — every filesystem with size, used, available, and use
percentage. For virtual disks, the backing file's apparent size beside
the guest's used space, with the balloon called out as its own figure.

**## Biggest consumers** — ranked by size, with the layer each sits on.
Report the measured number; do not round toward a more impressive
total.

**## Regenerable** — caches, stores, and build artifacts, with the
command that rebuilds each. Aggregate per ecosystem rather than listing
every directory.

**## Redundant** — candidate copies with their proof outcome:
redundant, mergeable, conflicted, or unique. Every entry names the
keeper it was compared against. An entry without a proof outcome does
not belong in this section.

**## Protected** — agent history and other irreplaceable data, with
what makes each protected. Include the total so the user can see what
was deliberately not reclaimed. State each tool's compression support
where it bears on a proposal.

**## Needs a decision** — stale-but-unique data and anything that
resisted classification, each with size, age, and origin. These are
questions, not candidates. Layers that could not be measured go under
`## Layers` as "not measured".

**## Only you can run this** — commands requiring the environment to be
halted, or a host-side administrator shell. One command per block, with
what it interrupts stated before it. Present these as pending.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

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

`/disk:reclaim` adds two sections after the above.

**## Reclaimed** — what was actually deleted or merged, with the
measured free-space delta per layer. When measured and predicted
disagree, state both and explain the gap.

**## Left alone** — what the plan covered but execution skipped, with
the reason. A failed proof, a repository with unpushed work, or a
declined approval each belong here.

## Rules

Report findings about the machine, never about the session's sandbox: no
stand-in home directories, scratch totals, or tool limits.

Say what rebuilding a regenerable item costs (time, bandwidth); never
write that deleting it "costs nothing".

Emit a command the user runs as a `console` fence with a `$ ` prefix,
one command per fence; a Windows command uses a `powershell` fence.

Attach every figure to a layer. State three numbers for a virtual disk:
what the cleanup frees inside the guest, what the balloon already holds,
and what the host gains once the user completes the steps only they can
run. A guest-side number presented as
machine-wide recovery is wrong even when the arithmetic is right.

Distinguish measured from projected in the words themselves. "Frees
40 GB once you compact" and "freed 40 GB" are different claims.

Name what was skipped. A report that silently omits protected history
reads as having missed it rather than having preserved it.

End with an `AskUserQuestion` panel offering the next step, unless
already inside plan mode. Without an interactive question tool, print
the question and stop. Run standalone, `/disk:usage` ends by
offering `/disk:reclaim`; run through the `disk` router it does not. After `/disk:reclaim`, it is the handoff steps or a
narrower follow-up pass.
