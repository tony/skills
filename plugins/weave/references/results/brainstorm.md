# Brainstorm results

ARTIFACT_PATH is a directory: list it to find the per-participant output files.

## Hero

`N responses from M participants`. N counts worker responses (one per participant and variant that produced output), M counts participants.

## Sections, in order

Per-participant responses (variants flattened) · Attribution

List each participant's ideas as written. Do not cluster, rank, tabulate, merge, or recommend, and do not count how many distinct designs the responses cover. Keep each design under the participant that wrote it; a recommendation inside a response stays there, introduced as that participant's. Add no prose between the hero and the first section. Say in Attribution that the originals were generated independently in parallel. Attribution is the last line of the reply: no closing comment on overlap, convergence, or which design is best.

## Example

```text
4 responses from 3 participants

## Per-participant responses
### maintainer
- Cache the parsed config per process.
- Add a `doctor` subcommand.
### skeptic (Variant 1, Conventional)
- Drop the plugin hook; it has one caller.
### skeptic (Variant 2, Creative)
- Replace the config file with environment variables.
### builder
- Split the loader from the validator so each tests alone.

## Attribution
Host-native sub-agents, generated independently in parallel: maintainer, skeptic, builder.
```

## Next-step options

**Pick one and plan it** (sub-prompt for which idea, then plan) · **Refine further** (suggest `/weave:refine`) · **Done**

## Plan-brief extractor

Treat the user-selected idea as a task. List the implementation steps.
