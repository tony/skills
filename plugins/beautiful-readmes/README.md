# Beautiful READMEs

Assess, write or improve a README for its readers. Keeps useful examples,
constraints, navigation and project voice while correcting concrete reader problems.

## Use

Ask to assess a README without edits, write one from project facts, or improve an
existing reader route. Claude Code also accepts `/beautiful-readmes:beautiful-readmes`;
Codex accepts `beautiful-readmes:beautiful-readmes`.

The skill returns evidence-ranked concerns for assessment, or the requested artifact
with a short check summary for edits. A working README can remain unchanged.

## Install

For Claude Code:

```console
$ claude plugin install beautiful-readmes --marketplace tony/skills
```

For Codex, add the marketplace if needed:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add beautiful-readmes@skills
```

## References and evaluation

[Patterns](references/patterns.md) supplies pinned examples for structural choices;
[context checks](references/contexts.md) covers ecosystem and lifecycle distinctions.
Both are read only when relevant. The [skill](skills/beautiful-readmes/SKILL.md)
defines preservation and verification; native evaluation cases exercise the resulting
artifacts, including unchanged READMEs and generated documentation.

From `plugins/beautiful-readmes/`, run the native suite with one run per arm:

```console
$ claude plugin eval . \
    --runs 1 \
    --ablation with-without \
    --judge-model sonnet \
    --concurrency 2 \
    --no-publish \
    --scaffold \
    --trust-plugin \
    --allow-tools Bash Write Edit \
    --keep-temp \
    --json evals/results/native.json
```

The scaffolds use only the supplied synthetic fixtures. Inspect them before granting
tools. Native judges assess README content; the separate artifact check binds each
case and arm to its retained workspace, verifies input hashes and generated owners,
and runs allowlisted fixture examples. Apply it to the same native report:

```console
$ python3 evals/readme_eval_checks/checks.py \
    evals/results/native.json \
    evals/results/round-1
```

Acceptance requires complete grading of both arms and passing native and artifact
checks for the skill arm. Baseline failures measure the comparison; they cannot
certify the skill. Missing cases, failed calls and skipped grading remain unverified.
