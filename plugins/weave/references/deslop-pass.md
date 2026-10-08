# Weave deslop pass: single-artifact prose polish

A reusable polish step for `/weave:*` commands that produce a synthesised
prose artifact. Scrubs AI-slop signatures (flagship phrases, hedging,
restated subjects, fragile counts/line numbers, AI footers) from one
markdown file in `<session_dir>` before the user sees the synthesis.

Distinct from `/slop:deslop` (mutates git history via patch series + autosquash)
and `/slop:scan` (mutates working-tree files via forward-going atomic
commits). Weave deslop edits **one** file, **once**, in `<session_dir>`.
The repo guard never triggers - no project-tree changes occur.

## Contents

- Caller contract
- Step 1: Resolve the registry
- Step 2: Tone calibration
- Step 3: Detect
- Step 4: Decide
- Step 5: Rewrite
- Step 6: Report

---

## Caller contract

A prose weave command sets these inputs:

- `ARTIFACT_PATH` - absolute path to the markdown file to clean.
  Always inside `<session_dir>`.
- `SESSION_DIR` - the run's session directory (already exists).
- `BASELINE_SHA` - the `baseline_sha` that the engine's `init` returned,
  used for tone calibration.
- `DESLOP_MODE` - one of `default`, `quiet`, `verbose`. Defaults to
  `default`. Set from `--quiet-deslop` / `--verbose-deslop` flags.

The caller is responsible for honouring `--no-deslop`: if set, do **not**
invoke this reference at all. Skip cleanly with no banner, no sibling
file, no summary block.

Print nothing while the pass runs. Return the summary block (nothing for a
no-op) to the caller, which places it after the result's last section. It never
comes before the hero line, and the reply never mentions this file's
storage or the rollback sibling.

---

## Step 1: Resolve the registry

Read `signatures.yml` from the directory that holds this file. If it is
missing, emit one line and return:

```
Skipping deslop (registry not found)
```

The weave run continues; the synthesis is presented unchanged. Deslop
is non-blocking by design.

Apply the project overlay `.claude/slop.local.yml` if present, with
`replace:` / `append:` / `delete:` lists of signature ids; an id may
appear under only one key. Hash the resolved registry
(sha256) for the audit record.

---

## Step 2: Tone calibration

Read the last 50 commit
messages on the locked baseline, pasting the literal `BASELINE_SHA`
(shell variables do not survive between Bash calls):

```console
$ git log \
    -n 50 \
    --format='%B%n--END--' \
    <baseline-sha>
```

Build a frequency map of Tier C signal phrases. Demote any phrase with
≥3 occurrences from Tier C-active to advisory-only. Trunk's accepted
voice is the authority - never HEAD.

If `BASELINE_SHA` is unset (caller did not lock one), skip calibration
silently. All Tier C signatures stay active.

---

## Step 3: Detect (two-pass hybrid, single-file scope)

### Pass A: Regex (always runs)

Apply registry signatures whose `target` contains `file` or
`message-body`. The artifact is a single long body for this purpose.
Skip signatures with `target: diff` or `target: message-subject`;
those concern commits, not prose.

Tier A and Tier B candidates are produced. Tier C is never auto-applied;
Tier C matches are recorded for the summary only.

### Pass B: Semantic verifier

Skip this pass (`verifier=skipped`, recorded in `deslop-report.md` only) when
the artifact is under 100 words. Otherwise dispatch **one** `Task` sub-agent
(not per-finding, not per-paragraph; the artifact is one file). Sub-agent
contract:

- Allowed tools: `Read`, `Grep`, `Glob`.
- Disallowed: `Bash`, `Write`, `Edit`, `Task`.

The prompt receives the artifact text, the registry filtered to
`kind: semantic`, and the Step 2 tone calibration. The
**anti-slop-on-slop constraint** applies verbatim:

> Do not introduce slop in your suggested replacements. Do not use
> phrases listed in the registry. Do not narrate your changes ("I
> tightened…"). Replacement text should be concrete and shorter than
> the original where possible.

Parse resiliently: strip markdown fences, extract the first balanced
`[ … ]`, parse JSON. On failure, mark `verifier=skipped` and use Pass A
findings only. Never crash the run.

If `Task` is unavailable, set `verifier=skipped` and continue.

---

## Step 4: Decide

For each finding produced by Step 3:

- **Tier A** - auto-apply silently. The summary block discloses the
  category and phrase pair.
- **Tier B** - count the candidates.
  - Exactly 1: auto-apply with phrase-pair disclosure in the summary.
  - 2 or more: present **one** batched `AskUserQuestion` with up to 4
    options ("apply both", "apply [a] only", "apply [b] only", "skip
    both"). Per-finding interrogation is wrong here - the artifact is
    one prose blob, not a series of commits. Without `AskUserQuestion`
    (Codex, headless runs), apply none and list the pairs as advisories
    in the summary.
- **Tier C** - advisory only. List in the summary; never edit.

---

## Step 5: Rewrite (single-file edit)

1. Copy the original to a sibling rollback file with a stable name,
   pasting the literal `ARTIFACT_PATH`:

   ```console
   $ cp <artifact-path> <artifact-path-without-.md>.pre-deslop.md
   ```

   Stable filename - no timestamp suffix - so the user can `diff` with
   one tab-complete.

2. Apply each accepted edit via the `Edit` tool against `ARTIFACT_PATH`.

3. **Sanity guard.** Compute word-count delta:

   - Hard abort: if the desloped artifact removed ≥30% of the original
     word count, restore from the sibling and surface:

     ```
     Held back: deslop would have removed N% of the artifact (>30% threshold).
     ```

     The synthesis is presented unchanged.

   - Suspect-edit: if any **single** finding's edit would have removed
     ≥15% of the original, demote that finding to advisory. The other
     findings still apply. The summary block opens with `(!)` and lists
     the held-back finding under a `!` glyph. The held trim is written
     to `<session_dir>/<artifact name>-deslop-held.md`
     for the user to inspect.

---

## Step 6: Report

Write `<session_dir>/deslop-report.md` with:

- Resolved registry path + sha256
- Tier A applied (count + signature ids)
- Tier B accepted, declined (counts; phrase pairs)
- Tier C advisories (list)
- Word-count delta (before → after)
- Path to `<artifact>.pre-deslop.md` sibling
- Verifier status (`enabled` | `skipped`)

Emit the terminal summary block per `DESLOP_MODE`. It reports edits only: no
scan narration, verifier status, or paths.

### `default` (≤ 8 lines, no banner, no tier letters)

```
Desloped synthesis  ·  -84 words  ·  3 trims, 1 kept-as-is
  • flagship-phrases   "comprehensive solution" → (removed, 2x)
  • restated-subject   trimmed 1 paragraph that paraphrased the question
  • line-numbers       "see line 142" → "see the resolve_trunk helper"
  ~ hedging            kept "may", "likely" (load-bearing, advisory)
```

`•` = applied, `~` = held as advisory. Word delta is the trust anchor.
Phrase pairs are the diff at the only granularity that matters for slop
edits.

### `quiet` (1 line)

```
Desloped synthesis (-84 words, 3 trims)
```

Tier B confirms still happen - quiet does not mean non-consenting.

### `verbose` (≤ 16 lines)

Adds `tier=A|B|C`, `signature_id`, and `confidence` per finding. Adds
Tier C phrases that were demoted by tone calibration with their trunk
counts. Caps at 16 lines; overflow goes to `deslop-report.md` with a
`+N more - see deslop-report.md` line.

### Suspect-edit banner

When the suspect-edit sentinel fires:

```
Desloped synthesis  ·  -84 words  ·  2 trims, 1 held back  (!)
  • flagship-phrases   "comprehensive solution" → (removed, 2x)
  ! restated-subject   would have removed 312 words - held as advisory
Held trims are listed in the report; nothing was removed from the result.
```

### No-op

If Steps 3-5 produced zero applied edits, emit nothing: no line and no block.
Scan details and verifier status stay in `deslop-report.md`.
