---
name: review-pr
description: "Use when reviewing an existing PR description for structure, proportionality, brittle details, and branch-internal narrative, without editing it."
allowed-tools: ["Bash", "Read"]
argument-hint: "[PR number or URL, e.g. '#42' or 'https://github.com/...']"
user-invocable: true
disable-model-invocation: true
---

# Review PR Description

Evaluate an existing PR description against the section patterns
`/pr` writes and suggest concrete improvements. Write the report per
`../../references/prose-rules.md`.

Target PR: $ARGUMENTS

## Procedure

### 1. Fetch the PR

Use the PR number (`#42`, `42`) or URL in `$ARGUMENTS`; when it is
empty, use the current branch's PR (omit `<number>`):

```bash
gh pr view <number> --json number,title,body,url
```

### 2. Fetch the diff context

```bash
gh pr diff <number>
```

Judge the change's magnitude (small fix, medium feature, large
overhaul) from the diff; the description must be **proportional** to it.
When the user's message names a PR template, read it and use its
sections as the structural baseline. Use it silently: this skill reports
findings and never raises template questions.

### 3. Evaluate against the quality patterns

Check each dimension that applies; a one-line typo fix needs no Design
decisions section.

| Dimension | What to check |
|---|---|
| **Structure** | `## Summary`, `## Changes`, `## Test plan` headings where the change size warrants them. |
| **Proportionality** | Detail matches the diff: a small fix does not carry 20 bullets, and a large feature is not one sentence. |
| **Bold impact labels** | Summary bullets open with a **bold verb** (Fix, Add, Remove, Replace, Migrate). |
| **Tables** | Comparison-heavy sections (renames, parameter maps, file inventories, environment matrices) use tables, not prose. |
| **Code blocks** | One command per block, no comments inside, explanation outside. |
| **Test plan** | A `- [x]` or `- [ ]` checklist whose items say what is validated, not only the command. |
| **Design decisions** | Non-trivial changes explain their trade-offs. |
| **Verification** | Copyable `rg` or `grep` commands prove the change is complete. |
| **Negative assertions** | Removal and migration PRs include "verify zero matches for X" items. |
| **Cross-references** | Companion PRs, related issues, and tracking links, where relevant. |
| **Before/After** | Behavioral changes show both states in labeled code blocks. |
| **No brittle details** | No test counts, SHAs, line numbers, or file or line-changed counts; the diff already shows them. |
| **No branch-internal narrative** | No rename history, "no longer X" or "previously Y" phrasing, or `### Fixes` framing for behavior that never appeared in a published release. Keep such text only when a user of the latest release experienced the old name, behavior, or bug. |
| **Whole-branch perspective** | Describes the net shipped result, not the branch's commit-by-commit evolution. Suggest a rewrite when it narrates. |

### 4. Report

**What the description does well:** specific strengths, so the author
keeps them.

**Suggested improvements:** each with a **concrete markdown snippet**,
never vague advice like "add more detail". Draft a missing section the
diff warrants as ready-to-paste text. Show the improved version of a
weak one. Flag brittle details as concrete edits.

**Overall assessment:** one sentence: adequate, good, or complete. For
adequate or good, name the single highest-impact improvement.

## Rules

- **Never** modify the PR; only report findings.
- **Never** run destructive git or gh commands.
