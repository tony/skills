# Weave ensemble techniques: cascade gate and residual re-attack

Two cost/quality protocols for `ask` and `review`:

- **Cascade gate** (`--cascade`): a Maintainer-only first pass that fans out only
  when a confidence trigger fires.
- **Residual re-attack**: governs multi-pass (N >= 2).

The skill reads this file only when `--cascade` is set or a pass N >= 2 begins.

Throughout, `M` = the number of lanes that produced an output this
pass. When `M` = 1 (single-participant fallback or cascade early-exit)
the residual procedure is skipped; it needs multiple lanes to mean anything.

## Contents

- Technique 1: Cascade gate
- Technique 2: Residual re-attack

---

## Technique 1: Cascade gate (`--cascade`)

Every weave invocation normally pays full-ensemble price up front. With
`--cascade`, a cheap Maintainer-only pass runs first, self-verifies, and
fans out to the Skeptic and Builder lanes only when a confidence trigger
fires or the user escalates. All lanes use the session's selected
`worker_backend`.

### Caller contract

The caller runs the gate after session-directory initialization and
context-packet write, **before** launching the Skeptic or Builder lane.
Inputs: `SESSION_DIR`, `worker_backend`, the command's Phase 3
Maintainer prompt (verbatim, role preamble included), and the command's
Verify Claims procedure.

### Step 1: Cheap pass

Run the command's Maintainer lane exactly as its Phase 3 specifies,
using the selected worker backend, prompt, and context packet. Capture
the output as `maintainer.md` in subagent mode or `claude.md` in
model-CLI mode. Do not launch the Skeptic or Builder yet. Running the
lane verbatim makes the output reusable unchanged if the gate
escalates.

### Step 2: Confidence gate

Run the command's Verify Claims procedure (synthesis Step 1) against
the cheap-pass output itself - self-verification against the codebase,
classifying each claim `verified` / `plausible-unverified` / `false`.
Then evaluate these triggers in order. **Escalate if ANY fires**; each
is a yes/no check an LLM can execute without judgment about the gate
itself:

1. **Contradicted claim** - any claim classified `false` during
   self-verification.
2. **Unverified load-bearing claim** - any claim classified
   `plausible-unverified` whose removal would change the answer's
   conclusion or a finding's severity. Test: delete the claim mentally;
   if the conclusion or severity must change, it is load-bearing.
3. **Ambiguous request** - the question or review focus admits two or
   more materially different readings, and the output committed to one
   without codebase evidence deciding between them. Record each reading
   in the ledger.
4. **Coverage gap** - an explicit part of the request (a sub-question,
   a named file or focus area) has no corresponding content in the
   output.
5. **Judgment call** - the conclusion rests on preference or design
   trade-off rather than facts checkable in the repo (e.g. "which
   approach is better"). Single-lane judgment has no error correction,
   so it always warrants the ensemble. For `review`: any finding
   reported at **Critical** severity fires this trigger - Criticals
   always get ensemble confirmation before reaching the user.

If no trigger fires, the verdict is **early-exit**.

### Step 3: Ledger and event

Write `<session_dir>/cascade.md`: the verdict (`early-exit` or
`escalate`), then one line per trigger - fired or not, with the
specific claim/reading/gap as evidence when fired. Record the event
through the engine, which stamps it and appends atomically (list the fired
triggers in `triggers_fired`):

```console
$ python3 <engine> update \
    --session "<session_dir>" \
    --event cascade_gate \
    --event-json '{"verdict": "early-exit", "triggers_fired": []}'
```

### Early-exit path

Early-exit ends the run: any remaining configured passes are not run,
making this pass the final pass. Skip the remaining lanes, blind
judging, and rubric scoring (nothing to compare). Keep the command's
Critic step - it is the only remaining error correction - and the
deslop pass. Present with `CASCADE_STATE` = `early-exit`:
the hero identifies the Maintainer lane in subagent mode or the Claude
lane in model-CLI mode, and the next-step panel gains **Escalate to full
ensemble** as the first option. If the user picks it, continue below as
if the gate had escalated. Record participants as `["maintainer"]` in
subagent mode or `["claude"]` in model-CLI mode until
escalation happens.

### Escalation path

Launch the Skeptic and Builder per the command's Phase 3 through the
same `worker_backend`, reusing the cheap-pass output as the Maintainer
lane. Do not re-run the Maintainer or switch worker backends. Include
the fired triggers verbatim in the two new prompts under a heading
`Known weak points in one prior attempt`; do not attribute the prior
attempt, which would break blind judging. The command then proceeds
normally: blind labels, synthesis, and passes 2..N if configured.

### Headless

Without `ask-user-choice`, the gate decides alone: no
early-exit panel, no escalation prompt. The verdict line is emitted in
the output.

---

## Technique 2: Residual re-attack (multi-pass, N ≥ 2)

Pass N+1 must not re-run the whole task with the prior synthesis as
context. It re-attacks **only the residuals** - the regions where pass
N could not reach an evidence-backed, agreed answer.

### Residual sources

After completing pass N synthesis in `ask` or `review`, extract
residuals from exactly four sources:

1. **Unresolved conflicts** - adjudication Step 3 items where codebase
   evidence could not pick a side.
2. **Failed verification** - claims classified `false` (needs a
   correct replacement) or load-bearing `plausible-unverified` (needs
   evidence) in `verification.md`.
3. **Unincorporated critic findings** - items in `critic.md` that were
   neither folded into the synthesis nor refuted with evidence.
4. **Split consensus**: items marked `split` in `consensus.md` that
   verification did not settle.

Run each later pass on the ledger: extract `pass-<N-1>/residuals.md` from the
prior pass, stop on an empty ledger, make the prompt the ledger entries only,
and merge resolutions back into the prior synthesis (untouched findings carry
forward verbatim).

`refine` fills its ledger from its Distribute step instead: critique
points the woven version left unaddressed, runner-up strengths the
weave could not reconcile, and judge overrides or split judgments.

### Ledger format

Write `<session_dir>/pass-NNNN/residuals.md` (internal bookkeeping, not
shown to the user). One entry per residual:

- **Source**: conflict | verification | critic | split-consensus
- **Region**: the disputed claim or synthesis passage, quoted verbatim
- **Positions**: what each blind label asserted, when they differ
- **Resolution criterion**: what specific evidence (file, behavior,
  convention rule) would settle it

An empty ledger means the pass converged: skip remaining passes,
report convergence (this is the operational definition behind ask's
and review's early-stop; refine stops per the early-stop rule in `refine-cycle.md`).

### Scoped re-attack prompt

The pass N+1 prompt contains ONLY: the ledger entries, and for each
entry at most 10 surrounding lines of the pass-N synthesis for local
context. Never the full prior synthesis, never the original full task.
Instruct: "Resolve ONLY the items listed. For each, give your
resolution and the evidence (file paths, line references). Anything
outside these items is out of scope and will be discarded."

### Merge-back

Apply each resolved item as a local edit to the quoted region of the
pass-N synthesis; every untouched passage carries into the pass N+1
synthesis verbatim. Re-score only the rubric dimensions the resolved
items affect. Content a participant volunteered outside the ledger is
discarded unread - scope discipline is what makes residual passes
cheap.

---
