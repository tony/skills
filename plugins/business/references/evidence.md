# External Evidence Table

## Contents

- Re-verify before citing
- Field studies
- Lab and context sources
- Usage rules
- Triangulation procedure

The BENCHMARKED sources for triangulating internal claims. An
internal savings claim must land near the study that measures the
same outcome, or explain its divergence.

The studies measure different outcomes, so there is no pooled range.
Place an internal figure by outcome:

- Task completion time: METR (time up 19%, early-2025 tools, about
  16% slower) and Google (time down about 21%, wide interval).
- Completed tasks: Cui et al. (+26.08% completed tasks).
- Throughput, review load, and quality: the context sources below,
  directional only.

The lab result is listed separately and never sets an expectation.

Table compiled 2026-07-24.

## Re-verify before citing

A run that cites this table repeats the check first:

1. Open each source it will cite at the pinned link with WebFetch.
   Without a fetch tool, ask the user to confirm the figure.
2. Confirm the quoted figure, sample size, and date appear at that
   link. Update the entry if the source revised them. Drop the entry
   from the report if the link is gone or the figure is absent.
3. Cite the date of this check as the retrieval date. Without a
   check, cite the table's date above and say the run did not
   re-verify.

## Field studies

- METR RCT, early-2025 tools (Becker, Rush, Barnes, Rein; arXiv
  [2507.09089](https://arxiv.org/abs/2507.09089), Jul 2025). 16
  experienced open-source developers, 246 real tasks in mature
  repos: completion time 19% longer with AI allowed. METR's
  later update ([Feb 24, 2026](https://metr.org/blog/2026-02-24-uplift-update/))
  reports follow-up estimates with newer tools whose intervals
  include zero, and says task selection bias makes them unreliable.
  Cite the 19% as the early-2025 result only.
- Cui et al. three-firm field experiments (DOI
  [10.1287/mnsc.2025.00535](https://doi.org/10.1287/mnsc.2025.00535),
  Management Science; SSRN
  [4945566](https://papers.ssrn.com/abstract=4945566)). 4,867
  developers at three firms: +26.08% completed tasks (SE
  10.3%). Less experienced developers adopted more and gained more.
- Google enterprise RCT (Paradis et al.; arXiv
  [2410.12944](https://arxiv.org/abs/2410.12944), Oct 2024). 96
  full-time engineers on an enterprise task: time on task shortened
  by about 21%, with a wide confidence interval.

## Lab and context sources

- Peng et al. (arXiv [2302.06590](https://arxiv.org/abs/2302.06590),
  2023). Synthetic greenfield HTTP-server task: 55.8% faster.
  Lab upper bound; never a field expectation.
- Bain Technology Report 2025 ([Sep 23, 2025](https://www.bain.com/insights/from-pilots-to-payoff-generative-ai-in-software-development-technology-report-2025/)).
  Teams with AI assistants see 10–15%; 25–30% with
  end-to-end process change; writing and testing code is 25–35% of
  idea-to-launch time. Consultancy report; flag it as such.
- DORA 2024 ([announcement](https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report)).
  Per 25% more AI adoption: estimated −1.5% delivery
  throughput and −7.2% delivery stability. DORA 2025
  ([report PDF](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf),
  nearly 5,000 respondents): AI amplifies existing team strengths
  and weaknesses.
- Faros AI Productivity Paradox, 2025 (vendor;
  [report](https://www.faros.ai/ai-productivity-paradox)). Telemetry
  from 10,000+ developers in 1,255 teams: high-adoption teams
  complete 21% more tasks and merge 98% more PRs; PR review
  time +91%, PR size +154%, bugs per developer +9%; no
  significant company-level correlation with delivery metrics.
  Directional; magnitudes are vendor-sourced.
- CodeRabbit AI vs human code report, Dec 2025 (vendor;
  [report](https://coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report)).
  470 open-source PRs (320 AI co-authored, 150 human): 10.83 vs
  6.45 issues per PR, about 1.7×. Directional only.

## Usage rules

- Cite a BENCHMARKED figure with its study label above, its link,
  and the retrieval date from the re-verify step.
- Never import a vendor headline as an internal savings-rate input.
  Cite it beside your own MEASURED number, flagged `(vendor)`.
- Vendor magnitudes are directional context. Internal inputs come
  from your own instruments or from the non-vendor studies, cited.

## Triangulation procedure

For each headline claim:

1. State the internal figure with its tag and denominator.
2. Place it against the study that measures the same outcome (see
   the top of this file). Near it: note how the settings differ.
3. Far from it: remove the claim, or keep it with an explicit
   methodology defense. Name what makes this setting different and
   which rung of the counterfactual ladder the comparison sits on.
4. Record the triangulation outcome next to the claim so a reviewer
   can retrace it.
