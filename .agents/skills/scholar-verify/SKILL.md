---
name: scholar-verify
description: >-
  Re-check a finished study against the corpus it cites — refs that moved,
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

User arguments: $ARGUMENTS

## Procedure

### 1. Walk every citation

For each `cites` entry in `terms.jsonl`, confirm three things separately,
because they fail differently:

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
way; report it under Uncheckable.

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
search the whole file when the source's `locator_kind` is `search-string`:

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
and list them under Uncheckable. Diff each output against what was recorded. A number that changed is not
automatically wrong, since the corpus moved, but it is no longer evidence for the
claim it was cited under.

### 3. Report by failure mode

Five categories, because the remedy differs:

- **Moved** — the ref advanced or the tag was retargeted. Re-pin.
- **Vanished** — the file or ref is gone. The claim needs a new source or it
  needs retracting.
- **Misquoted** — the locator resolves but the text there is not what was
  quoted. This is the dangerous one, and it is why quotations are recorded
  rather than just links.
- **Changed** — a measurement produced a different number.
- **Uncheckable** — a source behind a paywall or deleted, a row with no
  `commit`, an unsafe URL, or a command the user did not confirm.

## Rules

- Do not edit a claim in place. Anything that overturns a standing claim goes
  to the `scholar-revise` skill, which records what was believed and why it failed.
- Report a broken citation; do not repair it by finding a new source that
  happens to support the same claim. That is fitting evidence to a conclusion.
- A citation that cannot be checked is reported as uncheckable, never as
  passing.

## Output

Per `references/output-contract.md`. Hero: `✓ <n> citations checked, <n>
stale` or `⚠ <n> misquoted`. Name no local paths. With no study at the path, the run is halted: follow the
halted-run shape in the output contract (`⚠ Blocked: <reason>`, one sentence
on the unblock: the real study path, or the stage that builds the study), with
no sections. Sections:

1. `## Moved` — each citation whose ref advanced, with the new ref.
2. `## Vanished` — each source that is gone.
3. `## Misquoted` — each locator whose text no longer matches, with both texts.
4. `## Changed` — each measurement that produced a different number, with both.
5. `## Uncheckable` — each citation or command that could not be checked, and why.

Next-step options: revise the overturned claims, re-pin the moved ones, stop
here.

Write it per `references/prose-rules.md`.


## Portability notes

- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
