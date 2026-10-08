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

Hard sanitization contract:

- No organization, repository, team, or person names; no ticket
  IDs; no internal URLs; no internal or local file paths.
- Aggregates and ranges only. Round to honest precision: a
  number's precision must not exceed what its interval supports.
- Every headline claim triangulated against the field range.
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

`/business:case-study-public` runs this as an explicit final pass
over the finished draft. `/business:pr-release` inherits the result
by sourcing figures only from the public case study.

1. Run the scanner (by its absolute path) over the draft, passing each name on the
   `Names:` line of the run's `README.md` as `--deny`, one flag per
   name. When the README has no `Names:` line, stop and ask the user
   for the names to deny (`Names: none` is a valid answer, meaning no `--deny` flags, never
   `--deny none`). List organization and team names as bare words
   ("Atlas", not "Atlas team"):

   ```console
   $ ../scripts/business.py scan \
       --deny <name> \
       --allow-url https://arxiv.org/ \
       --allow UTF-8 \
       <draft file>
   ```

   It flags ticket IDs, URLs, local paths, emails, currency, and
   money terms (exit 1 on any hit). `--allow-url <prefix>` keeps
   the pinned citation links BENCHMARKED figures need, one prefix
   per cited host; `--allow <text>` skips a false positive such as
   `UTF-8` or `GPT-4`. `--deny` and both allow flags repeat. Remove or reword every other
   hit. Then read the draft once for names the scanner cannot know
   and for the re-identification rule above.
2. Confirm every figure is an aggregate or a range, rounded to
   honest precision, with its provenance tag and denominator.
3. Confirm every headline claim passed triangulation or carries its
   methodology defense.
4. Confirm the limitations section is present and candid.
5. Confirm no currency appears; external text travels furthest.

Report the checklist in the `## Sanitization` section of the
command output: pass per item, with what was removed or reworded.

## Firewall sweep

`/business:pr-release` verifies the public case study instead of
trusting it. Before deriving the announcement, run checklist items 1,
2, 4, and 5 over it; triangulation was the case study's job. The only
thing it reads from the run is the `Names:` line of `README.md` for
`--deny`; no figure comes from there.

Any failure stops the run: regenerate via `/business:case-study-public`,
never patch around it in the release. Report a passing sweep in
`## Firewall`; a failing one is a stopped run that names the failed
items.
