# Architecture results

## Hero

`Architecture: <chosen approach>`

## Sections, in order

Chosen Architecture · Component Map · Trade-off Analysis · Risks · Attribution

## Example

```text
Architecture: one engine module with thin CLI wrappers

## Chosen Architecture
A single `engine` module owns state; each command is a wrapper.

## Component Map
- engine.py: sessions and guards
- skills/: one prose workflow per command

## Trade-off Analysis
- One module is simple to test; it grows with every command.

## Risks
- The engine becomes a catch-all if wrappers start owning logic.

## Attribution
Host-native sub-agents: maintainer, skeptic, builder.
```

## Next-step options

**Plan the chosen architecture** · **Brainstorm alternatives** (suggest the `weave-brainstorm` skill) · **Done**

## Plan-brief extractor

Decompose the chosen architecture into ordered build steps: file, change, dependencies, tests.
