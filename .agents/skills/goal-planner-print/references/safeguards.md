# Select safeguards by need

Every goal needs outcome, scope, authority, and observable acceptance. Add a
safeguard only for a concrete failure mode, explicit request, or applicable
project/profile rule. State its trigger, evidence, and applicability. Write
these clauses under [prose-rules.md](./prose-rules.md).

## Study and experiments

For unfamiliar contracts or consequential behavior changes, study pinned
source, existing implementations, root causes, native idioms, and concrete
callers. Keeping the current approach is a valid outcome when alternatives
lack demonstrated benefit. Reuse studies whose relevant inputs remain valid.

Choose one experiment that answers the uncertainty: `spike:probe` for one
unknown, `spike:bakeoff` for competing approaches, or `spike:ratchet` for
retained iterative evidence. Check optional skill availability; a plain-language
equivalent is acceptable unless the user specifically requires the integration.
Define bounds and decision criteria before the future experiment. Drafting
the goal does not run it.

## Independent review

Require independent review when requested or triggered by an approved profile.
Give a fresh reviewer the original request, contract, exact revision, evidence,
and failure rubric. A fresh agent using the same model can be independent;
model diversity is a separate property. A self-check is not adversarial review.
Unavailable required review remains UNVERIFIED.

Challenge both missing guarantees and unnecessary guarantees that manufacture
an impasse. Ask what user benefit justifies each constraint. Preserve failed
findings and disagreements; bound rounds and stop on a concrete unresolved
blocker instead of sampling until a reviewer passes. Use blind comparisons,
calibration, negative controls, or deliberately broken inputs when they answer
a real concern. A gate should demonstrably reject its intended failure.

Choose quality dimensions for the domain. Documentation may need learning,
lookup, developer design, evidence, examples, and prose judgments; libraries
may need native idioms, compatibility, concurrency, and installed consumers;
UI work may need accessibility, responsive layouts, and rendered inspection.
Use numerical thresholds only when requested, with a rubric. Scores never
waive a mandatory failure.

## Verification and delivery

Discover project quality commands from its instructions. Select meaningful
tests, hand tests, runnable examples, installed consumers, rendered docs, or
actual user workflows according to the change. Test counts do not establish
usability or contract coverage. Preserve failed checks and compare against
the relevant baseline before attributing a regression.

When delivery is in scope, bind CI to the exact required local/remote/PR head
and individual job conclusions. Queued, skipped, stale, or unsupported checks
are not PASS. Require review, merged trunk, registry artifacts, deployment,
or package consumption only when the requested delivery needs them. A build
does not prove publication. Keep commit, changelog, release, and remote actions
within current or explicitly future authorization.

Use isolated worktrees, focused commits, recovery references, serial changes,
and exact remote identity when the work calls for them. Authorized rewrites
need the applicable lease and recovery rules. Do not add repository surgery
to a print-only request.

## Resources, deadlines, and cleanup

For heavy phases, define CPU, available-memory, free-space, worker-concurrency,
and expensive-evaluation budgets as applicable. Specify host versus owned
process scope, sampling interval, memory definition, and target filesystem.
Time the entire command, including setup. Machine-specific thresholds need
explicit selection; unavailable probes mean unknown.

Resource safety and benchmark validity are separate. Competing heavy work can
distort timings below safety ceilings. Isolate or defer measurements, or label
interference. Under resource pressure, defer or serialize owned heavy work
while continuing independent light work. Resume through process/resource events
or bounded checks; avoid busy polling. Verify a live job/process handle before
calling a wait verified. A stale lock is not proof of a live worker.

Distinguish soft failure thresholds, which can fail a gate while evidence
collection continues, from hard deadlines, which stop owned processes and
retain partial logs and artifacts. A local timeout does not prove a remote
job stopped. State escalation and recovery only when the task needs them.

Clean only owned disposable outputs with known reproduction and dependencies.
Preserve source, unrelated worktrees, shared live caches, recovery objects,
history, failed evidence, and intentionally retained hand-test fixtures or
preview servers. Measure recovered space. Missing platform capability or
insufficient safe cleanup is a constraint, not invented evidence of safety.

## Cost and proportionality

Require concrete user value for machinery, abstractions, or additional gates.
Preserve load-bearing rationale and remove redundant scaffolding. A small
documentation correction does not need a benchmark program, reviewer ensemble,
release pipeline, or monitoring service. Explicitly requested expensive checks
remain obligations; make their costs and scope visible.
