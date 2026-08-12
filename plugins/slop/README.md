# slop

Scan tracked files for AI slop and verbose noise, resolving each finding
with atomic, verified commits.

For branch-scoped slop cleanup that uses fixup commits and
`git rebase -i --autosquash`, see the sibling `pr` plugin's
`/pr:deslop` skill.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install slop@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add slop@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/slop:scan` | `slop:scan` | Scan tracked files at HEAD for slop; land one atomic commit per finding with quality-gate verification. |

## How It Works

### `/slop:scan` — Repo-wide slop scanner

1. **Snapshot state and lock baseline** — Detect trunk, lock absolute
   SHA, refuse dirty tree (unless `--allow-dirty`), detached HEAD, or
   in-progress rebase.
2. **Resolve scope** — Filter via `--paths=<glob>`. Use
   `--with-history=N` for advisory historical scanning.
3. **Discover quality gates** — Parse `AGENTS.md` / `CLAUDE.md` /
   `.github/CONTRIBUTING.md` for formatting, linting, type-checking,
   and test commands.
4. **Calibrate tone against trunk** — Analyze last 50 commits on
   `origin/<trunk>` to reduce false-positive Tier C signals.
5. **Detect (hybrid)** — Run Pass A regex. Run Pass B `Task` sub-agent
   (skip with `--no-semantic`) for semantic verification.
6. **Materialize patch series** — Write numbered patches and
   `commits.json` to `.git/slop-scan/<ts>-<pid>/` for review.
7. **Per-finding commit loop (`--apply`)** — Apply edit, stage explicit
   paths, run quality gates (tests opt-in via `--run-tests`), and
   commit. On gate failure: rollback and continue (configurable via
   `--on-fail`).

Result: N individual, forward-going, revertable commits per finding.

## Arguments

Audit the repo without applying anything (the default):

```
/slop:scan
```

Scope to a subdirectory:

```
/slop:scan --paths='src/**'
```

Include historical commits in the scan (advisory-only findings):

```
/slop:scan --with-history=50
```

Apply the per-finding commit loop:

```
/slop:scan --apply
```

Apply with the strict budget (only Tier A auto-applies; Tier B becomes
advisory):

```
/slop:scan --apply --budget=strict
```

Stop on the first gate failure instead of skipping:

```
/slop:scan --apply --on-fail=stop
```

Run tests as part of every per-finding commit's gates (slow on large
runs):

```
/slop:scan --apply --run-tests
```

## Safety

- **No history rewrites** — Every change is a forward-going commit.
- **No pushing** — User runs `git push` after review.
- **Explicit staging** — Stages explicit paths only; never `git add -A`.
- **Enforces hooks** — Project pre-commit/commit-msg hooks are
  respected.
- **Gate-failed rollback** — Reverts files on formatter/linter rejection
  and proceeds.
- **Audit-first default** — Writes a patch series for review without
  `--apply`.
- **Tier C calibration** — Subjective tone is advisory and calibrated
  against the project's voice.

## Prerequisites

- **git**
- **Formatter / linter / type-checker** — Discovered at runtime.

## Boundary with `/pr:deslop`

| Skill | Scope | Action shape |
|---|---|---|
| `/pr:deslop` | Branch commits since trunk (diffs + commit messages) | Fixup commits + autosquash (rewrites history) |
| `/slop:scan` | Tracked files at HEAD (optional advisory history scan) | Forward-going atomic commits, one per finding |

Both share the signature registry, quality-gate discovery, and
tone-calibration algorithm. They differ only in how findings are
resolved.
