# Measurement Contract

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

`S_inst` and every `t_*` input are in minutes per instance.

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
S_net = (N * S_inst / 60) - C_build - (C_maint * periods)
```

```
N_breakeven = (C_build + C_maint * periods) * 60 / S_inst
```

- `N`: instances over the chosen horizon. `C_build`: one-time skill build
  hours. `C_maint`: hours per maintenance period, multiplied by the number
  of periods in that horizon. `S_net` is engineer-hours over the horizon;
  `N_breakeven` is an instance count.
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
Annual_hours_saved = V * F * (t / 60) * s * a * r
```

- `V` — addressable population: people whose work contains the task.
- `F` — instances per person per year.
- `t` — baseline minutes per instance (measured, not self-reported).
- `s` — savings rate net of the verification tax. When the run has
  `S_inst` and `t_manual`, `s = S_inst / t_manual`.
- `a` — adoption: active use, not license-holding. Strictly < 1.0.
- `r` — realization: the fraction of gross saved time that becomes
  usable capacity, since scattered minutes rarely convert. Strictly
  < 1.0.

Refuse to default `a` or `r` to 1.0. If either is absent from the
assumptions register, ask the user, then append the answer as an
ESTIMATED entry (or MEASURED, when an instrument export gives it)
with rationale and owner before projecting. With no one to ask,
halt and name the missing input.

Projection inputs must be finite and nonnegative. A measured slowdown is a
loss to report, not a savings-rate input to turn positive.

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
A measured input's `low` and `high` are its 95% interval ends; with
fewer than 5 observations they are the observed min and max, labeled a range.

- Conservative: every input at `low`, except cost inputs (`t_ai`,
  `t_verify`, `p_fail`, `t_rework`, `C_build`, `C_maint`), which sit at `high`.
- Base: every input at `value`.
- Upside: every input at `high`, cost inputs at `low`.

When `S_inst` is negative, more instances deepen the loss: `S_net` uses
the high task count in the conservative case and the low count in the upside.
An input without `low` or `high` stays at `value` in that scenario.
The chosen horizon, `periods`, stays at `value` in every scenario.
The committed number is always the conservative one.

## Statistics discipline

- Medians plus IQR, not means: task durations are right-skewed,
  roughly log-normal, and means chase the tail.
- A median paired difference is not the difference of the two medians.
  Compute before and after medians separately, or report only the paired gap.
- Bootstrapped BCa intervals for medians, computed by
  `../scripts/business.py stats` (absolute path; one number per line on stdin or
  in files). It prints n, median, quartiles, the 95% interval, the
  seed, and the resample count; paste them next to the result.
  Below n=5, `stats` prints `range_lo` and `range_hi` instead and no `ci95_*`; call that
  a range, never a "95% interval".
- Fewer than 20 observations, whether paired comparisons or single
  distributions: present the raw values, the median (or median
  difference), and the wide interval (the range when n<5), and label the result
  DIRECTIONAL (the script sets the label). Never
  single-decimal percentages from 5 tasks.
- The n=5 and n=20 thresholds control display, not precision or causal
  certainty; never treat crossing them as proof or a sample-size design.
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
