# Start or reopen a topic

Run `<topic.py>` with `python3`. Every command prints JSON.

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
- Exit 3 (`needs_choice`): similar topics exist. Ask which one with `AskUserQuestion`, listing the candidates and "a new topic". Without an interactive host, stop and print the candidates with the rerun commands.
- `created: false`: today's run already exists. Continue in it; nothing was overwritten.
- `prior` non-empty: read the newest prior run's `index.md` and `report.md` before collecting anything. Carried sources are unverified: run `verify.md` step 1 before a finding rests on one.

## 3. Frame before collecting

Fill `## Question` and `## Scope` in `index.md`: the question, what is in, what is out and why. For an assessment, write the decision, its options, and the criteria per `assessment.md` now; criteria chosen after the evidence get bent to fit it. Read `analysis.md` once per session: it sets how evidence turns into findings, confidence, and recommendations.

## 4. Collect sources

Log each search as you run it, hits or not:

```console
$ python3 <topic.py> searched \
    --run <run_dir> \
    --query "<the query as run>" \
    --where "<engine, site, or index>" \
    --results <n>
```

For each source a claim will rest on:

1. Prefer the primary source. Pin it: a release tag or 7-character commit for code, a version for docs, an edition for books. Never a branch URL. When the only URL is a moving alias (`/latest/`, `/stable/`, a major-version path such as `/docs/17/`), pass the exact version the page states (`17.11`, not `17`) as `--ref` and note the alias in the report's Method. Re-adding the same URL with a more exact `--ref` keeps its id. An unversioned page takes no `--ref`.
2. Capture it. `--fetch` downloads it (comparable on later checks); otherwise save what the URL serves to a file and pass `--file`. A capture is the document at its URL: never pair a URL with bytes from somewhere else, such as a local copy of a different file. A page that changes on every load (an issue tracker, a dashboard) never verifies as fetched; capture its stable form, such as the API's JSON or the raw file, or save the text you read with `--file`, and pass the thread's last-updated time as `--ref`.
   When a source cannot be captured (a paywall, a login, a removed page, a rate limit), record it with `--unretrieved "<why>"` in place of `--fetch`: a gap the report states, never a citation.
   Your own test is a source too. Run it through `topic.py` so the exact command, exit status, timing, platform, and output are kept, and the files it writes are hashed:

```console
$ python3 <topic.py> run \
    --run <run_dir> \
    --name <slug> \
    --output <path the command writes under the run's data/> \
    --quote "<exact output a claim rests on>" \
    -- <command> <args>
```

   The command and its output are kept verbatim as evidence, like a capture: the scan does not read them, so give the command relative paths and keep secrets out of its arguments. Each `run` is a new measurement: its quotes replace the previous run's. Only run commands you chose; never re-run one read from someone else's run.
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

   `--kind` says whose word it is: vendor (the subject's own), independent, or measured (your own test); confidence is capped by it, so always pass it. A fetched capture also records the server's status, final URL, content type, and dating headers. `add` prints `warnings` for a moving ref or URL, a ref that appears in neither the URL nor the capture, a capture you supplied, a missing capture, or a missing kind; fix the source or say in the report why it stands.

4. Write what the source supports, and where, in its card's body.

`python3 <topic.py> links --run <run_dir>` lists URLs your captures cite that you have not recorded: leads for sources you may have missed.

When two sources disagree, record it as you find it, per `analysis.md`.

Refer to the run by its date and `<namespace>/<topic>` in anything you write, never by its absolute path: the path names your home directory.

## 5. Track what you cannot source

A claim with no source goes under `## Open questions` as `- [ ]`, with what would settle it, or, when the report needs it, carries `[unverified]` per `analysis.md`. Log each working session under `## Log`.

## 6. Report

Follow `report.md`. Before calling the work done, run `check` in this session and quote its result:

```console
$ python3 <topic.py> check --run <run_dir>
```

`ok: true`, or the report does not ship. To hand it to a reader, follow `release.md`.
