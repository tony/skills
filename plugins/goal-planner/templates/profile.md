---
documents: auto
claude_target: 3800
research_roots: [~/study]
review_lenses: [the project's language, its domain, developer experience]
rubric_target: 9
worktree_pattern: ../<repo>-<branch>
push_target: none
pull_request: no pull request unless asked
private_remote:
subagent_cap: 4
reserve_disk_gib: 20
reserve_inodes: 10000
reserve_mem_gib: 4
cpu_pressure_pct: 60
mem_pressure_pct: 10
---

# goal-planner profile

The defaults goal-planner applies when a request does not say otherwise. Each
module section below switches a guardrail from `references/modules.md` on or
off; text under a heading replaces that module's wording with your own.

## Dimensions

- dimensions.library: developer experience, docs, examples, typing, tests
- dimensions.docs: accuracy, scannability, examples, links
- dimensions.skills: routing, data sourcing, readability, freshness

## quality-bar: on

## method-ratchet: on

## rubric: on

## research-corpora: on

## adversarial-review: on

## vcs-policy: on

## ci-proof: auto

## anti-slop: on

## downstream-safety: off

## breaking-changes-ok: off

## scope-holds: on

## serial-issues: off

## subagents: on

## honest-stop: on

## hand-test: off

## resources: on
