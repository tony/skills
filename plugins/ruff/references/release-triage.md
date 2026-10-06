# Ruff release triage

What a ruff release does to a given repository, worked out before touching a file. If the linter surfaces something this triage did not predict, you misread the release or the configuration; find out which before committing a fix.

## Read the release, not the version number

Ruff ships breaking changes in minor releases, so a `0.N` bump is not a patch. Three sources, in order of authority:

1. The repository's own `CHANGELOG.md` at the release tag. This is canonical and complete.
2. The vendor's release blog post, when one exists for that version. Better narrative, sometimes omits detail.
3. The GitHub release page. Usually a rendering of the changelog.

If a local clone of the linter's source is available, reading the changelog at the tag is faster and more reliable than fetching it. Otherwise fetch the changelog from the tag ref, not from the default branch — the default branch describes unreleased work.

## Sort every change into one of five buckets

**Newly stabilized rules.** Rules promoted out of preview. These fire on repos that were never running preview mode, which is the common case, and are therefore the main source of new diagnostics. Record each rule's code and its prefix.

**Stabilized behavior inside existing rules.** A rule that already fired now fires in more places, or in fewer. These produce diagnostics on code that has been clean for years, which reads as a false positive until you check the changelog. Record the rule code and what widened.

**Default configuration changes.** Changes to what is selected when the repo does not say. Critical distinction: an explicit `[tool.ruff.lint] select` **replaces** the default set rather than extending it, so a release that dramatically expands the defaults produces no new diagnostics for any repo that sets `select`. It is only an immediate event for repos relying on the default, or using `extend-select` on top of it. Check which case each repo is in before predicting anything.

Do not report this bucket as inert: a repo with an explicit `select` is opted out of the new defaults. Raise it as a decision in the procedure's default-rule-set step.

**Formatter changes.** New syntax handled, changed output, or — the expensive one — new *file types* brought into the formatter's scope. A formatter that starts formatting embedded code inside documentation files will rewrite files that no formatter has ever touched in that repo, and the diff can dwarf every lint fix combined. Predict this by comparing the file count the formatter reports against the count of source files it used to cover.

**Output and interface changes.** Serialization formats, exit codes, CLI flags, suppression-comment syntax. These break tooling that parses the linter's output — CI annotation scripts, editor integrations, report generators — not the code being linted. Grep the repo for anything that consumes the linter's machine-readable output.

## Intersect the release with each repo's configuration

A rule can only fire if the repo selects it. For each repo, read its linter configuration and extract the effective rule selection: `select`, `extend-select`, `ignore`, `extend-ignore`, per-file ignores, and whether preview mode is on. Then intersect:

- A newly stabilized rule fires only if its prefix is selected and its code is not ignored.
- A behavior change fires only if that specific rule was already selected.
- A default-set change fires only if the repo has no explicit `select`.
- Formatter changes apply regardless of rule selection.

Write the prediction down before running anything. A rule you predicted that does not fire is fine — the code was already clean. A rule that fires and you did not predict means your reading of either the release or the config was wrong, and you need to resolve that discrepancy rather than reflexively applying the autofix.

## Per-rule triage before fixing

For each rule that actually fires, fetch its documentation page and read the *why*. Rules fall into three classes, and the class determines how much care the fix needs:

**Cosmetic.** Reordering, spelling, redundant syntax. The autofix is safe and the diff is mechanical. Commit it with the rule's rationale in the body.

**Semantic but equivalent.** The fix changes the code's shape but provably not its behavior — comprehension rewrites, path-API migrations, string-formatting changes. Run the project's test suite specifically to confirm the equivalence claim rather than trusting it.

**Behavior-changing.** The current code is subtly wrong, and fixing it changes what the program does. Exception-handling, logging, iterator-protocol and return-type rules land here. Explain the behavior delta in the commit body, ideally with a test that would have caught the old behavior.

Ruff distinguishes safe from unsafe fixes. Applying unsafe fixes wholesale is how a lint bump silently changes semantics. Apply the safe set by default; take unsafe fixes one at a time, reviewing each.

## Suppressions are a last resort with a stated reason

A suppression means the rule is wrong about this code or the fix is not worth its cost. Write the reason in the commit body. Prefer a per-file ignore in the configuration to inline suppressions, because it is visible in one place and shows up in review when the policy changes. A rule that fires broadly with no real findings gets one `ignore` entry with a comment.
