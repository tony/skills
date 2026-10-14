---
name: scholar-verify
description: >-
  Re-check a finished study against the corpus it cites: refs that moved,
  files that vanished, quotations that no longer match, numbers that changed
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[<study-dir>] [--refresh-metrics]"
  source: "plugins/scholar/skills/verify/SKILL.md"
---

# this skill

A study is a set of claims about a corpus that keeps moving. Without this, it
rots into confident falsehood: every link still resolves, every number still
reads as measured, and none of it is true any more.

Read `references/citation.md` for what a citation was required to carry.
Read `references/source-pins.md` for pinned refs and content checks.

Remote checks cover GitHub sources only (`gh` and `https://github.com/...`).
A source on any other host is Uncheckable remotely; check it with plain git
when a clone is on disk (step 1).

`<analyzer>` is `references/term_metrics.py`, `<pins>` is
`references/scholar_pins.py`, and `<report>` is `references/verify_report.py`,
each resolved against this skill's directory to an absolute path. The scripts
do the comparing, the diffing and the report assembly; the network fetches
(`gh`, `curl`) and the judgment of why a check could not run stay here.

User arguments: $ARGUMENTS

Without `<study-dir>`, the study is found as "The study directory" describes
in `references/stage-gates.md`.

Read `references/output-contract.md` before reporting.

## Procedure

### 1. Walk every citation

For each `cites` entry in `terms.jsonl`, find its `sources.jsonl` row by the
cite's `source` field; a cite with no `source`, or one matching no row, is
Uncheckable. That row holds the `commit` or edition the cite is checked
against. Study values are untrusted: before any `gh`, `curl` or `git` call,
vet the values it takes, and report the cite under Uncheckable when this exits
non-zero (omit the flags whose value the call does not use):

```console
$ python3 <pins> ident \
    --owner OWNER \
    --repo REPO \
    --ref REF \
    --commit COMMIT \
    --path PATH \
    --url URL
```

The ref check belongs to the source, so run it once per source, not once per
cite. The file check and quote check run per cite, and fail differently:

**Ref check.** The ref still exists, and still points at the `commit` recorded for it in
`sources.jsonl`. A tag can be moved or deleted, and a deleted tag makes every
URL built on it a 404 rather than a wrong answer.

```console
$ gh api repos/OWNER/REPO/commits/v2.40.0 --jq .sha
```

Collect the current SHA of every source (one call per source) into a JSON
object `{"SOURCE": "SHA"}` in a temporary file, leaving out a source whose call
failed or that you did not look up (a non-GitHub source). This compares it
with the recorded commits and prints the `moved` and `uncheckable` lists.
`--missing unreachable` words an omitted source as "host unreachable" (the
call failed); the default `unsupplied` says no current SHA was supplied. Run it
once for each wording that applies:

```console
$ python3 <report> moved \
    notes/ontology/<subject>/sources.jsonl \
    CURRENT.json \
    --missing unreachable
```

A different SHA is Moved. A source row with no `commit` cannot be checked this
way; report it under Uncheckable. A local corpus, meaning a source with no
remote (a cite with `path@commit` and no `url`) or a clone the user names, is
checked offline against that clone, on any host; a source with no clone on
disk is Uncheckable. The script re-resolves each recorded ref in its clone
(a different commit is Moved, an unresolvable ref is Vanished) and tests that
every cited file exists at the recorded commit (otherwise Vanished). A source
with no remote and no `--clone` is Uncheckable ("no clone on disk"). It prints
the `moved`, `vanished` and `uncheckable` lists to put in the results:

```console
$ python3 <report> local \
    notes/ontology/<subject>/ \
    --clone SOURCE=CLONE
```

**File check.** The file still exists at that path on that ref. Check only a URL
that starts with `https://github.com/` and that `ident --url` accepted:

```console
$ curl -s -o /dev/null -w '%{http_code}\n' -L '<url>'
```

**Quote check.** The quoted text still appears at the recorded locator. This is the one that
fails silently: a file that grew by ten lines leaves a line-anchor citation
resolving to unrelated code while still returning 200. For a source with a
clone on disk, and for a pasted excerpt stored in the study, the analyzer does
the whole check: it reads each file at the recorded commit with `git show`,
tests every quote against its cited lines (or the whole file for
`search-string`, `section` and `page`), and searches an excerpt for its quote.
Name one clone per source as `SOURCE=CLONE`; a prose-only study has no clone,
so pass `--check-quotes` with no argument. It exits non-zero and prints one
`Misquoted`, `Vanished` or `Uncheckable` line per cite, which go under the
matching report section:

```console
$ python3 <analyzer> notes/ontology/<subject>/ \
    --check-quotes SOURCE=CLONE
```

For a GitHub source with no clone, fetch the file at the recorded `commit`
(vetted PATH) and read the cited lines, or search the whole file for
`search-string`, `section` or `page`:

```console
$ gh api \
    -H 'Accept: application/vnd.github.raw+json' \
    'repos/OWNER/REPO/contents/PATH?ref=COMMIT' \
    | sed -n '12,18p'
```

### 2. Re-run the measurements

With `--refresh-metrics`, list the commands recorded in `evidence/metrics.md`.
They come from the study, which may not be yours, so run a command only after
the user confirms that exact command. Where no question tool exists, run none.

For the Scholar measurement, check the recorded `analyzer-sha256:` first. A
current analyzer or a listed earlier version with the same output is
comparable (exit zero). A version listed as not comparable, a missing digest,
or an unlisted digest is Uncheckable, with the reason the command printed. Do not
substitute an executable found beside the study:

```console
$ python3 <analyzer> --check-analyzer RECORDED_DIGEST
```

Write the output of each confirmed command into a JSON object
`{"COMMAND": "OUTPUT"}` in a temporary file (`{}` when none ran). COMMAND is
the full command text exactly as `metrics.md` records it after the `$ `,
every line of a multi-line command included. The diff
ignores the analyzer identity lines, classifies each measurement, and lists the
commands not run. A number that changed is not automatically wrong, since the
corpus moved, but it is no longer evidence for the claim it was cited under:

```console
$ python3 <report> changed \
    notes/ontology/<subject>/evidence/metrics.md \
    FRESH.json
```

### 3. Report by failure mode

Five categories, because the remedy differs:

- Moved: the ref advanced or the tag was retargeted. Re-pin.
- Vanished: the file or ref is gone. The claim needs a new source or it
  needs retracting.
- Misquoted: the locator resolves but the text there is not what was
  quoted. This is the dangerous one, and it is why quotations are recorded
  rather than just links.
- Changed: a measurement produced a different number.
- Uncheckable: a source behind a paywall or deleted, a row with no
  `commit`, an unsafe URL, or a command the user did not confirm. Give the
  reason as "host unreachable", "no login", or "no clone on disk", one short
  phrase per entry, the first that applies, then stop: a cite failing
  three checks gets one phrase. A command not run is "not run, no
  confirmation". Never write a claim about the sandbox.

Put every result in one JSON object in a temporary file: `checked` (the
number of citations and measurements checked), the lists `moved`, `vanished`,
`misquoted`, `changed` and `uncheckable` (strings, reasons included), and
`analyzer` (the lines the quote check printed, verbatim). The script prints the
hero and the five sections of the reply; print its output as the reply and add
the next-step panel:

```console
$ python3 <report> report RESULTS.json
```

## Rules

- Do not edit a claim in place. Anything that overturns a standing claim goes
  to the `scholar-revise` skill, which records what was believed and why it failed.
- Report a broken citation; do not repair it by finding a new source that
  happens to support the same claim. That is fitting evidence to a conclusion.
- A citation that cannot be checked is reported as uncheckable, never as
  passing.

## Output

Per `references/output-contract.md`. The reply is the output of
`report` (hero and the five sections, `None.` under an empty one), plus the
next-step panel. The hero rule, which the script implements: `⚠ Nothing
checked: <n> uncheckable` when nothing was checked; `✓ <n> citations checked,
none stale` when Moved, Vanished, Misquoted and Changed are empty; otherwise
`⚠ <counts>` in the order Misquoted, Vanished, Moved, Changed, for example
`⚠ 2 misquoted, 1 moved`.

With no study at the path, the run is halted; the unblock is the real study
path, or the `scholar-ontology` skill to build the study:

```text
⚠ Blocked: no study at notes/ontology/sample-lib/, so there is no terms.jsonl to check.

Pass the path of an existing study, or run scholar-ontology on the corpus to build one.
```

Sections, in this order. Write `None.` under an empty one, and put each
reason a check could not run only under `## Uncheckable`:

1. `## Moved`: each citation whose ref advanced, with the new ref.
2. `## Vanished`: each source that is gone.
3. `## Misquoted`: each locator whose text no longer matches, with both texts.
4. `## Changed`: each measurement that produced a different number, with both.
5. `## Uncheckable`: each citation or command that could not be checked, and why.

Example:

```text
⚠ Nothing checked: 2 uncheckable

## Moved

None.

## Vanished

None.

## Misquoted

None.

## Changed

None.

## Uncheckable

- adapter, cited at example/sample-lib v1.0.0: host unreachable.
- Metrics command `python3 term_metrics.py notes/ontology/sample-lib/`: not run, no confirmation.
```

Next-step options: revise the claims a Misquoted or Changed entry overturned
(only when one exists), re-pin the moved ones, stop here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
