# lean

Writing discipline and cleanup tools for tight, slop-free prose and code.

`slop` and `pr` clean slop that is already committed. `lean` keeps it
out of the draft in the first place, and tidies working-tree files
without the commit ceremony.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install lean@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add lean@skills
```

The skills below are written with Claude Code's leading slash. Codex uses
the same names without it, so `/lean:…` there is `lean:…`.

## Components

### `lean-writing` (skill)

Loads automatically while you produce or edit prose or code so the
first draft comes out tight: lead with the result, state current truth
over the journey, reuse before creating, and preserve references when
editing. Guidance only — it never edits files.

### `/lean:tighten` (skill)

Point it at files or a pasted draft; it removes slop in place and
prints a diff. It never commits, never pushes, and works fine on a
dirty tree.

## Relationship to `slop` and `pr`

### Reach for `lean` when

You are writing now and want the draft tight, or you want a quick
in-place tidy of working-tree files with a diff to review and no
commits.

### Reach for `/slop:scan` when

You want repo-wide coverage with one reviewable, revertable commit per
finding, on a clean tree.

### Reach for `/pr:deslop` when

The slop is in a branch's commits you are about to ship, and you want
fixup commits with autosquash.

## Prerequisites

None. Both components read the host repo's `AGENTS.md` / `CLAUDE.md` at
runtime to match its voice and rubric when present.
