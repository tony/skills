# Render and save a goal

Write under [prose-rules.md](./prose-rules.md). The complete printed payload and
saved goal must match exactly; links never replace the printed goal.

## Contents

- Select delivery and budget
- Prepare helper input
- Save immutable revisions
- Verify the handoff

## Select delivery and budget

Select the destination from the request or explicitly selected profile. The
assistant drafting in Codex does not impose Claude's limit. Claude defaults to
**3,800 characters for the whole `/goal ` payload**, including prefix, locators,
spaces, and all newlines. The host ceiling is 4,000; generic “under 4k” retains
the drafting reserve. Spend it only on explicit request; strict less-than-4,000
permits at most 3,999. Honor tighter limits and never pad spare capacity.

Codex receives the full objective unless an explicit user or delivery-interface
limit applies. Inspect the selected channel: full-text TUI and tool/API limits
may differ; a printed `/goal` in non-interactive output is still a handoff.
Verify installed help or primary host documentation before applying a surface
cap. Never activate a goal to test limits. Count the condition and whole
payload after substitutions. For Claude, both Unicode code points and UTF-16
units must fit the selected whole-payload limit. Report whole-payload counts
outside the payload.

If the full contract cannot fit, use a complete **goal specification** with
requirements, tasks, evidence rules, and provenance. The compact goal retains
outcome, exclusions, authority, hard acceptance, and companion reference. It
must require a visible acceptance summary with requirement verdicts, evidence,
exclusions, and companion identity/digest. Claude's completion evaluator reads
the conversation, so file-only evidence is insufficient for that evaluator.
If standalone brevity conflicts with obligations, print the fullest reviewable
candidate and name the conflict; never truncate requirements.

## Prepare helper input

`<planner>` is `./planner.py`, resolved from this reference's directory
to an absolute path written literally in each command. Use Python 3.9 or newer.
Skills declare their own relative helper path.

Generic output is stdout-only; save only when requested or selected by an
approved profile. Explicit stdout-only wins and forbids all file writes,
including temporary inputs. Pass JSON on stdin; authorized saving may use an
owned disposable request file. Set `host` (`claude` or `codex`), `topic`
(lowercase hyphenated slug), and `body` (without `/goal `). Optional fields:
`specification` (complete Markdown), `documents_root`, `date` (`YYYY-MM-DD`),
`max_chars`, `spend_reserve`, `strict_less_than_4000`, and `predecessors`.

`predecessors` contains same-topic saved goal paths in dated `goals/` folders.
Other-topic/legacy originals remain sourced contract inputs; importing does not
migrate layouts or infer counter identity. Report unresolved lineage rather
than resetting a series. Use the selected machine binding for `documents_root`;
native and mounted Documents roots are distinct.

With `specification`, include exactly one `{{GOAL_SPEC}}` token in `body`.
The helper inserts the absolute locator and SHA-256 digest before counting;
do not invent paths or substitute unverified digests.

Render without writes, substituting the draft JSON:

```console
$ python3 <planner> render \
    --input - <<'JSON'
{"host":"claude","topic":"docs-fix","body":"Correct the named documentation example and verify it against the documented interface. Preserve the existing scope and release hold."}
JSON
```

For selected saving:

```console
$ python3 <planner> render \
    --input <request.json> \
    --save
```

Read the complete result: `payload`, `measurements`, `ready`, paths, revision,
reuse state, and errors. Present it under [output.md](./output.md). Stdout-only
with a required unsaved companion is incomplete and must print that full
specification too.

## Save immutable revisions

Use local calendar date and the selected Documents root (default
`~/Documents`): `YYYY-MM-DD/goals/<topic>-NNN.md`, plus
`YYYY-MM-DD/goal-specs/<topic>-NNN.md` when needed. Goal files contain only the
payload; specifications may contain metadata. Short complete goals need no
empty companion.

Continue each topic across dates from `001`, with at least three digits
(`999`, then `1000`). Inspect only dated goal/specification folders and imported
same-topic predecessors; allocate above the known maximum, never fill gaps or
count research captures/copied fixtures. Report missing/conflicting lineage.

Preserve predecessor provenance and pair goal/specification revisions. Changed
specifications need new pairs; changed renderings may reuse identical
specification content. Unchanged reprints reuse only the latest completed
matching authored content in the selected root. Imports from another root need
a new revision with the resolved locator. Never overwrite existing revisions.

The helper uses exclusive creation and retries local collisions at a new
number, publishes the specification before the goal, verifies the completed
pair, and detects interrupted writes. Reservation records must not turn partial
writes into complete revisions or be reclaimed by age alone. Reconcile cross-machine
conflicts explicitly; a local counter is not distributed coordination.

## Verify the handoff

Verify required files, identities, and digests. The copied payload must resolve
its companion from an unrelated working directory; bare `../goal-specs/...`
without a base is insufficient. Transfer both dated folders, resolve the new
binding, and create a new revision if the payload changes.

Read back saved bytes and compare exactly with the printed payload. On failure,
print the returned payload (or authored draft if none), the complete required
specification, and the concrete error as an unsaved/incomplete handoff. After
a save failure, do not bypass exclusive creation with private helper calls
or manual writes.
Missing, changed, or unavailable required companions mean incomplete. Mechanical
checks do not establish semantic coverage or independent review.
