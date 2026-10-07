# Measurement Contract

Script paths here (`../scripts/...`) resolve from this file's directory; print the absolute path once and write it literally in each command.

## Contents

- Net per-instance saving
- Net over a period, and break-even
- Org-wide projection
- Scenarios
- Statistics discipline
- Counterfactual quality ladder
- Quality guardrails

Formulas, statistics discipline, counterfactual quality, and quality
guardrails for `/business:*`. The variable definitions here are the
only definitions — commands use them verbatim, never re-derive them.

## Net per-instance saving

```
S_inst = (t_manual - (t_ai + t_verify)) - (p_fail * t_rework)
```

- `t_manual` — baseline time per instance without the skill.
  Measured, not self-reported; see the counterfactual ladder.
- `t_ai` — AI-assisted time per instance, including failed and
  abandoned runs.
- `t_verify` — verification and review time. Always inside the task
  boundary.
- `p_fail` — probability the AI-assisted result needs rework.
- `t_rework` — time to rework a failed instance.

## Net over a period, and break-even

```
S_net = (N * S_inst) - C_build - (C_maint * periods)
```

```
N_breakeven = (C_build + C_maint * periods) / S_inst
```

- `N`: instances in the period. `C_build`: one-time skill build
  time. `C_maint`: maintenance time per period.
- `business.py breakeven <run>` computes `S_inst`, `S_net`, and
  `N_breakeven` per scenario from these register ids:
  `manual-minutes` (`t_manual`), `ai-minutes` (`t_ai`),
  `verify-minutes` (`t_verify`), `rework-probability` (`p_fail`),
  `rework-minutes` (`t_rework`), `instances-in-period` (`N`),
  `build-hours` (`C_build`), `maintenance-hours-per-period`
  (`C_maint`), and `periods`. Minutes and hours as named; never
  compute these by hand. A figure whose inputs are not all registered
  is absent and each absent id prints as `missing:`.
- Report break-even explicitly: the instance count at which the
  skill pays back its build and upkeep is more honest and more
  useful than an annualized headline.

## Org-wide projection

```
Annual_hours_saved = V * F * t * s * a * r
```

- `V` — addressable population: people whose work contains the task.
- `F` — instances per person per period.
- `t` — baseline time per instance (measured, not self-reported).
- `s` — savings rate net of the verification tax.
- `a` — adoption: active use, not license-holding. Strictly < 1.0.
- `r` — realization: the fraction of gross saved time that becomes
  usable capacity, since scattered minutes rarely convert. Strictly
  < 1.0.

Refuse to default `a` or `r` to 1.0. If either is absent from the
assumptions register, ask the user, then append the answer as an
ESTIMATED entry (or MEASURED, when an instrument export gives it)
with rationale and owner before projecting. With no one to ask,
halt and name the missing input.

Segment the population: addressable ⊃ served ⊃ realized. Reporting
only the addressable figure is the most common inflation — always
show all three segments.

`business.py project <run>` does the arithmetic from these register
ids, with `F` per person per year and `t` in minutes:
`addressable-population` (`V`), `instances-per-person-year` (`F`),
`baseline-minutes` (`t`), `savings-rate` (`s`), `adoption-rate` (`a`),
`realization-rate` (`r`). It prints the three scenarios, the segment
hours, and the one-way sensitivity ranking; never recompute them by
hand.

## Scenarios

Each register entry may carry `low` and `high` fields beside `value`.
A measured input's `low` and `high` are its 95% interval ends.

- Conservative: every input at `low`, except cost inputs (`t_ai`,
  `t_verify`, `p_fail`, `t_rework`, `C_build`, `C_maint`), which sit at `high`.
- Base: every input at `value`.
- Upside: every input at `high`, cost inputs at `low`.

An input without `low` or `high` stays at `value` in that scenario.
The committed number is always the conservative one.

## Statistics discipline

- Medians plus IQR, not means: task durations are right-skewed,
  roughly log-normal, and means chase the tail.
- Bootstrapped BCa intervals for medians, computed by
  `../scripts/business.py stats` (one number per line on stdin or
  in files). It prints n, median, quartiles, the 95% interval, the
  seed, and the resample count; paste them next to the result.
  Small n gets wide intervals and honesty, not precision.
- Fewer than 20 observations, whether paired comparisons or single
  distributions: present the raw values, the median (or median
  difference), and the wide interval, and label the result
  DIRECTIONAL (the script sets the label). Never
  single-decimal percentages from 5 tasks.
- Exclude the novelty ramp window; measure steady state. State the
  excluded window in the run README. No identifiable introduction
  event to anchor a ramp on → state "none excluded" with the
  reasoning, rather than inventing a window.

## Counterfactual quality ladder

Best → worst. Label which rung every comparison sits on:

1. Self-A/B with tasks pre-specified before randomization.
2. Paired task design.
3. Pre-period cycle-time distribution.
4. Matched historical tasks.
5. Retrospective recall — weakest; always labeled as such.

## Quality guardrails

Time saved that degrades these is not savings. Track them alongside
any savings claim:

- Delivery lead time.
- Deployment / change frequency.
- Change-failure rate and rework, revert, and reopen rates.
- Review latency.
- PR-size drift.
- CI failure and retry rates.

Activity metrics (lines of code, commit counts, PR counts) never
stand alone, per Forsgren et al., "The SPACE of Developer
Productivity" (ACM Queue 19(1), 2021,
https://queue.acm.org/detail.cfm?id=3454124). They may appear only next
to a quality or outcome metric.
