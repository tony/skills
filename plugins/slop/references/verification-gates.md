<!-- Vendored from shared/verification-gates.md; edit that file, then run 'scripts/marketplace.py portable'. -->
# Verification-Gate & CI Discovery

How a skill learns, at runtime, which verification the project expects
and how much of it to run locally versus observe in CI after pushing.
Language-agnostic, never hardcoded.

## Local gate buckets

Five buckets, resolved by reading the project's conventions files in
priority order: `AGENTS.md`, then `CLAUDE.md`, then
`.github/CONTRIBUTING.md`. Split each file by heading; a heading that
contains a bucket keyword as a whole word ("Tests" matches `test`;
"Latest" and "Respect" do not) claims the first fenced code block beneath
it, when that block holds a command rather than output or an example. The
first file's command wins on collision. In a non-interactive run, name each
discovered command in the report before running it.

| Bucket | Heading keywords (case-insensitive) |
|---|---|
| `format` | `format`, `fmt` |
| `lint` | `lint`, `ruff check`, `eslint`, `clippy` |
| `typecheck` | `typecheck`, `type check`, `mypy`, `pyright`, `tsc` |
| `test` | `test`, `spec`, `pytest`, `vitest`, `jest` |
| `build` | `build`, `compile` |

When a bucket is unset **and the manifest shows evidence the project
has that gate** (a typecheck config such as a `mypy`/`pyright` section
or `tsconfig.json`, a `build` script, a test-runner dependency), present
*example* commands via `AskUserQuestion` and require explicit
selection. Never auto-inject `pytest`, `npm test`, `cargo build`, etc.
Without such evidence, the bucket is legitimately `unset`: skip it
downstream, do not prompt. In a non-interactive run, treat
evidence-backed unset buckets as `unset` too, and name them in the
report.

If no conventions file and no manifest exist, prompt once; the user
may answer `skip` to disable gates for the run. In a non-interactive
run, treat every bucket as `unset` and say so in the report.

## CI-coverage pass

After resolving local buckets, discover what CI verifies after a push
so local runs are not duplicated effort:

1. List CI definitions: `.github/workflows/*.yml`, `.gitlab-ci.yml`,
   `.circleci/config.yml`, `Jenkinsfile`, or equivalents.
2. For each job, note which buckets it covers and anything it runs
   that has **no local bucket** (matrix builds, slow/property-based
   suites, integration/e2e jobs, artifact builds).
3. Detect observability: if the `gh` CLI is present and the repo has a
   GitHub remote, post-push results can be watched with
   `gh pr checks --watch` (or `gh run watch` when no PR exists yet).

Record the result as a split the calling skill embeds in its plan
output: fast buckets (`format`, `lint`, `typecheck`, scoped `test`) run
locally per commit; full-matrix tests, slow or marked suites, e2e, and
release builds are deferred to CI after the push.

## Right-sizing: no more verification than the change needs

The gates exist to keep every commit green, not to re-run the world.

- **Per-commit**: run `format`, `lint`, `typecheck` on the tree, and
  the `test` bucket **scoped to the affected area** when the runner
  supports path/keyword selection; otherwise (including when no test
  maps to the change, such as docs-only edits) the project's default fast
  test command as written (its defaults often already exclude slow
  suites).
- **`build`**: run per commit only when the change plausibly affects
  build output (build config, entry points, packaging, codegen).
  Otherwise run it once at the end of the run, or defer to CI when a
  CI job covers it.
- **Deferred-to-CI** work is never silently dropped: the skill's final
  report must name what was deferred and, when observable, end by
  offering `gh pr checks --watch` after the push.
- Buckets discovered as `unset` are skipped, not reinvented.

## Storage

Shell state does not persist between commands, so record each resolved
command verbatim in the plan text (`format`, `lint`, `typecheck`,
`test`, `build`, the CI split, and the CI watch command, empty when
unobservable) and reuse the recorded text. The user audits what was
discovered there. Do not pre-validate that a command exists on `$PATH`.
