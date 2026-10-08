# A trim with the command fences preserved

This is a style example, not a validated restore procedure. Both command
fences remain unchanged, including their unresolved flaws.

````markdown
---
name: db-helper
description: Restores PostgreSQL backups and checks the result. Use when restoring a database backup or verifying a restore.
---

# Database Helper Skill

Getting a database restore wrong can lead to data loss.

## Choose the restore tool

- `pg_restore`: custom-format dumps.
- `psql`: plain SQL dumps.
- pgAdmin: a graphical interface.
- Docker exec: a database in a container.
- Cloud console: a managed service.

`pg_restore` is a reasonable default; `psql` and pgAdmin are alternatives.

## Locate the backup

Look in the backup directory for the most recent file.

```bash
ls -la C:\backups\nightly\
```

## Restore the database

```bash
pg_restore --dbname=mydb backup.dump
```

## Verify the restore

Use the `query_database` tool to check that the data looks correct.

## Read the restore reference

See `reference/advanced.md`, which links to `reference/internals.md`.
````

The description now names the existing workflow and its trigger. The title,
tool choices, data-loss warning, verification step, and reference paths stay;
the code fences are byte-for-byte the same as the input.

The ledger would flag the Windows path in a Bash fence, the hardcoded database
target, the unspecified `query_database` tool, and the reference chain. A style
pass reports those flaws; correcting them needs separate verification and
authorization.
