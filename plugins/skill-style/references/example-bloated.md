# A bloated skill, with its defects named

This illustrative SKILL.md repeats background information and leaves
operational choices unresolved.

## Contents

- The file
- What the test cuts, and why
- What survives

## The file

````markdown
---
name: db-helper
description: A helpful skill for working with databases. You can use this to restore backups and do other database-related things.
---

# Database Helper Skill

## Introduction

Welcome to the database helper skill! This skill is designed to help
you work with PostgreSQL databases in a safe and effective manner.

PostgreSQL is a powerful, open-source object-relational database
system with over 35 years of active development. It is known for its
reliability, feature robustness, and performance. Backups in
PostgreSQL are typically created using the `pg_dump` utility, which
produces a file containing the SQL commands needed to recreate the
database.

## Overview

This section provides an overview of what this skill does. This skill
helps with restoring PostgreSQL database backups. It walks through the
process step by step.

## Why This Matters

Database restoration is an important operation. Getting it wrong can
lead to data loss, which can be very costly for an organization. It is
therefore generally considered a best practice to be careful when
performing restores. Taking your time and double-checking your work
can help you avoid problems down the line.

## Prerequisites

Before you begin, you will need to have a few things set up. You
should make sure you have the appropriate tools installed and that you
have the necessary permissions to perform the restore operation.

## Choosing Your Approach

There are several ways to restore a PostgreSQL backup, and the right
one depends on your situation:

| Option | Tool | Notes |
|---|---|---|
| A1 | `pg_restore` | Works with custom-format dumps |
| A2 | `psql` | Works with plain SQL dumps |
| A3 | pgAdmin | Has a graphical interface |
| A4 | Docker exec | If you are running in a container |
| A5 | Cloud console | If you are on a managed service |

You can pick whichever of these options works best for you. Option A1
is often a reasonable default, but feel free to use Option A2 or
Option A3 if you prefer.

## The Restore Process

This section explains the restore process.

### Step 1: Locate the backup

First, you need to find the backup file. Backups are stored in the
backup directory. Look in that directory for the most recent file.

```bash
ls -la C:\backups\nightly\
```

### Step 2: Restore the database

Now that you have located the backup file, you can restore it. Run the
restore command shown below. This command will restore the database
from the backup file you located in the previous step.

```bash
pg_restore --dbname=mydb backup.dump
```

The command above uses the `--dbname` flag to specify which database
to restore into, and takes the path to the backup file as its final
argument.

### Step 3: Verify

After the restore completes, you should verify that it worked. Use the
`query_database` tool to check that the data looks correct. Note that
as of the 2024 release, the verification step is faster than it used
to be.

## Additional Information

For more details, see `reference/advanced.md`, which links onward to
`reference/internals.md` where the full explanation lives.

## Conclusion

That's it! You now know how to restore a PostgreSQL database backup.
If you have any questions, feel free to ask. Happy restoring!
````

## What the test cuts, and why

**The description underspecifies the task.** `A helpful skill for working
with databases` gives a domain, not a workflow. Keep the restore trigger,
remove `other database-related things`, and write it in third person.

**The introductory background changes no step.** Cut Postgres's age,
`pg_dump`'s definition, and the argument for being careful. Keep the warning
that a failed restore can cause data loss; destructive-step warnings are
outside the deletion test.

**`This section explains the restore process` restates its own
heading.** So does `This section provides an overview`. A line whose
content is its heading is the purest form of the defect.

**`Prerequisites` names no prerequisite.** "The appropriate tools" and
"the necessary permissions" cannot be acted on. Either name the binary
and the role, or cut the section.

**The options are a list of tools and their uses.** Drop the coded labels
and keep the format and environment distinctions as bullets. A style pass
does not invent a deployment-specific choice among them.

**The prose under each fence repeats the fence.** `The command above
uses the --dbname flag to specify which database to restore into` is
the command, in English, one line lower. Where a fence and its prose
say the same thing, the prose goes — the fence is what was verified.

**Command flaws belong in the ledger.** The Windows path is inside a Bash
fence, and the restore command names `mydb` without establishing that it is
the intended target. The verification tool is unspecified. Report those
gaps; do not replace commands, add cleanup flags, or invent a restore
procedure while trimming prose.

**`Conclusion` is postamble.** `That's it!`, `feel free to ask`, and
`Happy restoring!` are conversational filler in a file no human reads
conversationally.

## What survives

The command fences, tool choices, data-loss warning, verification step,
and reference paths survive. Their presence in the trimmed example does
not establish that they are correct or safe to execute.
