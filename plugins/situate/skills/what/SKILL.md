---
name: what
description: "Use when the user asks what is going on and needs a five-line summary of the session, branch, pull request, and ticket."
allowed-tools: ["Bash", "Read", "Grep", "Glob"]
argument-hint: "[what you are confused about]"
user-invocable: true
disable-model-invocation: true
---


# What

The reader is disoriented. End that in five lines.

Read `../../references/brief.md` first — it defines the
five-line budget, what earns a line, the option lines, and the evidence
tiers that keep this cheap enough to ask casually.

User arguments: $ARGUMENTS

## Procedure

### 1. Read what was actually asked

Empty `$ARGUMENTS` means the whole situation: what this session has been
doing, and where the repository stands.

An argument narrows it to that subject, and narrowing is the point —
`/situate:what the test failure` answers about the test failure and
spends no lines on branch position.

### 2. Answer from the session first

When the confusion is about what just happened (a command that ran, a
decision taken, why the work moved), the answer is already in context
and needs no tools.

When the session's memory is thin, gather the cheap tier:

1. Position: run `python3 ../../scripts/position.py` for branch, trunk,
   ahead/behind, uncommitted work, and stashes. `../../scripts/` resolves
   from this skill's directory: write the absolute path literally in the
   command. A `dotfile_repo` or an
   empty repository (`has_commits` false) gets one line saying so and no
   file list; the script prints nothing else then.
2. Commit subjects since the base:
   `git log --no-merges --format='%h %s' <trunk>..HEAD`.

A null `trunk` or a failed command means that layer is unavailable; say
so inside an existing line. Measuring from trunk is approximate on a
branch stacked over another branch, because the range carries the
parent's commits; say so rather than re-resolving the base.

Go beyond that only for the paid tier in the brief reference.

### 3. Write the brief

Five lines is a ceiling; a narrow question usually needs two. Rank lines
as the brief reference sets out, then add numbered single-line options
only when there is a real fork; each option is a different action, never a
restatement of another. Stay read-only, per the contract in
`../../references/situation-sweep.md`, and write per
`../../references/prose-rules.md`.

Before sending, hold each line to `../../references/brief.md` (its
Banned and Confidence sections), plus these:

- One sentence per line, at most about 20 words.
- A narrow question gets only the causal answer, with no branch or
  trunk name inside an option ("commit it", not "commit it on main").
- No absolute paths, and tool state (`gh` signed out) is never a line.
- If the work has wandered from its purpose, offer `/situate:refocus`
  as an option; do not diagnose it here.

## Output

The body, then the options. Nothing else: no title, no framing
sentence, no offer to go deeper.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
⚠ CI is red on PR #12: the type-check job fails on three files this branch added.
feat-brief-mode, 4 commits ahead of main, 2 files uncommitted.
This session rewrote the output contract and has not re-run the gates since.
The ticket asks for a terse mode; the terse mode works, the failing types do not.

1. Fix the three type errors and push
2. Show the failing job output
3. Stash the uncommitted work and check whether the branch alone is green
```
