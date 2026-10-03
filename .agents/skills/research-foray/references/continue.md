# Continue, fill, or expand a topic

`<topic.py>` is the script path from the skill that sent you here.

## 1. Pick the topic

Use the topic the user names. If the name matches more than one topic, ask which one; without an interactive host, stop and list the candidates. If none is named, run `status.md` and ask; without an interactive host, take the most recently updated topic and say so.

## 2. Open today's run

Follow `start.md` step 2 with the topic's existing slug and no `--subject`, `--mode`, or `--audience`, so the prior ones stay. A new date gives a new run that carries the sources and the framing (question, criteria, scope, unanswered open questions); `--resume` keeps writing in the latest run instead. Then read the prior run's `index.md` and `report.md`, and copy any other `data/*.csv` you will update from the prior run into the new one; an assessment's `criteria.csv` comes across on its own.

## 3. Re-verify what you carried

```console
$ python3 <topic.py> verify --run <run_dir>
```

Handle failures per `verify.md` step 1 before relying on any carried source.

## 4. Do the work the user asked for

- **Continue**, with neither `--fill` nor `--expand`: work the open questions and the prior report's weakest findings, in that order.
- **Fill gaps** (`--fill`): work only the `- [ ]` items under `## Open questions`. Tick each one you settle and cite the source that settled it.
- **Expand** (`--expand=<scope>`): add the new scope to `## Scope` and its questions to `## Open questions` before collecting, then collect per `start.md` step 4.

Record what changed under `## Since <prior date>` as you go: new findings, rating changes, sources that failed or were replaced.

## 5. Update the report

Write the run's `report.md` per `report.md`, building on the prior report rather than appending to it. Run the two ship checks from `start.md` step 6.

## Output

Open with a one-line hero (`✓ <topic> <date>: carried <n>, verified <n>, ticked <n> open questions` or `⚠ Blocked: <reason>`), then exactly these sections:

1. `## Since <prior date>`: new findings, replaced or failed sources, and rating changes.
2. `## Open`: what is still unanswered.
3. `## Run`: run directory and report path.

End with an `ask-user-choice` panel (for example: keep going, write the report, stop). Skip it in plan mode; without an interactive host, print the options as a numbered list.
