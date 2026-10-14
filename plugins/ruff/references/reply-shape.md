# Reply shape

The reply to the bump skill. Plain text outside any code fence, plain bullets with no bold label, direct statements rather than first person.

## Contents

- Hero and sections
- Required facts
- Left out
- Halted and blocked runs
- Templates

## Hero and sections

The first line of the reply is the hero, with nothing before it:

- `✓ N repos on ruff X.Y.Z`
- `⚠ Audit only: N repos behind`, with `, target version unconfirmed` appended when the target could not be confirmed
- `⚠ Nothing to do: N repos skipped`
- `⚠ M of N repos halted`

Then exactly these sections, in this order, with nothing between the hero and the first heading:

1. `## Release`
2. `## Scope`
3. `## Default rule set`, only when the release changed the default set or `--adopt-defaults` was passed; always before `## Per repo`
4. `## Per repo`
5. `## Verification`
6. `## Pre-merge`
7. `## Drift`

Omit a section with nothing to report, except `## Per repo` and `## Verification`. An audit-only run replies with `## Release`, `## Scope`, and `## Default rule set`, with predicted work and any resolver gate under `## Scope`.

## Required facts

Release:

- The changelog URL at the tag, the releases covered, and the ruff version used for measurement.
- What the release changes, sorted into the triage buckets; the formatter's scope change separately.
- `Bug fixes only.` alone when nothing was stabilized; one line when only the default set changed.

Scope:

- Each repository with its current and target versions; `unlocked` after a version no lockfile pins. State nothing else about lockfiles.
- What was excluded: fork, unowned, already current, already branched.
- Audit with several repositories: end each line with `Predicted: N rules`, the predicted commit count and the default-set delta.

Default rule set, per repository:

- Whether `select` is explicit, so the repository takes an added default rule only where its prefixes cover it. This is a finding.
- The measured delta of the recommended configuration and the shape measured, or `unmeasured` with the reason.
- Whether the run adopted the defaults.

Per repo:

- The rules that fired, each commit as the commit the run read back, and the formatter commit only when it rewrote files.
- For a grown rule, the `new`, `now` and `was` counts, noting that earlier findings of the code were fixed with it.
- Publication: pushed (only after the remote ref matched), the pull request URL, or the push command. A partial result says what did not happen, for example the floor committed but the defaults not adopted.
- A halted repository: the failing phase, the error, and the worktree path.

Verification:

- Each check as "<check> passes" or the failure itself, a failure named pre-existing or new against the baseline, and any failing check the repository requires.
- The CI conclusion, or that CI had not concluded.

Pre-merge: each repository carrying a temporary resolver exemption, and when its block lapses.

Drift holds only these: pin sites that disagreed before the bump, repositories with no lint configuration, repositories relying on the default set. Nothing else belongs there.

## Left out

- Any line whose only content is that something is missing, absent or unneeded: "no formatter commit", "the formatter changed nothing", "no CI", "no lockfile", "no quality checks defined", "no pull request was opened", "no rules were newly stabilized", "nothing blocked the install". List only what exists. An unknown or unmeasured fact is different: state it with its reason ("unmeasured", "target unconfirmed"), and say CI had not concluded only when CI ran.
- Remarks about how the run complied or what a tool printed: commit trailers, a rule lookup that returned nothing, a stubbed or blocked tool. The user needs outcomes.
- Verification lines for checks that were not run or are not defined: "no quality checks of its own", "the formatter changed no files", "nothing failed before the bump". Passing and failing checks only.
- First person ("I fetched", "I could not"). Write direct statements.
- The sandbox, git configuration (even when a write failed because of it), upstream tracking, and which skill rule or host default applied.
- Where the input came from, local absolute paths, and temp files, unless the user must act on that file.
- Advice about sandbox settings. Report an environment fault only when the user must act on it, in one clause with the failing step and the command to run next.
- A repository named by `cwd`. Use its remote slug or `[project] name`, or the basename of `git rev-parse --show-toplevel` when that is not generic.

State the vendor's default rule set only from a run of the project's runner (`check --show-settings`), never from memory. Recommend exempting only when the user said the release is needed now.

## Halted and blocked runs

A run that stops before any change (nothing behind, every repository skipped, the target unconfirmed outside an audit, or the user declined) is the hero, one result sentence, then what the user must do to proceed. Name what blocked in one clause ("pypi.org was unreachable").

An audit whose target cannot be confirmed still replies with `## Scope` (the current pins) and `## Default rule set` (each explicit `select` as a finding, the delta `unmeasured`). It ends on its last section, naming the failing step and the re-run command, with no panel.

## Templates

All example values are invented.

A run that stops before any change:

```text
⚠ Nothing to do: 1 repo skipped

Nothing changed: the branch ruff-bump-9.4.2 already exists in api.

To proceed, delete that branch or re-run with `--branch <name>`.
```

An audit with the target confirmed:

```text
⚠ Audit only: 2 repos behind

## Release

- Changelog: https://example.invalid/ruff/blob/9.4.2/CHANGELOG.md, releases 9.2.0 to 9.4.2, measured with ruff 9.4.2.
- Newly stabilized: ZZ101.

## Scope

- api: 9.1.0 to 9.4.2. Predicted: 1 rule (ZZ101), 3 commits, default-set delta 9 findings.
- web: 9.3.0 to 9.4.2, unlocked. Resolver gate needed (7 day cooldown). Predicted: 0 rules, 3 commits, default-set delta 0.

## Default rule set

- api: explicit `select = ["E", "F"]`, so it takes added default rules only where those prefixes cover them. Delta if it adopted the defaults: 9 findings, measured with `select` moved to `extend-select`. Not adopted.
- web: uses the defaults. Delta: 0 findings.
```

An audit with the target unconfirmed:

```text
⚠ Audit only: 1 repo behind, target version unconfirmed

## Scope

- api: pinned at ruff 9.1.0. The target could not be read because pypi.org was unreachable.

## Default rule set

- api: explicit `select = ["E", "F"]`, so it takes added default rules only where those prefixes cover them. Delta: unmeasured.

Re-run `/ruff:bump --audit-only` once pypi.org is reachable.
```

A completed local run:

```text
✓ 1 repo on ruff 9.4.2

## Release

- Changelog: https://example.invalid/ruff/blob/9.4.2/CHANGELOG.md, releases 9.2.0 to 9.4.2, measured with ruff 9.4.2.
- Newly stabilized: ZZ101 and ZZ204. The formatter now covers Markdown code blocks.

## Scope

- api: 9.1.0 to 9.4.2. web excluded as a fork.

## Per repo

- api: ZZ101 fired in 14 files (commit 3a1f9c2), ZZ204 in 2 (commit 7be40d5), formatter last (commit c19d8e3). Branch ruff-bump-9.4.2 not pushed; run `git push --set-upstream origin ruff-bump-9.4.2`.

## Verification

- Lint, format check, type check, and tests pass.
- CI had not concluded.
```

A release that changes only the default set reads, under `## Release`:

```text
- Changelog: https://example.invalid/ruff/blob/9.4.2/CHANGELOG.md, releases 9.2.0 to 9.4.2, measured with ruff 9.4.2.
- Default rule set gains ZZ310.
```
