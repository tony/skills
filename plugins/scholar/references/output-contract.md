# Output contract

Every scholar skill reports in this shape.

1. Open with a one-line hero: `✓` and a short summary, or `⚠ Blocked:
   <reason>`. The skill's `## Output` section gives its hero text. No prose
   paragraph before the first section.
2. Write the sections the skill lists, in that order, under those exact
   headings. Add none.
3. End with an `AskUserQuestion` panel of next steps, using the options the
   skill suggests, so the reader can act without composing a follow-up. Skip
   the panel in plan mode and on a halted run. Where no question tool exists (Codex, headless
   runs), print the options as a plain list and stop; never pick one.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`). This is `gather`; other skills
swap in their own hero and sections:

```text
✓ http-client: 3 sources pinned, 1 skipped

## Pinned

- notes/ontology/http-client/sources.jsonl
- https://github.com/acme/http-client at v2.40.0, from the newest release.
- https://github.com/acme/http-core at 9a29b1a, a commit on trunk; no releases.

## Skipped

- http-client test/: names fixtures, not domain concepts.

## Shape

- http-client: 14 modules, most under src/parser/.
```

## A halted run

The first line of the reply is the hero, `⚠ Blocked: <reason>`: no sentence
before it and no code fence around the reply. When a prerequisite is missing
or a gate fails, report only that line, one sentence naming what is missing
and the step the user takes to unblock it. Nothing follows that sentence (no
"Next step"). Print none of the skill's sections, no empty
placeholders, no guesses from partial input, and no next-step list. Do not
list files you did not create. The sentence names the unblock; it does not
restate the hero, list what was searched, or say what was not written.

```text
⚠ Blocked: no sources.jsonl for this study.

Run /scholar:gather on the corpus first.
```

## Content

- Bullets are plain sentences. Do not put a bold label on every bullet.
- Report only what happened. Never claim a write, a gate pass, or a command
  run that did not occur.
- The hero is one line with no second sentence.
- Write no sentence about a file left alone ("I left `terms.jsonl`
  unchanged") or an input that could not be reached ("the sandbox blocked
  github.com"). Report the verdict and its evidence. A reason a check could
  not run is the one exception, and only under `verify`'s `## Uncheckable`:
  write "host unreachable", never a claim about the sandbox.
- A fix for a failed gate is one sentence; do not explain how a finding was
  counted.
- Do not narrate process ("I raised one more candidate myself"), justify a step ("this is what the stage exists to
  prevent"), or say what you did not do ("I wrote no files", "I did not
  search the corpus").
- Name no local absolute paths or temp files. Show paths relative to the study
  directory.
