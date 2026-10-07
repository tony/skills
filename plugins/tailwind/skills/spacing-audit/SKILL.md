---
name: spacing-audit
description: "Use when Tailwind spacing looks uneven or too wide: gap, space-x, margin, or padding mixed on navbars, toolbars, and flex rows."
user-invocable: true
argument-hint: <file-or-directory-to-audit>
---

# Tailwind spacing audit

Detect and fix inconsistent spacing in Tailwind CSS layouts. Most spacing
bugs come from fragmented spacing authority: gap, margin, padding, and
fixed widths all control the space between the same visual peers. Each
pair of adjacent items gets exactly one mechanism.

Use `$ARGUMENTS` as the target scope. If it is empty and the user pasted
markup, audit the paste. Otherwise ask which component or file to audit;
without a question tool, stop with the halted result below.

Run scripts from the project root so targets stay relative to the
project. Resolve `../../scripts/detect.py` against this skill's directory,
print the absolute path once, and write it literally in each command,
since shell variables do not persist between Bash calls.

## Workflow

### Step 0: Detect framework and Tailwind version

Find the template files in scope and the class attribute each uses:

- `*.tsx`, `*.jsx`: `className=`
- `*.vue`: `class=`, `:class=`
- `*.svelte`, `*.astro`, `*.html`, `*.erb`, `*.blade.php`: `class=`

The detect commands in `references/patterns.md` run
`../../scripts/detect.py` (needs `python3`) and name an `rg` fallback for
when it cannot run. If neither runs, read the files in scope.

Read the installed Tailwind version: the `tailwindcss` entry in the
lockfile (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`,
`bun.lock`), else the range in `package.json`. As a cross-check, an
`@import "tailwindcss"` line in a stylesheet means v4, and
`@tailwind base` or a `tailwind.config.*` file means v3. If the version
cannot be found, say so in the result and keep Pattern 7 advice
version-neutral.

### Step 1: Structural audit

Read the Detect command limits and Decision tree sections of
`references/patterns.md`, then only the pattern sections the findings
match. Scan the component and draw a spacing
map in the list form shown under Output: every spacing mechanism acting
on the group the user cares about.

Call out how many mechanisms act between visual peers, which items sit
in different containers yet read as one group, and any fixed `w-*` on
an item whose siblings size to content.

### Step 2: Classify

Match each finding to a pattern in `references/patterns.md`. Run that
pattern's detect command for codebase-wide scope. Each match needs a
read in context before it counts. A command that returns nothing for a
file the user named is not a clean bill: read the file.

### Step 3: Refactor

Propose the changes as a diff or before/after; edit files only when the
user asked to fix or apply them. For a pasted snippet, reply with the
code. Preserve existing breakpoints, and change only spacing and sizing
classes.
Work in this order:

1. Merge fragmented containers. Put one visual group in one flex
   container with one `gap-*`. Remove the outer `me-*` and `ms-*` that
   compensated for the split.
2. Pick one authority per relationship. `gap-*` on the parent for
   uniform spacing; margin on a child only for a deliberate exception;
   padding only for space inside an item.
3. Standardize peer envelopes. Peer buttons, links, and toggles
   share one height class and one horizontal padding, and no `w-*`
   unless every peer has the same one.
4. Flatten single-child wrappers. Move the alignment classes onto
   the child.
5. Keep intentional breaks. A divider between nav groups is
   deliberate. Ask before normalizing a difference that may be design.
   Without a question tool, or when the user said not to ask ("no
   questions"), keep the break, ask nothing, and report it as a kept
   difference after the findings, never as a finding, with no guessed
   rationale. When you keep separate containers, name the evidence that
   they are separate groups (a divider, different roles, a
   `justify-between`), or merge them. Never end a reply with a question
to the user when they said not to ask.

### Step 4: Validate

Redraw the spacing map and confirm:

- [ ] Every adjacent pair has exactly one spacing authority
- [ ] Each visual group shares one parent container
- [ ] Peer interactive elements share envelope classes
- [ ] No `w-*` on content-sized items, unless all peers match
- [ ] Hit targets are consistent across peers

Leave a box `[ ]` and give the reason for any unmet item; never tick a
box and then argue against it.

## Output

Write it per `../../references/prose-rules.md`. Present these sections
in order, with these headings:

1. Spacing map
2. Anti-patterns found: one plain sentence per finding, naming the
   pattern and the elements involved, with no bold lead-ins. For a file or
   directory audit, name each finding's `path:line`. Put each kept
   difference in one plain sentence after the last finding, not among them
3. Proposed refactor: a focused diff or before/after
4. Validation checklist: Step 4 filled in

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

````text
## Spacing map

nav (p-4, no gap)
- Docs, gap-2, Pricing
- ms-3 on the second group
- Sign in (px-2 h-8), nothing, Sign up (h-8)

## Anti-patterns found

- The `ms-3` on the second group (`src/Nav.tsx:11`) sets the space between groups with a margin (Pattern 2).
- "Sign in" has `px-2` and "Sign up" has none, so the buttons differ in width (Pattern 3).

## Proposed refactor

```tsx
<nav className="flex items-center gap-3 p-4">
  ...
</nav>
```

## Validation checklist

- [x] Every adjacent pair has one spacing authority.
- [x] Peer buttons share `h-8 px-2`.
````

Use the full shape when auditing a file or directory. For a pasted
snippet with one finding, collapse it to a short explanation and the
code, with no bold anywhere and no counted lead-in ("for three
reasons:"). State each visible change once. Do not restate that
distances stay the same.

Halted or empty runs give one result sentence, then what the user does:

- No target given: "Nothing audited: no file or directory was given."
  Pass a file or directory.
- No Tailwind class attributes in scope: "No Tailwind classes found in
  `<scope>`." Check the path, or point at the template files.
- Issues found but all kept as deliberate: "No spacing changes made in
  `<scope>`." Stop after one sentence naming the kept break and the one change
  that would alter it. Do not reprint unchanged code or recap.
- No issues found: "No spacing issues found in `<scope>`." Name the files
  you read, since the detect commands can miss dynamic classes.
