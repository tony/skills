---
name: business-pr-release
description: >-
  Use when writing the tier-3 one-page announcement from a public case
  study, with denominators attached and a limitations line.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Write", "Grep", "AskUserQuestion"]
metadata:
  argument-hint: "[run directory]"
  source: "plugins/business/skills/pr-release/SKILL.md"
---

# PR Release (tier 3)

Derive a one-page announcement from the public case study, and only
from it. The public case study is the sanitization firewall: this
skill introduces no figure that is not already in it and re-derives
nothing from the interim package.

Read `references/interim-format.md` first, only § Where runs live,
§ Locating an existing run, and § Rendering a report; there is no
completeness gate here. The scanner reads the run's `README.md` only for
the names the sweep denies. Defer these until the firewall (the public
case study) is located:

- `references/provenance.md`
- `references/audiences.md`: the tier-3 contract and the
  firewall sweep.

User arguments: $ARGUMENTS

## Procedure

### 1. Locate the run

The `$ARGUMENTS` path if given, else per `interim-format.md` §
Locating an existing run; for a named workflow, the first line of
`runs --workflow <slug>`.

### 2. Locate and verify the firewall

Check for `<run>/reports/case-study-public.md`. If it is missing,
ask via `ask-user-choice` whether to write it now (read
the `business-case-study-public` skill and follow it) or stop; never draft
the release straight from the interim package. Without a question
tool, halt with the second stopped-run example in `interim-format.md`.
If present, run `references/business.py fresh <run>` (absolute path):
a `case-study-public.md` line means the case study is unstamped or its
run inputs changed, so regenerate it with
the `business-case-study-public` skill before going on. Then run the firewall
sweep from `audiences.md`; a sweep failure routes back to the public
case study, never into hand-patching here.

### 3. Compose one page

From the public case study only:

1. Headline result: the case study's headline, with its tag
   and range.
2. Supporting numbers: two or three, each with its denominator
   and window length, exactly as they appear in the case study.
3. Quote placeholder: clearly marked as a placeholder, with
   attribution left blank for the user to fill.
4. Limitations one-liner: a single candid sentence distilled
   from the case study's limitations section.

Write `<run>/reports/pr-release.md` per
`references/prose-rules.md`, with every figure copied verbatim
from the public case study; if a wanted figure is not there, extend the
case study first instead of reaching into the run's measurements. Then:

1. Scan the saved release with `scan --run <run> <release>` and rewrite
   until it prints `clean` (`audiences.md` § Tier-3 final checklist).
2. Run `trace <release> --against <run>/reports/case-study-public.md`;
   it lists each number the case study lacks. Rewrite until it prints
   `ok`.
3. Run `stamp` (`interim-format.md` § Rendering a report, step 5).

## Output

Hero success form: `✓ PR release: <headline>`; a stopped run follows
`interim-format.md` § Rendering a report. Sections:

1. `## Run`: the task category and rounded window, per `audiences.md`
   tier 3, never the run name.
2. `## Firewall`: the public case study used, and that `trace` found
   every figure in it.
3. `## Report`: where it was written and the headline.

Panel options: revise the headline, regenerate after updating the
case study (read the `business-case-study-public` skill and follow it), or stop.
Panel rules as in `interim-format.md` § Finished run.
Scan the reply as `audiences.md` § Tier-3 final checklist describes
before sending it.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
