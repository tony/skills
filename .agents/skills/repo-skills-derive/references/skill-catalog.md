# Skill catalog

The categories this skill weighs, the evidence each needs,
and what each skill must hold. A category is a question to answer with
evidence, not a file to write by default.

## Contents

- Weighing evidence
- Setup
- Architecture
- Style
- Gates
- Dependencies
- Review
- Commits and pull requests
- Live checks
- Doc checks
- Repository-specific skills
- Usually skipped

## Weighing evidence

Count sessions as well as commits: setup, pull requests, and reading
docs leave few commits but recur across sessions. A category with
neither commits nor sessions behind it is skipped. A category skipped
because a document already covers it needs that document checked
against the tree first.

Each skill owns one task. Its description names the task in the user's
words; its body holds what an agent got wrong without it.

## Setup

Evidence: environment work in transcripts (version managers, installs,
worktrees, missing generated files) or a stale setup section.

Holds: the checkout or worktree convention, how each toolchain pin
resolves (verify the mechanism, not only the version), large-file or
submodule fetches, the install, browsers or system packages, generated
files a fresh checkout lacks, network needs, and the session tooling.
Invoked by name only: `disable-model-invocation: true`.

## Architecture

Evidence: more than one package, more than one runtime path, generated
code, or prompts asking how something works.

Holds: package boundaries and dependency direction, the main runtime
flows, the checklist for adding the repository's most common unit (a
route, a command, a module), parts the docs describe that the code
lacks, and where upstream sources are read.

## Style

Evidence: conventions spread across long files, or baselines that write
code against outdated versions.

Holds: which section governs each kind of code, the example file that
shows them together, test locations and helpers, import rules, and
which installed version wins over prose.

## Gates

Evidence: a CI workflow or documented checks. Nearly always.

Holds: the order to run them, which CI enforces and which are local,
how to tell a new failure from one the trunk shares (run the gate on the
trunk in a separate worktree, including any generated files it needs),
and where each failing gate points.

## Dependencies

Evidence: dependency commits as a large share of history, release
cooldowns, held or pinned packages, or prompts about updates.

Holds: the policy files and their holds, finding what is out of date,
taking compatible bumps, bumping a held tool by measuring unchanged
output, lockfile-only refreshes, multi-package upgrades, bisecting a bad
bump, and the commit forms.

## Review

Evidence: always, once other skills exist.

Holds: report and stop without editing, the repository's checks keyed
to the file that owns each, the rule that each finding names its
breaking input or its rule, and a fixed report shape with an empty
result sentence.

## Commits and pull requests

Evidence: merge commits or pull requests in history, or prompts about
merging, CI, or deploys.

Holds: what lands on the trunk directly and what goes through a pull
request, the merge method and merge subject measured from history,
whether a push deploys, branch cleanup, and watching CI and the deploy.

## Live checks

Evidence: the repository runs something: an app, a service, a CLI with
state.

Holds: finding the running instance rather than starting a second one,
the entry points worth checking, debug toggles, how to switch modes the
way a user does, environment limits that fake a failure, and comparing
against production.

## Doc checks

Evidence: conventions files with claims about commands, versions,
ports, or gate results. Nearly always.

Holds: listing every claim line by line, the source of truth for each
kind, running a claim that a command settles in seconds, and a report
whose first sentence counts claims checked, wrong, and unverified.

## Repository-specific skills

Evidence: one request recurring in at least three sessions with no
category above owning it, such as porting changes from a sibling
repository or rebuilding an asset pipeline.

Holds: the steps the transcripts show, the name and number mappings the
agent got wrong, and how the result is credited in the commit.

## Usually skipped

Builders, sample creators, unit guides, and design documents. Write one
only when the repository has the tree it would write into and sessions
asked for it. A builder's checklist usually belongs in architecture.
