# Ruff release triage

What a ruff release does to a given repository, worked out before touching a file. If the linter surfaces something this triage did not predict, you misread the release or the configuration; find out which before committing a fix.

## Read the release, not the version number

A bump can carry breaking changes whatever its version number; read the changelog for the target tag, and every section between the resolved version and the target (the target tag's changelog holds the earlier sections). Changes from an intervening release count as much as the target's.

Three sources, in order of authority:

1. The repository's own `CHANGELOG.md` at the release tag, `https://github.com/astral-sh/ruff/blob/<tag>/CHANGELOG.md`. This is canonical and complete.
2. The vendor's release blog post, when one exists for that version. Better narrative, sometimes omits detail.
3. The GitHub release page. Usually a rendering of the changelog.

If a local clone of the linter's source is available, reading the changelog at the tag is faster and more reliable than fetching it. Otherwise fetch the changelog from the tag ref, not from the default branch, which describes unreleased work.

## Sort every change into one of five buckets

**Newly stabilized rules.** Rules promoted out of preview. These fire on repos that were never running preview mode, which is the common case, and are therefore the main source of new diagnostics. Record each rule's code and its prefix.

**Stabilized behavior inside existing rules.** A rule that already fired now fires in more places, or in fewer. These produce diagnostics on code that has been clean for years, which reads as a false positive until you check the changelog. Record the rule code and what widened.

**Default configuration changes.** Changes to what is selected when the repo does not say. Check which case each repo is in (explicit `select`, `extend-select` only, or neither) before predicting anything. The opt-out rules are in the default-rule-set reference.

**Formatter changes.** New syntax handled, changed output, or, the expensive one, new *file types* brought into the formatter's scope. A formatter that starts formatting embedded code inside documentation files will rewrite files that no formatter has ever touched in that repo, and the diff can dwarf every lint fix combined. Predict this by running `<runner> format --check --no-cache` before and after the version change and comparing the count on its last line (`N files would be reformatted`).

**Output and interface changes.** Serialization formats, exit codes, CLI flags, suppression-comment syntax. These break tooling that parses the linter's output (CI annotation scripts, editor integrations, report generators), not the code being linted. Grep the repo for anything that consumes the linter's machine-readable output.

## Intersect the release with each repo's configuration

A rule can only fire if the repo selects it. For each repo, extract the effective rule selection with `<runner> check --no-cache --show-settings <file.py>` (it resolves `extend`, `ruff.toml` against `pyproject.toml`, and per-file ignores) rather than reading config by hand; before approval `<runner>` is the ephemeral runner. It covers `select`, `extend-select`, `ignore`, `extend-ignore`, per-file ignores, and whether preview mode is on. Then intersect:

- A newly stabilized rule fires only if its prefix is selected and its code is not ignored.
- A behavior change fires only if that specific rule was already selected.
- A default-set change fires where the repo has no explicit `select`; with one, only the added rules its prefixes cover.
- Formatter changes apply regardless of rule selection.

Write the prediction down before running anything. A rule you predicted that does not fire is fine: the code was already clean. A rule that fires and you did not predict means your reading of either the release or the config was wrong, and you need to resolve that discrepancy rather than reflexively applying the autofix.

## Per-rule triage before fixing

For each rule that actually fires, fetch its documentation page and read the *why*. Rules fall into three classes, and the class determines how much care the fix needs:

**Cosmetic.** Reordering, spelling, redundant syntax. The autofix is safe and the diff is mechanical. Commit it with the rule's rationale in the body.

**Semantic but equivalent.** The fix changes the code's shape but provably not its behavior: comprehension rewrites, path-API migrations, string-formatting changes. Run the project's test suite specifically to confirm the equivalence claim rather than trusting it.

**Behavior-changing.** The current code is subtly wrong, and fixing it changes what the program does. Exception-handling, logging, iterator-protocol and return-type rules land here. Explain the behavior delta in the commit body, ideally with a test that would have caught the old behavior.

## Suppressions are a last resort with a stated reason

A suppression means the rule is wrong about this code or the fix is not worth its cost. Write the reason in the commit body. Where to put it is in `default-rule-set.md`, under curating.
