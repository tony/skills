# Slop Taxonomy

`signatures.yml` owns detection: each signature's `pattern`, `kind`,
`target`, `action`, and `fp-guard`. This file explains what each tier
means and how to judge branch-internal narrative.

Slop is a workflow label, not proof the text is wrong. Tier decides what
a run may change; confidence and `fp-guard` decide whether a finding
reaches the proposal.

---

## Tiers

**Tier A: deterministic, near-zero false positives.** Exact AI-tool
footers, emoji in commit subjects, markdown syntax opening a subject,
and net-new `TODO: revisit` noise. In an apply mode these change with no
per-finding confirmation; they are the only findings that do. The
emoji rule flags pictographic emoji only, not status glyphs such as
check marks, and is overridable for gitmoji projects.

**Tier B: high-confidence, edge cases remain.** Brittle references (line
numbers, counts, bare SHAs), restated subjects, bullets
that mirror the diff, dead code added "for future use", log debris,
AI co-author trailers, hardcoded test runners and user-home paths, and
most `branch-internal.*` signatures. The user confirms each one in an
apply mode; in audit mode each becomes a patch for review.

**Tier C: advisory only, never applied.** Flagship phrases, oversized
docstrings, defensive wrapping, multi-topic commits, "as of <date>"
markers, and intermediate-state narrative. Tone calibration demotes a
phrase the project's own trunk history already uses to summary-only.

---

## Branch-internal narrative

The `branch-internal.*` family flags within-branch tactical narrative
that leaked into a shipped artifact: renames of unshipped symbols,
intermediate states, and `### Fixes` entries for bugs no release had.

**Published-Release Test.** Flag the text only when no user of the most
recently published release ever experienced the old name, behavior, or
bug. Keep deprecations and `### Fixes` entries for things that shipped.
Judge by whether the symbol or behavior appears in `git log` before the
branch point.

| Flag | Keep |
|---|---|
| `Renamed from test_foo_old` in an unmerged-branch test docstring | `Deprecated: OldClass was renamed to NewClass in v2.0` (`OldClass` shipped) |
| `### Fixes` entry for a regression the branch itself introduced | `### Fixes` entry for a bug present in the most recent release |
| `no longer raises spuriously on resize-grow` (the raise never shipped) | `no longer hangs on large datasets` (the hang shipped in v0.4 and earlier) |
