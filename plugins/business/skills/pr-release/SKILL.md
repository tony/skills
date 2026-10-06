---
name: pr-release
description: Write the tier-3 one-page announcement — figures drawn only from the public case study, denominators attached, limitations one-liner included
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
argument-hint: "[run directory]"
user-invocable: true
disable-model-invocation: true
---

# PR Release (tier 3)

Derive a one-page announcement from the public case study, and only
from it. The public case study is the sanitization firewall: this
skill introduces no figure that is not already in it and re-derives
nothing from the interim package.

Read `../../references/interim-format.md` first for the run location
and output frame; there is no completeness gate here. Defer these
until the firewall (the public case study) is located:

- `../../references/provenance.md`
- `../../references/audiences.md`: the tier-3 contract and the
  firewall sweep.

User arguments: $ARGUMENTS

## Procedure

### 1. Locate the run

The `$ARGUMENTS` path if given, else per `interim-format.md` §
Locating an existing run.

### 2. Locate and verify the firewall

Check for `<run>/reports/case-study-public.md`. If it is missing,
ask via `AskUserQuestion` whether to run
`/business:case-study-public` now or stop; never draft the release
straight from the interim package. Without a question tool, halt
with `⚠ Refused: no public case study for this run` and tell the user
to run `/business:case-study-public`. If present, run the firewall
sweep from `audiences.md`; a sweep failure routes back to
`/business:case-study-public`, never into hand-patching here.

### 3. Compose one page

From the public case study only:

1. **Headline result**: the case study's headline, with its tag
   and range.
2. **Supporting numbers**: two or three, each with its denominator
   and window length, exactly as they appear in the case study.
3. **Quote placeholder**: clearly marked as a placeholder, with
   attribution left blank for the user to fill.
4. **Limitations one-liner**: a single candid sentence distilled
   from the case study's limitations section.

Write `<run>/reports/pr-release.md`. Every figure must trace to the
public case study verbatim or by stated rounding; if a wanted figure
is not there, extend the case study first instead of reaching into
the run.

Write it per `../../references/prose-rules.md`.

## Output

Hero success form: `✓ PR release: <headline>`; a stopped run follows
`interim-format.md` § Rendering a report. Sections:

1. `## Run`: the run chosen.
2. `## Firewall`: the public case study used, and confirmation that
   every figure traces to it.
3. `## Report`: where it was written and the headline.

Panel options: revise the headline, regenerate after updating the
case study, or stop. Skip the panel in plan mode or when running
non-interactively.
