# Quality-Gate Discovery

How `/slop:deslop` and `/slop:scan` find the project's formatter, linter,
type-checker, and test command at runtime, never hardcoded.

Four buckets are resolved before any change is applied: `format`,
`lint`, `typecheck`, `test`. Any bucket may stay `unset`; every step
that runs gates skips empty buckets.

## Algorithm

```
function discover_quality_gates():
    files = []
    for path in [./AGENTS.md, ./CLAUDE.md, ./.github/CONTRIBUTING.md]:
        if exists(path):
            files.append((path, read(path)))

    if not files:
        return prompt_user_for_commands()

    gates = {format: None, lint: None, typecheck: None, test: None}

    for (path, content) in files:
        for section in split_by_heading(content):
            heading_lower = section.heading.lower()
            for bucket, keywords in HEADING_KEYWORDS:
                if any(k in heading_lower for k in keywords):
                    blocks = extract_fenced_blocks(section)
                    if blocks and gates[bucket] is None:
                        gates[bucket] = first_command(blocks[0])

    for bucket, cmd in gates.items():
        if cmd is None and manifest_exists():
            gates[bucket] = ask_user_for_bucket(
                bucket,
                examples=manifest_examples(bucket),
            )

    return gates
```

Read every file that exists; do not stop at the first. The first file's
command wins on collision, in the order `AGENTS.md`, `CLAUDE.md`,
`.github/CONTRIBUTING.md`; a later file fills only the buckets still
unset.

## Heading keywords

| Bucket | Heading substrings (case-insensitive) |
|---|---|
| `format` | `format`, `fmt`, `style` |
| `lint` | `lint`, `ruff check`, `eslint`, `clippy` |
| `typecheck` | `typecheck`, `type check`, `mypy`, `pyright`, `tsc` |
| `test` | `test`, `spec`, `pytest`, `vitest`, `jest` |

Match is a substring of the lowercased heading. The first command line
of the first fenced block under a matching heading becomes the bucket's
command.

## Manifest fallback

Manifest sniffing is never a default. When a bucket is still `unset` and
a manifest exists (`pyproject.toml`, `package.json`, `Cargo.toml`,
`go.mod`, `Gemfile`, and the like), offer example commands for that
ecosystem through `AskUserQuestion` and require an explicit choice
before storing. Never auto-inject `pytest`, `npm test`, `cargo test`, or
any other command.

## Total absence

When no conventions file and no manifest exists, ask once through
`AskUserQuestion`:

> I could not find AGENTS.md / CLAUDE.md describing your project's
> quality gates. What command should I run to verify each change? You
> can answer 'skip' to disable quality gates.

Answering `skip` makes every gate step a no-op for the run.

## Empty buckets

Skip an `unset` bucket wherever gates run: the conflict loop, the
per-finding commit loop, and final verification.

When every bucket is `unset` and the run will modify files or history
(`--apply-patches`, `--apply-rebase`, `--apply`), warn before the first
modification that no gate will validate the result.

## Storage

Cache the resolved commands as `FORMAT_CMD`, `LINT_CMD`, `TYPECHECK_CMD`,
`TEST_CMD` and record them in `0000-PLAN.md` so the user can audit what
was discovered. Store the strings verbatim and do not check them against
`$PATH`; a command-not-found surfaces through the gate-failure path of
the step that ran it.
