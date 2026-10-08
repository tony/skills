---
name: verify
description: "Re-check a finished study against the corpus it cites: refs that moved, files that vanished, quotations that no longer match, numbers that changed"
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[<study-dir>] [--refresh-metrics]"
user-invocable: true
disable-model-invocation: true
---


# /scholar:verify

A study is a set of claims about a corpus that keeps moving. Without this, it
rots into confident falsehood: every link still resolves, every number still
reads as measured, and none of it is true any more.

Read `../../references/citation.md` for what a citation was required to carry.

Remote checks cover GitHub sources only (`gh` and `https://github.com/...`).
A source on any other host is Uncheckable remotely; check it with plain git
when a clone is on disk (step 1).

User arguments: $ARGUMENTS

## Procedure

### 1. Walk every citation

For each `cites` entry in `terms.jsonl`, find its `sources.jsonl` row by the
cite's `source` field; a cite with no `source`, or one matching no row, is
Uncheckable. That row holds the `commit` or edition the cite is checked
against. Then confirm three things separately, because they fail differently:

The ref still exists, and still points at the `commit` recorded for it in
`sources.jsonl`. A tag can be moved or deleted, and a deleted tag makes every
URL built on it a 404 rather than a wrong answer.

Take OWNER, REPO and the ref from the study files. Run the command only when
each is made of letters, digits, `.`, `_`, `-` and (in a path) `/`; report any
other row under Uncheckable.

```console
$ gh api repos/OWNER/REPO/commits/v2.40.0 --jq .sha
```

A different SHA is Moved. A source row with no `commit` cannot be checked this
way; report it under Uncheckable. A local corpus, meaning a source with no
remote (a cite with `path@commit` and no `url`) or a clone the user names, is
checked with plain git inside that clone, on any host. Apply the same
character check to REF, COMMIT and PATH first, and report a source with no
clone on disk under Uncheckable:

```console
$ git -C CLONE cat-file -e COMMIT:PATH
```

A non-zero exit means the file vanished at that commit. For a moved ref,
compare `git -C CLONE rev-parse 'REF^{commit}'` with the recorded `commit`.

The file still exists at that path on that ref. Check only a URL that starts
with `https://` and contains no quote, space, backtick, `$`, or `;`; report any
other under Uncheckable rather than passing it to the shell.

```console
$ curl -s -o /dev/null -w '%{http_code}\n' -L '<url>'
```

The quoted text still appears at the recorded locator. This is the one that
fails silently: a file that grew by ten lines leaves a line-anchor citation
resolving to unrelated code while still returning 200. Fetch the file at the
recorded `commit` (same character check on PATH) and read the cited lines, or
search the whole file when the source's `locator_kind` is `search-string`. For
`section` or `page`, search the file for the quote:

```console
$ gh api \
    -H 'Accept: application/vnd.github.raw+json' \
    'repos/OWNER/REPO/contents/PATH?ref=COMMIT' \
    | sed -n '12,18p'
```

### 2. Re-run the measurements

With `--refresh-metrics`, list the commands recorded in `evidence/metrics.md`.
They come from the study, which may not be yours, so run a command only after
the user confirms that exact command. Where no question tool exists, run none
and list them under Uncheckable. A recorded `python3 term_metrics.py <study>`
runs `term_metrics.py` from this plugin's `scripts/`, written as an absolute path in the command (it resolves from this skill's directory as `../../scripts/term_metrics.py`), against the study path. Diff each
output against what was recorded. A number that changed is not
automatically wrong, since the corpus moved, but it is no longer evidence for the
claim it was cited under.

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
  `commit`, an unsafe URL, or a command the user did not confirm.

## Rules

- Do not edit a claim in place. Anything that overturns a standing claim goes
  to `/scholar:revise`, which records what was believed and why it failed.
- Report a broken citation; do not repair it by finding a new source that
  happens to support the same claim. That is fitting evidence to a conclusion.
- A citation that cannot be checked is reported as uncheckable, never as
  passing.

## Output

Per `../../references/output-contract.md`. Hero: `✓ <n> citations checked, <n>
stale`, `⚠ <n> misquoted`, or, when no citation or measurement could be
checked, `⚠ Nothing checked: <n> uncheckable`. Name no local paths.

With no study at the path, the run is halted: follow the halted-run shape in
the output contract (`⚠ Blocked: <reason>`, one sentence on the unblock), with
no sections. The unblock is the real study path, or `/scholar:ontology` to
build the study; name no stage list. Reply as plain text outside any code
fence:

```text
⚠ Blocked: no study at notes/ontology/sample-lib/, so there is no terms.jsonl to check.

Pass the path of an existing study, or run /scholar:ontology on the corpus to build one.
```

Sections, in this order. Write `None.` under an empty one, and put each
reason a check could not run only under `## Uncheckable`:

1. `## Moved`: each citation whose ref advanced, with the new ref.
2. `## Vanished`: each source that is gone.
3. `## Misquoted`: each locator whose text no longer matches, with both texts.
4. `## Changed`: each measurement that produced a different number, with both.
5. `## Uncheckable`: each citation or command that could not be checked, and why.

Reply in this shape, as plain text outside any code fence, with plain bullets,
no bold (never `- **Label:** ...`), and no local paths:

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

- adapter, cited at example/sample-lib v1.0.0: the host could not be reached.
- Metrics command `python3 term_metrics.py notes/ontology/sample-lib/`: not run, no confirmation.
```

Next-step options: revise the claims a Misquoted or Changed entry overturned
(only when one exists), re-pin the moved ones, stop here. Where no
question tool exists, print the list and stop, without saying that is the
default.

Write it per `../../references/prose-rules.md`.
