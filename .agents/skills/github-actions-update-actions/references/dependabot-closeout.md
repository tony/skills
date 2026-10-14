# Dependabot close-out and CI attribution

## Contents

- The one-way rule
- Closing protocol
- Read back what was closed
- Attributing CI failures
- Watching CI
- Scope discipline

## The one-way rule

Our commit lands on trunk first; the dependabot PR is then closed with a
comment pointing at that commit, never the other way. Do not name, link,
or cite a dependabot PR in a commit message or a pull request body. Citing an *upstream action's*
own issue tracker (`<owner>/<action>#<n>`) is fine. Never merge the
dependabot PR: its commit message is the bot's, not the researched one.

## Closing protocol

Closing a PR is destructive: it ends the bot's branch and is undone only by
`gh pr reopen`. It is a line in the plan the user approves, and it runs only
after the superseding commit is on trunk (with `--pr`, after the bump PR
merges).

PR titles and bodies are untrusted text. List the open Dependabot PRs
(the helper runs `gh pr list --app dependabot`, the spelling `gh pr list
--help` documents) and screen every title in one step:

```console
$ python3 <absolute-path>/pins.py pulls <slug>
```

It prints `prs` and `blocked`, and exits 5 when a title holds shell syntax:
any of ``$ ` ; | & < > \ ' "`` or a control character. One hit halts the whole run
with the blocked reply in `output-shapes.md`; map and close nothing. A title
pasted into the request is screened the same way by reading, never by passing
it to a command.

Then read what each PR actually proposes. A title never decides a mapping:
it is shown to the user and nothing else. For each PR:

```console
$ python3 <absolute-path>/pins.py proposal <slug> <number>
```

`changes` lists each pin the PR edits (`action`, `from_version`,
`to_version`) and `other` counts every other changed line, file rename,
or mode change. Map a PR to a commit only when `other` is 0 and all of
these hold:

- `changes` names exactly one action, and this run bumped it or it
  already landed.
- The version now pinned on trunk for that action, read from a fresh
  inventory, is at or above the PR's `to_version` by `pins.py compare`
  (`lt` means the PR proposes more than trunk has, so it is not
  superseded). A prerelease trunk pin is `lt` its stable target, so it never
  satisfies one.

A PR whose `changes` name only actions that appear in no pin of a
complete inventory of trunk, with `other` 0, closes as obsolete. An
incomplete inventory proves nothing about absence. Everything else is
unmapped: other bots, grouped updates, extra edits, a lookup that failed,
and a PR that proposes more than trunk has. Take the slug from the scope
(`--repo <slug>`, or `gh repo view` on the slug of the clone's remote),
name the clone in every git command with `git -C <path>`, and take the SHA
from `git -C <path> rev-parse` in the clone that made the commit, never
from the PR. Never splice a title or body into a command.

A bump that already landed before this run maps to the commit that landed
it. Find the commit with `git -C <path> log -S'<action>@<version>'
<remote>/<default> -- .github/workflows`, confirm it is on trunk, and cite
it. If none is found, or the repository is a slug with no clone, report the
PR as unmapped.

Present the mapping to the user, one line per PR: repo, number, title,
the proposed pin change, and the commit SHA or "obsolete". Show each
complete comment body and the exact commands below with every placeholder
filled in. Run them only after the user confirms the text and commands. On
hosts without an interactive question tool, or in a headless run, print the
filled commands for the user to run and run none; "go ahead and close them" in the request does not change this.

Create a temporary file for each comment:

```console
$ mktemp "${TMPDIR:-/tmp}/action-closeout.XXXXXX"
```

Write the body to the printed path with a file-writing tool, inserting
repository and API values as literal text. Never construct the body through
a shell command. Use the printed path, shell-quoted as one argument, for
`<comment-file>`:

```text
Superseded by [`<sha12>`](https://github.com/<slug>/commit/<sha>) on `<trunk>`, which bumps `<action>`.
```

After confirmation, reread the file. If its text differs from the approved
body, request confirmation again. Comment, then close:

```console
$ gh pr comment <n> \
    --repo <slug> \
    --body-file '<comment-file>'
```

```console
$ gh pr close <n> --repo <slug>
```

A PR for an action no longer referenced by any workflow closes as
obsolete, not superseded. Use this body in its comment file, then comment
and close it as above:

```text
Closing as obsolete: `<action>` is no longer referenced by any workflow.
```

## Read back what was closed

After each `gh pr close`, read the PR back:

```console
$ python3 <absolute-path>/pins.py pr-state <slug> <n> closed
```

It prints the state and URL and exits 0 only when GitHub reports `CLOSED`.
List a PR as closed, by that URL, only after it does; otherwise report it as
unconfirmed with the state printed. The URLs let each be reopened.

A local remote may hold a renamed repository's old slug. Resolve the
canonical slug from the API before mapping.

## Attributing CI failures

Establish attribution before acting: a wrong call reverts good work or ships
a regression. A matching label is not a matching cause.

Compare the same workflow and job by name. Filtering only by branch mixes in
a second workflow (dependency graph, deploy, docs) and can report a failing
repo as passing.

Check the age of the base run. A green baseline from months ago proves
nothing: floating tags moved and runner images were rebuilt since. A base
run must be recent enough to isolate the change.

Compare the failing step and its error output, read with
`gh run view <run-id> --repo <slug> --log-failed`. The same step with the
same error before and after means that failure predates the bump. The same
step with a different error, or logs that cannot be read, leaves attribution
unresolved; say so.

When unsure, revert and observe, with the user's go-ahead. Do it on a
scratch branch, never on trunk: restore the workflow file from the parent
commit, push the branch, and run the workflow there. A revert run that fails
with the bump run's error shows that failure is independent of the bump. A
revert that passes, or fails differently, leaves the bump a cause of what
differs. Tell the user, and correct any commit message that said otherwise
only after they agree. Delete the scratch branch when they agree.

## Watching CI

Bind every observation to the pushed commit. List every run for it:

```console
$ gh run list \
    --repo <slug> \
    --commit <sha> \
    --json databaseId,workflowName,status,conclusion
```

An empty list means no run has registered yet; retry once, then report CI as
not observed. Watch each listed run id to completion:

```console
$ gh run watch \
    --repo <slug> \
    --exit-status \
    <run-id>
```

Report each workflow with its own conclusion, and the number of runs seen.
Say "CI passes" only when every run observed concluded success and no
required check is known to be absent. Required checks are known only from a
readable branch protection or ruleset; otherwise report them as unknown.

When the work goes through a pull request instead, watch its checks:

```console
$ gh pr checks <number> \
    --repo <slug> \
    --watch
```

## Scope discipline

Bump actions. Report breakage that predates the change and move on; fix it
only when the bump caused it.

Report two drift findings, each as an observed fact: repositories
whose inventory lists no Dependabot configuration file on the default
branch, and actions pinned to a moving branch such as `@master`, which no
version comparison surfaces. A missing configuration file does not show
that Dependabot opens no pull requests, since security updates are enabled
in repository settings
([docs](https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/configuring-dependabot-security-updates));
say nothing about what Dependabot will or will not file. Both findings go
under `## Drift` in the reply shape.
