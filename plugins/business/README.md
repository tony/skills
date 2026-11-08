# business

Measure and report the business value of AI workflows with
provenance-tagged data: metrics in engineer-hours and cycle time,
never currency.

Every figure carries a provenance tag (MEASURED, DERIVED, BENCHMARKED,
or ESTIMATED); `references/provenance.md` holds the tag rules and the
no-currency contract.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install business --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace and install the plugin
with these two slash commands:

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
  scenarios, and inline assumptions. A measured loss is reported as one.
- `/business:report-org-wide` (tier 1): org-wide projection
  (`V * F * t * s * a * r`) with adoption and realization inputs,
  segmentation, and sensitivity ranking. Team aggregates only.
- `/business:case-study-internal` (tier 2): internal narrative
  (situation, outcomes, lessons, replication guide). Asks you for the
  maintainer, lessons, and build time the run does not hold. Individuals
  appear as roles.
- `/business:case-study-public` (tier 3): public case study.
  Sanitized of names, ticket IDs, and internal URLs, with each headline
  claim placed against external evidence or marked as having none.
- `/business:pr-release` (tier 3): one-page announcement derived from
  the public case study, with every figure traced to it.

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
- `evidence.md`: external studies with pinned links, a re-verify step,
  and what the evidence can and cannot support.
- `instruments.md`: probes, pinned-window conventions, absence
  snapshots.
- `interim-format.md`: run-directory layout, completeness gate, and
  report shapes.
- `audiences.md`: disclosure ladder and tier-3 sanitization checklist.

## Script

`scripts/business.py` (Python 3 standard library). Run
`business.py <command> --help` for each command.

- `init`: create a run directory, refusing one whose `raw/` holds
  snapshots.
- `collect-prs`: per-PR cycle-time and first-review CSV from
  `gh api graphql` pages. `--output` writes the CSV only when the pages
  parse and refuses to overwrite a snapshot; it warns when reviews were
  truncated or a column is absent from the rows.
- `stats`: median, quartiles, and a seeded BCa interval, or the range
  below n=5.
- `gate`: the completeness gate, recomputing `check:` figures from
  `raw/`.
- `assumptions`: register check, including one id per quantity.
- `project`: org-wide projection, scenarios, and sensitivity from
  register ids; a negative savings rate is a measured loss.
- `breakeven`: net per-instance and per-period saving and break-even
  from register ids.
- `runs`: newest-first run listing.
- `scan`: tier-3 identifier and money-term scan. `--run <run>` reads the
  README `Names:` line as the deny list, `--names-file <file>` adds
  names from a file, `--allow` and `--allow-url` skip false positives and
  citation links, `--rules` checks only some kinds, and stdin is scanned
  when no file is given.
- `stamp` and `fresh`: record the inputs a report was written from, then
  report any report that is unstamped or whose inputs changed.
- `trace`: list the numbers in a derived text, such as the PR release,
  that its source text, such as the case study, does not contain.

## Prerequisites

- `python3` (3.14 or newer) for `scripts/business.py`.
- `git` for history-based collection.
- `gh` CLI (optional) for PR/review telemetry.
- Ticket-tracker MCPs/CLIs are probed at runtime but not required.
