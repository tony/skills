# business

Measure and report the business value of AI workflows with
provenance-tagged data: metrics in engineer-hours and cycle time,
never currency.

> Never use money. Value is stated in engineer-hours, cycle-time
> deltas, throughput, quality rates, and capacity language. All figures
> carry a provenance tag (MEASURED, DERIVED, BENCHMARKED, ESTIMATED) and
> appropriate qualifiers.

## Installation

In Claude Code, add the marketplace and install the plugin with these
two slash commands:

```text
/plugin marketplace add tony/skills
```

```text
/plugin install business@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add business@skills
```

Every skill runs only when invoked by name; none is routed to
automatically.

Claude Code uses a leading slash (`/business:…`). Codex omits it (`business:…`).

## Skills

### `/business:research`

Collects cycle times, review latency, and telemetry into a run
directory (`~/Documents/<date>/business/<workflow>/`) and writes a
tagged interim package. Unavailable data is recorded as unknown.

### Report skills, one per disclosure tier

- `/business:report-leadership` (tier 0): full-detail leadership
  report with SCQA, exhibits, explicit multipliers, conservative
  scenarios, and inline assumptions.
- `/business:report-org-wide` (tier 1): org-wide projection
  (`V * F * t * s * a * r`) with adoption and realization inputs,
  segmentation, and sensitivity ranking. Team aggregates only.
- `/business:case-study-internal` (tier 2): internal narrative
  (situation, outcomes, lessons, replication guide). Individuals
  appear as roles.
- `/business:case-study-public` (tier 3): public case study.
  Sanitized of names, ticket IDs, and internal URLs, with outcomes
  triangulated against external evidence.
- `/business:pr-release` (tier 3): one-page announcement derived from
  the public case study.

### Handing hours to finance

Reports stop at engineer-hours, cycle time, and capacity. To compare
against a budget, give finance the hours with their interval, the
pinned window, and the population (engineers and period). Finance
converts them with its own rates outside this plugin's artifacts.

## Shared references

Read from `references/`:

- `provenance.md`: tags, anti-inflation rules, the no-currency
  contract.
- `measurement.md`: saving and projection formulas, statistics
  discipline, quality guardrails.
- `evidence.md`: external studies with pinned links and a re-verify
  step.
- `instruments.md`: probes, pinned-window conventions, absence
  snapshots.
- `interim-format.md`: run-directory layout, completeness gate, and
  report shapes.
- `audiences.md`: disclosure ladder and tier-3 sanitization checklist.

## Script

`scripts/business.py` (Python 3 standard library) does the
deterministic work: `stats` (median, quartiles, seeded BCa interval, or the range below n=5),
`scan` (tier-3 identifier and money-term scan, with `--allow` and
`--allow-url` for false positives and citation links), `gate` (the
completeness gate, recomputing `check:` figures from `raw/`),
`assumptions` (register check), `project` (org-wide projection,
scenarios, and sensitivity from register ids), `breakeven` (net
per-instance and per-period saving and break-even from register ids), and `collect-prs`
(per-PR cycle-time and first-review CSV from `gh api graphql` pages), and
`runs` (newest-first run listing).

## Prerequisites

- `python3` (3.9 or newer) for `scripts/business.py`.
- `git` for history-based collection.
- `gh` CLI (optional) for PR/review telemetry.
- Ticket-tracker MCPs/CLIs are probed at runtime but not required.
