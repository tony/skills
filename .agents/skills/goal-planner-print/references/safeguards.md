# Select safeguards by need

Every goal needs outcome, scope, authority, and observable acceptance. Add
safeguards for a concrete failure mode, explicit request, or applicable
project/profile rule; state trigger, evidence, applicability, and cost under
[prose-rules.md](./prose-rules.md). Keep load-bearing rationale and require user
value for machinery or extra gates. A small docs fix needs no benchmark or
release program, but explicitly requested expensive checks remain obligations.

## Study and experiments

For unfamiliar contracts or consequential changes, study pinned source,
existing implementations, root causes, native idioms, and callers. Reuse valid
studies; retaining the current approach is valid without demonstrated benefit.

Choose an experiment for the uncertainty: `spike:probe` for one unknown,
`spike:bakeoff` for alternatives, or `spike:ratchet` for iterative evidence.
Check availability; a plain-language equivalent suffices unless the integration
is specifically required. Define bounds and decision criteria in the future
goal without running the experiment while drafting.

## Independent review

When requested or triggered by an approved profile, give a fresh reviewer the
original request, exact contract revision, evidence, and failure rubric.
Same-model review can be independent; model diversity is separate. A self-check
is not adversarial review; unavailable required review stays UNVERIFIED.

Challenge missing guarantees and unnecessary constraints. Preserve failures and
disagreements, bound rounds, and stop at concrete unresolved blockers instead
of sampling until PASS. Use blind comparisons, calibration, negative controls,
or broken inputs for relevant concerns; a gate should reject its target failure.

Select domain dimensions: documentation may need learning, lookup, developer
design, evidence, examples, and prose; libraries may need native idioms,
compatibility, concurrency, and installed consumers; UI may need accessibility,
responsive layouts, and rendered inspection. Use numeric thresholds only when
requested, with a rubric; scores cannot waive mandatory failures.

## Verification and delivery

Discover project quality commands from its instructions. Choose meaningful
tests, hand tests, runnable examples, consumers, rendered docs, or user
workflows for the change. Counts do not prove usability or coverage. Preserve
failures and compare the relevant baseline before calling them regressions.

For requested delivery, bind CI to exact local/remote/PR heads and individual
job conclusions; queued, skipped, stale, or unsupported checks are not PASS.
Require review, merged trunk, registry artifacts, deployment, or consumption
only as delivery needs them. A build does not prove publication. Keep commits,
changelogs, releases, and remote actions within present or explicit future
authority. Use isolated worktrees, focused commits, recovery references, serial
changes, and exact remote identity when applicable; authorized rewrites need
lease and recovery rules. Printing does not require repository surgery.

## Resources, deadlines, and cleanup

For heavy phases select CPU, available-memory, free-space, concurrency, and
expensive-evaluation budgets as applicable. Specify host/owned-process scope,
sampling interval, memory definition, and target filesystem. Time entire
commands including setup. Machine thresholds need selection; absent probes mean
unknown. Safety ceilings do not establish benchmark validity: isolate/defer
competing heavy work or label interference.

Under pressure, defer or serialize owned heavy work and continue independent
light work. Resume through events or bounded checks without busy polling.
Verify live job/process handles before claiming a verified wait; stale locks
prove no live worker. Soft thresholds can fail gates while evidence collection
continues; hard deadlines stop owned processes and retain partial logs/artifacts.
A local timeout does not prove a remote job stopped. Add escalation/recovery
only when needed.

Clean only owned disposable outputs with known reproduction and dependencies;
measure recovered space. Preserve source, unrelated worktrees, shared live
caches, recovery objects, history, failures, and intentionally retained
hand-test fixtures or preview servers. Missing capability or insufficient safe
cleanup remains a constraint, not evidence of safety.
