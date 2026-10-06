# Output contract

Every scholar skill reports in this shape.

1. Open with a one-line hero: `✓` and a short summary, or `⚠ Blocked:
   <reason>`. The skill's `## Output` section gives its hero text. No prose
   paragraph before the first section.
2. Write the sections the skill lists, in that order, under those exact
   headings. Add none.
3. End with an `ask-user-choice` panel of next steps, using the options the
   skill suggests, so the reader can act without composing a follow-up. Skip
   the panel only in plan mode. Where no question tool exists (Codex, headless
   runs), print the options as a plain list and stop; never pick one.

## A halted run

When a prerequisite is missing or a gate fails, report only the hero line
(`⚠ Blocked: <reason>`), one sentence naming what is missing, and the step the
user takes to unblock it. Print none of the skill's sections and no empty
placeholders. Do not list files you did not create.

## Content

- Bullets are plain sentences. Do not put a bold label on every bullet.
- Report only what happened. Never claim a write, a gate pass, or a command
  run that did not occur.
- Do not narrate process or justify a step ("this is what the stage exists to
  prevent").
- Name no local absolute paths or temp files. Show paths relative to the study
  directory.
