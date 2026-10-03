# Start or reopen a topic

`<topic.py>` is the script path from the skill that sent you here; run it with `python3`. Every command prints JSON.

## 1. Parse the request

- **Topic**: the subject in a few words. It becomes the slug; reuse an existing topic's slug when the user means it.
- **Mode**: assessment when the request is a decision (adopt, choose, ready, should we, compare against criteria); research otherwise.
- **Namespace**: `research`, unless a plugin sent you with its own.
- **Audience**: private unless the user says who will read it.

## 2. Open the run

```console
$ python3 <topic.py> open \
    --topic <topic> \
    --subject "<human title>" \
    --mode <mode>
```

Add `--root` when the user names a location (`RESEARCH_ROOT` sets it for every call), `--resume` for work that continues in one place across days, and `--namespace` for a plugin's runs.

- Exit 2 (`error`): bad input, or no single default root. For the root, ask the user where runs should live and rerun with `--root`; without an interactive host, stop and report the folders the error names.
- Exit 3 (`needs_choice`): similar topics exist. Ask which one with `ask-user-choice`, listing the candidates and "a new topic". Without an interactive host, stop and print the candidates with the rerun commands.
- `created: false`: today's run already exists. Continue in it; nothing was overwritten.
- `prior` non-empty: read the newest prior run's `index.md` and `report.md` before collecting anything. Carried sources are unverified: run `verify.md` step 1 before a finding rests on one.

## 3. Frame before collecting

Fill `## Question` and `## Scope` in `index.md`: the question, what is in, what is out and why. For an assessment, write the decision, its options, and the criteria per `assessment.md` now; criteria chosen after the evidence get bent to fit it.

## 4. Collect sources

For each source a claim will rest on:

1. Prefer the primary source. Pin it: a release tag or 7-character commit for code, a version for docs, an edition for books. Never a branch URL. When the only URL is a moving alias (`/latest/`, `/stable/`, a major-version path such as `/docs/17/`), pass the exact version the page states (`17.11`, not `17`) as `--ref` and note the alias in the report's Method. Re-adding the same URL with a more exact `--ref` keeps its id. An unversioned page takes no `--ref`.
2. Capture it. `--fetch` downloads it (comparable on later checks); otherwise save what the URL serves to a file and pass `--file`. A capture is the document at its URL: never pair a URL with bytes from somewhere else, such as a local copy of a different file. A page that changes on every load (an issue tracker, a dashboard) never verifies as fetched; capture its stable form, such as the API's JSON or the raw file, or save the text you read with `--file`, and pass the thread's last-updated time as `--ref`.
   Your own test is a source too: save its command and output to a file under `data/` and add it with `--kind measured --file <log>`, with no `--url`.
3. Record it:

```console
$ python3 <topic.py> add \
    --run <run_dir> \
    --url <url> \
    --ref <tag-or-version> \
    --title "<title>" \
    --author "<author>" \
    --kind <vendor|independent|measured> \
    --fetch \
    --quote "<exact supporting text>"
```

   Each `--quote` must appear in the capture; case, line breaks, markdown marks, and spaces before punctuation are ignored. Repeat `--quote` for each claim the source supports; a later re-add adds quotes to the ones recorded. `python3 <topic.py> find --run <run_dir> "<words>"` shows where text occurs in your captures, in the capture's own case, ready to quote.

   `--kind` says whose word it is: vendor (the subject's own), independent, or measured (your own test). `add` prints `warnings` for a moving ref or URL, a capture you supplied, a missing capture, or a missing kind in an assessment; fix the source or say in the report why it stands.

4. Write what the source supports, and where, in its card's body.

`python3 <topic.py> links --run <run_dir>` lists URLs your captures cite that you have not recorded: leads for sources you may have missed.

Refer to the run by its date and `<namespace>/<topic>` in anything you write, never by its absolute path: the path names your home directory.

## 5. Track what you cannot source

A claim with no source goes under `## Open questions` as `- [ ]`, with what would settle it. Log each working session under `## Log`.

## 6. Report

Follow `report.md`. Before calling the work done:

```console
$ python3 <topic.py> lint-report --strict <run_dir>/report.md
```

```console
$ python3 <topic.py> scan --run <run_dir>
```

Both exit zero, or the report does not ship.
