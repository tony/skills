# Stopped run

Read this file in full when a run stops before any change lands. A plan
awaiting approval is not a halt: present its plan. A failed check after a
commit is a result: report the landed commits and failed check.

Write the stopped reply as plain text, with no enclosing fence or bold:

1. `⚠ Stopped: nothing was changed.` followed on the same line by one
   sentence naming the fact the user must resolve.
2. `To continue:` and a plain list of available actions. Use a question
   tool when available; otherwise list the options and take none.

Nothing precedes the stop line, separates it from the options, or follows
the options. No headings, second reason, plan, recap, or promise of later
work. Options name user actions, not commands that failed or future steps
the assistant promises to take.

## State the evidence

- Unreadable release history or notes: say only that the notes for the
  named package and version span could not be read. Unread is not absent.
  Do not enumerate unverified intermediate releases or explain why a
  version crossing triggers the stop.
- Unconfirmed version: name the package and version that could not be
  confirmed as published. Do not infer an alternative from memory.
- Cooldown: give the publication day, window, and eligible day, without a
  time of day or the configuration file or key that sets the window.
- Hold: name the package, held version, and recorded reason.
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

For a cooldown, substitute the observed publication day and computed end:

```text
⚠ Stopped: nothing was changed. <package> <version> was published <day> and the <N>-day cooldown hides it until <eligible day>.

To continue:

- Wait until then and rerun.
- Exempt this package from the cooldown for this release.
- Stop here.
```
