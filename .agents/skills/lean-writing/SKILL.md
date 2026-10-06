---
name: lean-writing
description: >-
  Use when commit messages or prose must stay tight: cut filler, padding,
  preamble, AI fluff, and stories of attempts; lead with current results.
allowed-tools: ["Read", "Grep", "Glob"]
metadata:
  source: "plugins/lean/skills/lean-writing/SKILL.md"
---

# Lean writing

Write tight, slop-free prose the first time, so nothing has to be
cleaned up later.

## Moves

- Write per `references/prose-rules.md`: lead with the result,
  state current truth rather than the journey, and cut its listed words
  and patterns.
- Preserve what `references/lean-rubric.md` lists when editing
  existing text: links, citations, anchors, warnings, and comments that
  document an invariant or a "why".
- Read `./AGENTS.md` and `./CLAUDE.md`. When they define a slop rubric
  or a house voice, that governs.

## Comments

Code comments and docstrings answer to
`references/comment-policy.md`: one or two lines, only for what
the code cannot say, rationale in the commit message. To trim comments
that already exist, use the `lean-trim-comments` skill.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
