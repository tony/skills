# Stopped run

Read this file in full when a run stops before any change lands. A plan
awaiting approval is not a halt: present its plan. A failed check after a
commit is a result: report the landed commits and failed check.

Write the stopped reply as plain text, with no enclosing fence or bold:

1. `⚠ Stopped: nothing was changed.` followed on the same line by one
   sentence naming the fact the user must resolve, with no first-person
   subject ("Ownership of X could not be confirmed", never "I couldn't
   confirm").
2. `To continue:` and a plain list of available actions. Use a question
   tool when available; otherwise list the options and take none.

Nothing precedes the stop line, separates it from the options, or follows
the options. No headings, second reason, plan, recap, or promise of later
work. Options name user actions, not commands that failed or future steps
the assistant promises to take.

## Contents

- State the evidence
- Examples for unconfirmed ownership, unreadable notes, a held package,
  an unreadable fact, a rolling cooldown and a fixed cutoff

## State the evidence

- Unreadable release history or notes: say only that the notes for the
  named package and version span could not be read. Unread is not absent.
  Do not enumerate unverified intermediate releases or explain why a
  version crossing triggers the stop.
- Unconfirmed version: name the package and version that could not be
  confirmed as published. Do not infer an alternative from memory.
- Cooldown: for a rolling window give the publication day, window, and
  eligible day; for a fixed cutoff give the publication day and the
  cutoff day, since waiting does not lift it. No time of day, and no
  configuration file or key.
- Hold: name the package, held version, and recorded reason.
- Unreadable repository fact: name the repository and the fact (status,
  default branch, a pin file) that could not be read.
- Scope or ownership: give the unresolved repository or fork relationship,
  not an inventory of remotes, history, credentials, or lookup attempts.
- No manifest or pin file: say that none was found in the selected scope.

Exclude local absolute paths, host configuration, sandbox details,
deliberately omitted output, and narration of the skill's rules. The
reason is the only fact outside the options.

## Examples

For unconfirmed ownership, name the repository without narrating the
failed lookup or commit-author history:

```text
⚠ Stopped: nothing was changed. Ownership of <repository> could not be confirmed.

To continue:

- Confirm that you maintain this repository.
- Choose another repository.
- Stop here.
```

For unreadable notes, substitute only the verified package and endpoints:

```text
⚠ Stopped: nothing was changed. The release notes for <package> <current> to <target> could not be read.

To continue:

- Paste the notes, or point to where they live.
- Commit with verified release links and a reason stating that the notes were unread.
- Skip this package.
- Stop here.
```

For a held package, substitute the recorded package, version and reason:

```text
⚠ Stopped: nothing was changed. <package> is held at <version>: <recorded reason>.

To continue:

- Release the hold.
- Stop here.
```

For an unreadable fact, name only the repository and the fact:

```text
⚠ Stopped: nothing was changed. The <fact> of <repository> could not be read.

To continue:

- Fix access to the repository and rerun.
- Skip this repository.
- Stop here.
```

For a rolling cooldown, substitute the observed publication day and the end
`plan_rules.py lapse` computes (see "Supply-chain cooldown" in
`ecosystems.md`):

```text
⚠ Stopped: nothing was changed. <package> <version> was published <day> and the <N>-day cooldown hides it until <eligible day>.

To continue:

- Wait until then and rerun.
- Exempt this package from the cooldown for this release.
- Stop here.
```

For a fixed cutoff, the options drop waiting:

```text
⚠ Stopped: nothing was changed. <package> <version> was published <day>, after the <cutoff day> cooldown cutoff.

To continue:

- Move the cutoff past <day>.
- Exempt this package from the cooldown for this release.
- Stop here.
```
