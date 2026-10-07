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

1. The current branch (`git branch --show-current`; empty means
   detached HEAD).
2. Trunk (`git symbolic-ref --short refs/remotes/origin/HEAD`, falling
   back to whichever of `origin/main` or `origin/master` exists), then ahead/behind counts
   (`git rev-list --left-right --count <trunk>...HEAD`).
3. Uncommitted work (`git status --short`).
4. Commit subjects since trunk
   (`git log --no-merges --format='%h %s' <trunk>..HEAD`).

A failed command means that layer is unavailable; say so inside an
existing line. Measuring from trunk is approximate on a branch stacked
over another branch, because the range carries the parent's commits;
say so rather than re-resolving the base.

If `git rev-parse --show-toplevel` is `$HOME` or contains it, or `HEAD`
has no commits, say that in one line and list no files.

Go beyond that only for the paid tier in the brief reference.

### 3. Write the brief

Five lines is a ceiling; a narrow question usually needs two. Rank lines
as the brief reference sets out, then add numbered single-line options
only when there is a real fork; each option is a different action, never a
restatement of another. Stay read-only, per the contract in
`../../references/situation-sweep.md`, and write per
`../../references/prose-rules.md`.

Before sending, check each line:

- One sentence per line, at most about 20 words. Cut a second sentence
  or a stacked "so", "because", or "which" clause.
- A narrow question gets only the causal answer. No line on branch
  position, trunk, or repository location unless the answer needs it.
- No headings, bullets, bold, preamble, closing summary, or offer to go
  deeper. No `AskUserQuestion`; options are plain numbered lines.
- No absolute paths, and no line true in every repository ("nothing has
  been committed because no one ran `git commit`").
- Never spend a line saying a layer was checked and was quiet. At most
  one hedged inference.
- If the work has wandered from its purpose, say so in one line and
  offer `/situate:refocus` as an option; do not diagnose it here.

## Output

The body, then the options. Nothing else: no title, no framing
sentence, no offer to go deeper.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
⚠ CI is red on PR #12: the type-check job fails on three files this branch added.
feat-brief-mode, 4 commits ahead of main, 2 files uncommitted.
This session rewrote the output contract and has not re-run the gates since.
The ticket asks for a terse mode; the terse mode works, the failing types do not.

1. Fix the three type errors and push
2. Show the failing job output
3. Stash the uncommitted work and check whether the branch alone is green
```
