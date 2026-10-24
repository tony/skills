# Profiles and machine bindings

Profiles hold explicitly approved planning defaults. Write inspectable values
and rationale under [prose-rules.md](./prose-rules.md).

## Separate preferences, context, and bindings

Portable preferences cover evidence/prose standards, review triggers, resource
principles, host/output defaults, and optional integrations. They cannot override
the instruction hierarchy or grant future publication authority. Re-read target
identity, tooling, compatibility, exceptions, and delivery requirements from
project context instead of promoting them to universal defaults.

Store the Documents root in separate machine bindings. Discover workspace
roots, tools, reviewers, resource probes, and owned scratch/build locations
when needed. Native/mounted Documents roots remain distinct; never infer a
username or equate folders by name.

## Approve selections

An explicit request to save named values approves them; preserve session
approval. Otherwise show candidates and await selection before persistence.
History suggests candidates under [recovery.md](./recovery.md), never silently
changes memory/configuration or promotes assistant habits. Prefer direct human
evidence, retain contradictions/provenance limits, and report absent history
instead of inventing preferences or claiming exhaustive historical coverage.

One-off release permissions, model names, platform exclusions, timing holds,
machine thresholds, and paths remain scoped unless the user deliberately
promotes an appropriate default. Set `approved: true` only for selected values;
a CLI approval flag records consent, never creates it.

## Validate and persist

`<planner>` is `./planner.py`, resolved from this reference's directory
to an absolute path written literally in each command. Skills declare their
own relative helper path. Use these strict schemas. `max_chars` is optional;
omit it for uncapped Codex. Claude profile limits cannot spend the addendum
reserve.

```json
{
  "schema_version": 1,
  "kind": "profile",
  "approved": true,
  "name": "portable",
  "defaults": {"host": "claude", "save": true, "max_chars": 3800},
  "principles": ["Require independent review for delivery goals."]
}
```

Bindings require an absolute path or one starting with `~/`, independent of
the working directory:

```json
{
  "schema_version": 1,
  "kind": "bindings",
  "approved": true,
  "documents_root": "~/Documents"
}
```

Validate a selected existing profile before updating it:

```console
$ python3 <planner> profile read \
    --path <profile.json>
```

Persist selected values to a user-selected location:

```console
$ python3 <planner> profile write \
    --input - \
    --path <profile.json> \
    --approved <<'JSON'
{"schema_version":1,"kind":"profile","approved":true,"name":"portable","defaults":{"host":"claude","save":true,"max_chars":3800},"principles":[]}
JSON
```

Use `bindings read`/`bindings write` with the same options and binding schema.
New writes must not overwrite files; add `--replace` only for an approved
revision of an existing same-kind settings file. Read back through the helper
and compare with approved values. Report validation/write failures and complete
values under [output.md](./output.md). There is no automatic discovery or
application: workflows explicitly select profiles/bindings and supply defaults
to rendering.

## Transfer

Use the user's chosen file/repository mechanism. Exclude raw histories,
credentials, private paths, and private marketplace dependencies from portable
profiles. Never upload histories implicitly. Resolve receiving-machine bindings;
missing tools remain unavailable, or UNVERIFIED when required.

For goal bundles, verify companion hashes/identities, reconcile changed
contracts, and render a new numbered goal when its locator changes. Transferring
a profile never activates goals or imports execution permissions.
