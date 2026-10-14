# Audience Sensitivity Ladder

## Contents

- When the package holds no committable savings figure
- Tiers 0 to 3
- Tier-3 final checklist
- Firewall sweep

Four disclosure tiers, from tier 0 (internal leadership, full
detail) to tier 3 (fully external). The binding rule: an artifact
may never contain detail its tier's contract excludes, even though
the run directory has it. Sanitization is a property of the
artifact, not of the data.

## When the package holds no committable savings figure

A complete package may still contain no defensible savings number:
early instrumentation, unknowns blocking `S_inst`, no counterfactual
yet. Render an evidence report at any tier: the headline states what
the data does and does not yet support, and where a committed number
would go, the open unknowns and the data that would resolve them.
Refusal is for gate failures, never for a thin dataset.

## Tier 0: leadership

Full detail: names, raw links, registers inline. Provenance tags
render with complete source refs: manifest entry names, file paths,
assumption ids.

## Tier 1: org-wide

Team-level aggregates only; no individual names anywhere. Internal
team and system names allowed. Ends with a plain-language summary
readable by the whole company: no methodology jargon, figures still
tagged and true.

## Tier 2: internal case study

Internal team and repo names allowed; individuals anonymized to
roles ("a senior engineer", never a name). Tags with internal source
refs allowed.

## Tier 3: public

This contract covers the saved report and the entire reply, including checklist
results, the run description, and next steps:

- No internal organization, repository, team, or person names; no ticket
  IDs, internal URLs, or internal/local file paths. Public study names may
  appear only as citations, not as identities of the measured group.
- Aggregates and ranges only. Round to honest precision: a
  number's precision must not exceed what its interval supports.
- Every headline claim placed per `evidence.md`: against a study of the
  same outcome where one exists, otherwise stated as having no external
  comparator.
- A candid limitations section is mandatory; credibility is the PR
  asset.
- Provenance tags remain on every figure, rendered as tag plus
  method phrase ("MEASURED over a 12-week window, n=41 PRs") with
  internal source refs stripped.
- Re-identification: a small team plus an exact window can name the
  team. Describe teams of fewer than 10 people by kind only ("a
  small product team"), round the window to a month or quarter, and
  drop any combination of team size, window, and domain that points
  at one group.

## Tier-3 final checklist

the `business-case-study-public` skill runs this as an explicit final pass
over the saved report. the `business-pr-release` skill inherits the result
by sourcing figures only from the public case study.

1. Scan the saved file, not a draft, with the absolute path to the
   script. `--run` makes the scanner read the names itself from the
   `Names:` line of the run's `README.md`, so no name is ever typed into
   a shell. It exits 2 when the README has no `Names:` line, and `Names:
   none` means no names. A person, team, or workflow name on that line is
   denied whole and by each of its words, in any case and with any
   separator:

   ```console
   $ ./business.py scan \
       --run <run> \
       --allow-url https://arxiv.org/ \
       --allow UTF-8 \
       <run>/reports/<name>.md
   ```

   It flags ticket IDs, URLs, hosts, IP addresses, local paths, emails,
   `@handles`, tokens and private keys, `owner/repo` slugs, currency, and
   money terms (exit 1 on any hit). `--allow-url <prefix>` keeps
   the pinned citation links BENCHMARKED figures need, one prefix
   per cited host; `--allow <text>` skips a false positive such as
   a slash pair or a version string. Both allow flags repeat. Reword
   every other hit in the file and scan again until it prints `clean`.
   Then read the file once for names the scanner cannot know and for
   the re-identification rule above.
2. Confirm every figure is an aggregate or a range, rounded to
   honest precision, with its provenance tag and denominator.
3. Confirm every headline claim carries its external placement or "no
   external comparator", or its methodology defense.
4. Confirm the limitations section is present and candid.
5. Confirm no currency appears; external text travels furthest.

Report the checklist in `## Sanitization` with one short result per check;
omit scanner debugging, discarded flags, and descriptions of tool access.
Name removed categories, never the excluded strings: "personal names removed",
not the names themselves. In `## Run`, use the task category and rounded
window; in `## Report`, name only the report's filename, not an internal path.

Before replying, pipe the reply to the scanner on stdin with the same
`--run` and allow flags, then reword every hit and scan again until it
prints `clean`:

```console
$ ./business.py scan \
    --run <run> \
    --allow-url https://arxiv.org/ \
    --allow UTF-8 <<'EOF'
<the reply text>
EOF
```

Send only the checked text. A clean report does not establish that its
accompanying reply is safe to publish. For a stopped run, never repeat
excluded strings or the supplied run path; name the failed category and
the skill to run next. Without a run directory, use that generic refusal
without creating files or scanning.

## Firewall sweep

the `business-pr-release` skill verifies the public case study instead of
trusting it. Before deriving the announcement, run checklist items 1,
2, 4, and 5 over the saved case study; placement against external evidence
was the case study's job. The only thing it reads from the run is the
`Names:` line of `README.md`, through `--run`; no figure comes from there.

Any failure stops the run: regenerate via the `business-case-study-public` skill,
never patch around it in the release. Report a passing sweep in
`## Firewall`; a failing one is a stopped run that names the failed
items.
