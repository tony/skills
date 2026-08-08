# Virtual disks and nested filesystems

When the filesystem being cleaned lives inside a virtual disk, deleting
files frees nothing on the host until the disk is compacted. Getting
this wrong produces the most demoralizing possible outcome: hours of
cleanup, and a host disk still at 100%.

## Detect the nesting first

Measure free space on **every** layer before proposing any reclaim.
A guest filesystem reporting ample free space tells you nothing about
the host that stores its backing file.

```
df -h
```

On WSL, the guest root is an `ext4.vhdx` under the Windows user
profile, and container runtimes add their own. Locate every backing
file and compare its on-disk size against the used space reported
inside it.

```
find /mnt/c/Users/*/AppData/Local -iname '*.vhdx' -size +1G -printf '%s\t%p\n' | sort -rn | numfmt --field=1 --to=iec
```

The gap between a backing file's allocated size and the guest's used
space is *balloon* — blocks written once, freed inside the guest, and
never returned to the host. It is recoverable without deleting
anything.

## Why balloon accumulates

A dynamically expanding virtual disk grows on write and never shrinks
on delete. The guest kernel can signal freed blocks with TRIM, but the
signal only reaches the host when the backing file is sparse-aware.

Check whether the guest even issues TRIM:

```
findmnt -no OPTIONS /
```

`discard` in the mount options means the kernel trims on every delete.
Its presence alongside a fully-allocated backing file is the
diagnostic signature of a non-sparse virtual disk: the guest is
signalling correctly and the host is ignoring it.

## Never run the shutdown yourself

Compacting requires the guest to be stopped. **Do not run
`wsl --shutdown`, `wsl --terminate`, or any equivalent guest-halting
command.** It kills every running shell, editor server, language
server, container, and background job on the machine — including the
session issuing the command, and including work the user has not saved.

Present it as a step the user runs. Give the exact command, say what it
will interrupt, and stop. This holds even when the user has approved
the surrounding cleanup: approval to delete caches is not approval to
terminate the environment.

The same restraint applies to any host-side compaction command, since
those run from a Windows administrator shell the agent does not own.

## Ordering

Compaction only reclaims blocks that are already free inside the guest,
so sequence matters:

1. Delete and merge inside the guest. This frees blocks internally and
   changes the host's disk usage by nothing at all.
2. Hand the user the shutdown command and wait.
3. Hand the user the compaction command.

Setting the disk sparse is a durable fix rather than a one-time
recovery — it makes future TRIM self-reclaiming, so the balloon stops
re-accumulating. Offer it alongside a plain compact and let the user
choose.

## Reporting

Report guest and host separately, and never present a guest-side figure
as space recovered on the host. State three numbers: what the cleanup
frees inside the guest, what the balloon already holds, and what the
host gains once the user completes the steps only they can run.

When the host is critically full, say so before anything else. Guest
cleanup is often not the user's most urgent lever — a host-side cache,
media library, or second virtual disk may dominate, and the user cannot
weigh that against guest cleanup unless both are on the table.
