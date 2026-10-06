---
name: package-updater-updating-packages
description: >-
  Use when packages are out of date across repos; bump dependencies, refresh
  uv.lock, update .tool-versions/packageManager pins, and commit each.
metadata:
  source: "plugins/package-updater/skills/updating-packages/SKILL.md"
---

# Updating packages

Find what is actually out of date, research each move against the
vendor's own release notes, and land it as commits that separate the
toolchain from the dependencies from their fallout.

References:

- `references/repo-scope.md` — scope flags, which repositories
  are yours to commit to, and when to stop and ask.
- `references/ecosystems.md` — per-ecosystem detection, discovery
  and apply commands, and the supply-chain cooldown, including the
  exemption protocol.
- `references/commit-conventions.md` — commit tracks, subject
  grammar, body anatomy, and the empty-body rule.
- `references/upstream-links.md` — which URLs each tool's bump
  cites, and how to verify them.
- `references/follow-ups.md` — which bumps need a second commit,
  and how to declare a knowingly-red intermediate.
- `references/holds.md` — staying behind on a package on purpose,
  and releasing the hold.

## Never run cargo-outdated

It allocates around 18 GB resident and the OOM killer takes the whole
host down with it on a memory-constrained machine. The cost is paid by
starting the process, so there is no safe probe: do not run it to check
whether the problem still reproduces, and do not offer it as an option.

`cargo update --dry-run` reports the same thing safely. This holds until
the user explicitly lifts the restriction.

## Core principle

A dependency commit's value is its reasoning, and reasoning does not
survive bundling. Keep the toolchain, the named bumps, the bulk refresh,
and the fallout in separate commits, and each one reverts on its own
years later when someone needs exactly that.

## Scope

Repositories the user maintains. Follow `references/repo-scope.md`
before any sweep that walks a directory; it owns the fork, ownership and
ask-first rules.

Three dependency classes belong to sibling plugins. Report them as
findings with the command that handles them, and do not do the work:

- GitHub Actions `uses:` pins → the `github-actions-update-actions` skill
- ruff's floor and the rule fallout it produces → the `ruff-bump` skill
- Terraform versions, providers and lock files →
  the `terraform-bump-provider` skill, the `terraform-bump-terraform` skill,
  the `terraform-refresh-lock` skill

## Phase 1 — Inventory

Detect ecosystems by the files present, per the ecosystems reference. A
repository can carry several, and each updates on its own track.

Read pins from the default branch rather than the working tree. A
checkout parked on a feature branch reports pins the branch that ships
does not have.

Record, per repository: the ecosystems found, every manifest and
lockfile, every toolchain pin file, the project's declared quality-check
commands, and any cooldown configuration. That inventory is the unit of
work for everything after this.

## Phase 2 — Discover what is outdated

Run each ecosystem's discovery command. Prefer the project's own wrapper
— a `justfile` target, a `package.json` script — over the raw command,
because the wrapper is the maintained path.

**Check the cooldown before calling anything current.** A release
published inside the window is invisible to the resolver, so a tree that
looks up to date may only be gated. Report gated releases separately
from current ones, with the date each becomes visible.

Separate what moves in-range from what needs a manifest edit. They are
different commits with different meanings, and conflating them at
discovery time makes the plan wrong.

**Audit the existing holds in the same pass.** Every `reject` entry in
every config in the tree, not just the root one, per the holds
reference. A hold whose condition has been met is released in this run;
a hold with no recoverable reason is reported for the user to decide.
Packages held back are the ones a sweep is most likely to report as
current when they are merely hidden.

## Phase 3 — Research each move

A bulk lockfile refresh needs no research; it gets an empty body and
carries no claims. Everything else does.

For each named package and each toolchain pin: read the release notes
for every version in the span, work out what the change means for *this*
repository, and collect the links per the upstream-links reference.
Verify every URL resolves before it reaches a commit body.

Predict the follow-ups now rather than discovering them after a test
run. The follow-ups reference lists which bumps carry one.

Where the host supports it, dispatch one researcher per package or
upgrade chain — they are independent, and repositories sharing a chain
share the research.

Intersect the research with the repository before writing anything. A
release note describes the package; only the repository can say whether
the change reaches it. A general claim written into a body it does not
fit is false in that repository's history permanently.

Research owes two products, and both belong in the commit rather than
only in the session report: the headline changes across the span, named
release by release; and what those changes reach here. Prove the
intersection instead of asserting it — a resolver or lockfile check, a
search for the input format a release now rejects, the test lane that
exercises the changed code path. The proof is the difference between
"reviewed and inert" and "assumed inert", and it is cheap enough to run
before the plan rather than after the commit.

## Orchestration Plan

Before any file is written, enter plan mode — `EnterPlanMode` in Claude
Code, `/plan` or `Shift+Tab` in Cursor, Codex, and Gemini — and present
a plan covering:

- Which repositories and ecosystems are in scope, and what was excluded
  as a fork, unowned, already current, or gated by cooldown.
- Every move, grouped into the four commit tracks, in landing order.
- Which packages earn their own commit and why; which fall into the bulk
  refresh.
- The follow-up commits expected, and any bump that will leave the tree
  red until its follow-up lands.
- Where commits land: the default branch directly, or a branch and pull
  request, and whether an issue or card is created first.
- How many commits this produces, and whether they will be pushed.
- The quality-check commands this project actually declares.

Present it and wait for approval. Exit plan mode before Phase 4.

If plan mode is unavailable, the phase structure still applies: finish
inventory, discovery and research, and confirm scope with the user
before writing anything.

## Phase 4 — Land, in order

Follow the commit-conventions reference for subject and body, and write
each message per `references/prose-rules.md`. Write multi-line
messages through a heredoc or a file, never as a multi-line `-m`
argument.

The four tracks land in this order within a repository:

1. **Toolchain and runtime** — `.tool-versions`, `.nvmrc`,
   `.python-version`. One tool per commit, even when one edit moves
   three. Link every release in each tool's span.
2. **Package manager and engines** — `packageManager`, `engines`. Never
   mixed with dependencies.
3. **Named package bumps** — one per package, or per release train when
   the body can say why they are coupled.
4. **Bulk lockfile refresh** — empty body.

A follow-up (config schema, snapshots, migrations) lands immediately
after the bump it belongs to, as its own commit.

A hold added or released is its own commit too, naming the condition
that started or ended it. Releasing a hold comes before the bump it
unblocks.

Toolchain first is not arbitrary: those pins select the resolver that
produces everything below them.

A repository parked on a feature branch gets a throwaway worktree based
on the remote default branch, not the local one, which may be stale and
will be rejected as a non-fast-forward after the work is done.

Make the run resumable. Push whenever the local branch is ahead of the
remote, rather than only when this invocation created the commits, so an
interrupted run can be re-invoked without hand repair.

### Trunk or a pull request

Routine dependency work lands on the default branch. A pull request is
for the bumps whose consequences reach past the repository: a first-party
sibling package a downstream project consumes, a linter or type-checker
floor that changes what CI accepts, or a supported-runtime constraint.

Follow the project's documented branch naming; otherwise read its
existing branch names before inventing a scheme.

A sibling bump PR usually carries a second commit: the changelog entry
for the bump, following that repository's own changelog conventions.

### When an issue or card comes first

When the user asks for the outstanding work to be filed before it is
done, the order is: finish the audit, create the issue or card from it,
derive the branch name from what was created, then work on that branch.

Detect the tracker at runtime rather than assuming one. Linear through
its MCP tools or CLI if either is present; GitHub through `gh`. Linear
supplies its own branch name — use it verbatim. For a GitHub issue,
derive `<number>-<slug>`.

The pull request references the issue. The commits do not: an issue
number means nothing to a reader a year later, and may not exist when
the commit is written.

## Phase 5 — Verify

Run the project's own quality checks after each commit — the lint,
format, type-check and test commands its `AGENTS.md`, `CLAUDE.md`,
`justfile`, or CI workflow declares. Never substitute assumed commands.

When a check fails, establish whether it fails on the default branch too
before attributing it to a bump. Pre-existing failures are reported as
pre-existing, not fixed and not concealed.

A bump that is knowingly red until its follow-up is not a failure — but
the body must have said so, and the follow-up must land before the run
is reported complete. Never report green without having read the output
that says so.

## Phase 6 — Report

Say what moved, what was deliberately held, and what belongs to a
sibling plugin, per `references/prose-rules.md`. Two findings explain most drift and are worth surfacing
every run: pins that disagree with each other across a workspace, and
packages held back with no recorded reason.

## Common mistakes

**Trusting one discovery tool to see every pin.** `ncu` reads
`package.json` and nothing else, so catalog entries, overrides and
`.ncurc` holds are invisible to it. A clean report is not a current
tree.

**Regenerating a snapshot without reading why it moved.** That records a
regression as the new expected value.

**A cooldown exemption that outlives its reason.** Follow the exemption
protocol in the ecosystems reference and revert it when the block
lapses.


## Portability notes

- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
