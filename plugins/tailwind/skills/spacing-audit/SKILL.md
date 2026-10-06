---
name: spacing-audit
description: "Use when Tailwind UI spacing, alignment, gaps, margins, padding, or toolbar and navbar rhythm looks inconsistent."
user-invocable: true
argument-hint: <file-or-directory-to-audit>
---

# Tailwind spacing audit

Detect and fix inconsistent spacing in Tailwind CSS layouts. Most spacing
bugs come from fragmented spacing authority: gap, margin, padding, and
fixed widths all control the space between the same visual peers. Each
pair of adjacent items gets exactly one mechanism.

Use `$ARGUMENTS` as the target scope. If it is empty, ask which
component or file to audit.

## Workflow

### Step 0: Detect framework

Find the template files in scope and the class attribute each uses:

- `*.tsx`, `*.jsx`: `className=`
- `*.vue`: `class=`, `:class=`
- `*.svelte`, `*.astro`, `*.html`, `*.erb`, `*.blade.php`: `class=`

Search every framework present. The catalog's commands match both
`class=` and `className=`.

### Step 1: Structural audit

Read `references/patterns.md`. Scan the component and draw a spacing
map: every spacing mechanism acting on the group the user cares about.

```
[LinkedIn] --gap-1--> [Wrench] --gap-1--> [Babylon.js] --me-1+flex--> [Theme(me-2)]
            ^ parent gap                   ^ margin leak    ^ separate container
```

Call out how many mechanisms act between visual peers, which items sit
in different containers yet read as one group, and any fixed `w-*` on
an item whose siblings size to content.

### Step 2: Classify

Match each finding to a pattern in `references/patterns.md`. Run that
pattern's detect command for codebase-wide scope. Each match needs a
read in context before it counts.

### Step 3: Refactor

Apply in this order. Preserve existing breakpoints, and change only
spacing classes.

1. **Merge fragmented containers.** Put one visual group in one flex
   container with one `gap-*`. Remove the outer `me-*` and `ms-*` that
   compensated for the split.
2. **Pick one authority per relationship.** `gap-*` on the parent for
   uniform spacing; margin on a child only for a deliberate exception;
   padding only for space inside an item.
3. **Standardize peer envelopes.** Peer buttons, links, and toggles
   share one height class and one horizontal padding, and no `w-*`
   unless every peer has the same one.
4. **Flatten single-child wrappers.** Move the alignment classes onto
   the child.
5. **Keep intentional breaks.** A divider between nav groups is
   deliberate. Ask before normalizing a difference that may be design.

### Step 4: Validate

Redraw the spacing map and confirm:

- [ ] Every adjacent pair has exactly one spacing authority
- [ ] Each visual group shares one parent container
- [ ] Peer interactive elements share envelope classes
- [ ] No `w-*` on content-sized items, unless all peers match
- [ ] Hit targets are consistent across peers

## Output

Write it per `../../references/prose-rules.md`. Present, in order:

1. **Spacing map**
2. **Anti-patterns found**: numbered, with the pattern name and the
   elements involved
3. **Proposed refactor**: a focused diff or before/after
4. **Validation checklist**: Step 4 filled in

For a straightforward fix, collapse this to a short explanation and the
code.
