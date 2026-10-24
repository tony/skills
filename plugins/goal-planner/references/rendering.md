# Render and save a goal

Apply [prose-rules.md](prose-rules.md) to goal text and status. The saved goal
and the complete user-facing payload must be identical. A path-only response
fails the output contract even when the file is correct.

## Contents

- Select host and budget
- Prepare the helper input
- Save immutable revisions
- Verify the handoff

## Select host and budget

Default Claude output to at most **3,800 characters for the whole `/goal `
payload**, including prefix, locators, spaces, newlines, and any trailing newline.
The 4,000-character host ceiling is distinct from this drafting budget. A
generic “under 4k” request keeps the reserve. Spend it only on explicit request;
a strict less-than-4,000 ceiling permits at most 3,999. Honor tighter limits.

Count the final condition and whole payload after all substitutions. Until
the installed host's counting metric is verified, require both Unicode code
points and UTF-16 units to fit. Report the measurements and remaining host
capacity outside the copy block. Never pad the spare capacity.

Codex receives the full objective by default. Do not impose Claude's drafting
ceiling on it. Inspect the chosen delivery capability: a full-text TUI and a
bounded tool/API can differ. For a bounded channel use its explicit limit and
a verified portable companion. Never activate a native goal to test limits.

If the complete contract cannot fit, save a **goal specification** containing
all requirements, detailed tasks, evidence rules, and provenance. Preserve the
outcome, exclusions, authority, hard acceptance conditions, and required
companion reference in the compact goal. Require a visible acceptance summary
with requirement-level verdicts, evidence, exclusions, and companion identity
and digest; a bare claim that the file is complete is insufficient.

If standalone brevity conflicts with mandatory obligations, print the fullest
reviewable candidate and name the conflict. Do not truncate requirements.

## Prepare the helper input

`<planner>` is `../scripts/planner.py`, resolved from this reference's directory
to an absolute path and written literally in each command. Skills declare
their own relative path to this helper. Use the available Python 3.9-or-newer
interpreter.

Pass request JSON on stdin from the selected options and complete draft.
Stdout-only must not create temporary input files. With authorized saving,
an owned temporary request file is also acceptable; it is disposable rendering
input, not a second maintained contract. Set
`host` to `claude` or `codex`, `topic` to a lowercase hyphenated slug, and `body`
to the goal text without the `/goal ` prefix. Optional fields are
`specification` (complete Markdown), `documents_root`, `date` (`YYYY-MM-DD`),
`max_chars`, `spend_reserve`, `strict_less_than_4000`, and `predecessors`
(an array of same-topic saved goal paths in the dated `goals/` layout).
Other-topic or legacy originals remain sourced contract inputs, not helper
counter inputs. Import does not migrate older layouts or infer their revision
identity. Report any unresolved lineage and do not silently restart a series.

When `specification` is supplied, put exactly one `{{GOAL_SPEC}}` token in
`body`. The helper inserts its concrete absolute locator and SHA-256 digest
before counting. Do not hand-substitute an unverified digest or invent a path.
Use the resolved machine binding for `documents_root`; native and mounted
Documents folders are distinct.

Render without writing files, substituting the actual draft JSON:

```console
$ python3 <planner> render \
    --input - <<'JSON'
{"host":"claude","topic":"docs-fix","body":"DRAFT_NOT_STARTED. Correct the named documentation example and verify it against the documented interface. Preserve the existing scope and release hold."}
JSON
```

Save when the current request or approved profile selects it:

```console
$ python3 <planner> render \
    --input <request.json> \
    --save
```

Read the complete JSON result, including `payload`, `measurements`, `ready`, paths,
revision, reuse state, and errors. Print `payload` verbatim as specified in
[output.md](output.md); do not summarize or reconstruct it. Stdout-only still
prints the full contract. A compact draft needing an unsaved companion is not
ready for activation; print the complete specification as well in that case.

## Save immutable revisions

Use the local calendar date and selected Documents root, defaulting to
`~/Documents`. Save `YYYY-MM-DD/goals/<topic>-NNN.md` and, when needed,
`YYYY-MM-DD/goal-specs/<topic>-NNN.md`. The goal file has only the payload;
the specification may contain contract metadata. A short complete goal needs
no empty companion.

Continue each topic's sequence across dates, starting at `001`, using at least
three digits (`999` then `1000`). Inspect only dated `goals/` and `goal-specs/`
folders and explicitly imported same-topic predecessors in that layout.
Allocate above the known maximum;
do not fill gaps or count research captures and copied fixtures. Report missing
or conflicting imported lineage rather than silently resetting it.

Keep predecessor provenance in the contract. Pair both files at the same
revision. Changed specifications require a new pair; a changed rendering may
use an identical specification snapshot. Unchanged reprints reuse the existing
revision and print it again. Reuse only the latest completed matching authored
content in the selected root; an imported draft at another root requires a
new revision with the resolved locator. Exclusive creation prevents overwrites; local
collisions retry at a new number. Finalize and verify the specification before
publishing its goal. Detect interrupted pairs rather than treating them as
complete. Reservation records prevent a partial write from claiming a complete
revision; never reclaim one based on age alone. Cross-machine conflicting copies
require reconciliation; a local
counter is not distributed coordination.

## Verify the handoff

Verify required files, identity, and digest before reporting readiness. The
copied payload must resolve its companion from an unrelated working directory;
a bare `../goal-specs/...` needs an explicit base and is insufficient alone.
Keep both dated folders together when transferring, resolve the new binding,
and create a new revision when the rendered payload changes.

Read back the saved goal and compare it exactly with the printed `payload`.
If saving fails, print the draft and the concrete error. Mark a missing,
changed, or unavailable required companion incomplete. Never claim the helper's
mechanical checks established semantic coverage or independent review.
