# Brainstorm-and-refine results

## Hero

`Refined through N passes`; add `(early-stop @ K)` when it converged early.

## Sections, in order

Final Result · Evolution Summary · Rationale Chain · Attribution

Rationale Chain gives the reasons for the choices made. It ends with the last reason: no advice, "next improvement", or list of what could still be added.

Evolution Summary opens with an Originals bullet: how many drafts were generated independently, and what they differed on. The final result is the weave, so this bullet is where the reader sees that more than one approach existed. Name the approaches that lost, in a few words each, in Rationale Chain.

## Example

```text
Refined through 2 passes

## Final Result
Page with an opaque keyset cursor: base64 of (created_at, id), ordered by that pair, and the client sends the cursor back until it is null.

## Evolution Summary
- Originals: 3 drafts generated independently in parallel; they differed on the cursor (opaque keyset, signed token, plain offset).
- Pass 1 picked the maintainer draft (34/40).
- Pass 2 merged the skeptic's tie-break on id.

## Rationale Chain
- Offset paging was set aside: it skips rows when data changes between pages.
- A signed token was set aside: nothing here needs tamper protection.

## Attribution
Host-native sub-agents, generated independently in parallel: maintainer, skeptic, builder.
```

## Next-step options

**Plan the refined result** · **Refine again** (suggest `/weave:refine`) · **Done**

## Plan-brief extractor

Treat the refined artifact as a task. List the implementation steps.
