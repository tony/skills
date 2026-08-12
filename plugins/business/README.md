# business

Measure and report the business value of AI workflows with
provenance-tagged data — metrics in engineer-hours and cycle time, never
currency.

> **Never use money.** Value is stated in engineer-hours, cycle-time
> deltas, throughput, quality rates, and capacity language. All figures
> carry a provenance tag (MEASURED, DERIVED, BENCHMARKED, ESTIMATED) and
> appropriate qualifiers.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install business@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add business@skills
```

*Note: The skills below use Claude Code's leading slash. Codex uses the
same names without it.*

## Components

### `/business:research` (skill)
Collects cycle times, review latency, and telemetry into a run directory
(`~/Documents/<date>/business/`). Writes a tagged interim package.
Unavailabilities are recorded as unknown.

### Report Commands (Bound to Disclosure Tiers)
- **`/business:report-leadership` (tier 0):** Full-detail leadership
  report (SCQA, exhibits, explicit multipliers, conservative scenarios,
  inline assumptions).
- **`/business:report-org-wide` (tier 1):** Org-wide projection
  (`V * F * t * s * a * r`). Includes adoption/realization inputs,
  segmentations, and sensitivity rankings. Team aggregates only.
- **`/business:case-study-internal` (tier 2):** Internal narrative case
  study (situation, outcomes, lessons, replication guide). Anonymizes
  individuals to roles.
- **`/business:case-study-public` (tier 3):** Public external case study.
  Strictly sanitized (no names, ticket IDs, or internal URLs). Outcomes
  are triangulated against external evidence.
- **`/business:pr-release` (tier 3):** One-page sanitized announcement
  derived from the public case study.

## Shared References
Read from `references/`:
- **`provenance.md`**: Tags, anti-inflation rules, no-currency contract.
- **`measurement.md`**: Saving/projection formulas, statistics discipline,
  quality guardrails.
- **`evidence.md`**: External study tables and triangulation.
- **`instruments.md`**: Probes, pinned-window conventions, absence
  snapshots.
- **`interim-format.md`**: Run-directory layout and completeness gates.
- **`audiences.md`**: Disclosure ladder and tier-3 sanitization checklist.

## Prerequisites

- `git` for history-based collection.
- `gh` CLI (optional) for PR/review telemetry.
- Ticket-tracker MCPs/CLIs are probed at runtime but not required.
