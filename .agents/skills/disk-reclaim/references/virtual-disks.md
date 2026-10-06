# Virtual disks and nested filesystems

## Contents

- Detect the nesting first
- Why balloon accumulates
- Never run the shutdown yourself
- Ordering
- WSL: shutdown, compact, sparse
- Docker Desktop and Hyper-V

When the filesystem being cleaned lives inside a virtual disk, deleting
files frees nothing on the host until the disk is compacted.

## Detect the nesting first

Measure free space on **every** layer before proposing any reclaim.
A guest filesystem reporting ample free space tells you nothing about
the host that stores its backing file.

```console
$ df -h
```

On WSL, the guest root is an `ext4.vhdx` under the Windows user
profile, and container runtimes add their own. Locate every backing
file and compare its on-disk size against the used space reported
inside it. This command is WSL-only and needs GNU `find` and `numfmt`:

```console
$ find /mnt/c/Users/*/AppData/Local \
    -iname '*.vhdx' \
    -size +1G \
    -printf '%s\t%p\n' \
  | sort -rn \
  | numfmt --field=1 --to=iec
```

The gap between a backing file's allocated size and the guest's used
space is *balloon* — blocks written once, freed inside the guest, and
never returned to the host. It is recoverable without deleting
anything.

## Why balloon accumulates

A dynamically expanding virtual disk grows on write and never shrinks
on delete. The guest kernel can signal freed blocks with TRIM, but the
signal only reaches the host when the backing file is sparse-aware.

Check whether the guest even issues TRIM. This layer is Linux-only —
`findmnt` is util-linux, and the surrounding `.vhdx` inspection assumes
a WSL guest:

```console
$ findmnt -no OPTIONS /
```

`discard` in the mount options means the kernel trims on every delete.
Its presence alongside a fully-allocated backing file is the
diagnostic signature of a non-sparse virtual disk: the guest is
signalling correctly and the host is ignoring it.

## Never run the shutdown yourself

Compacting requires the guest to be stopped. **Do not run
`wsl --shutdown`, `wsl --terminate`, or any equivalent guest-halting
command.** It kills every running shell, server, container, and
background job, including the session issuing the command and any
unsaved work.

Present it as a step the user runs, with what it interrupts, and stop.
The same applies to host-side compaction, which runs from a Windows
administrator shell the agent does not own.

## Ordering

Compaction only reclaims blocks that are already free inside the guest,
so sequence matters:

1. Delete and merge inside the guest. This frees blocks internally and
   changes the host's disk usage by nothing at all.
2. Hand the user the shutdown command and wait.
3. Hand the user the compaction command.

Sparse is a durable fix: future TRIM self-reclaims, so the balloon stops
re-accumulating. Offer it alongside a plain compact.

## WSL: shutdown, compact, sparse

These commands run on the Windows host, not in the Linux guest, and only
the user runs them; each halts WSL or needs the VM stopped.

Sources:
[Basic commands for WSL](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
(`wsl --shutdown`),
[How to manage WSL disk space](https://learn.microsoft.com/en-us/windows/wsl/disk-space)
(locating the vhdx),
[Advanced settings configuration in WSL](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
(`sparseVhd`), and
[Optimize-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/optimize-vhd)
(compact). Re-check them with `wsl --help` before relying on a command.

Run in PowerShell. It terminates every running distribution and the WSL 2
VM, killing all shells, servers, and containers in them:

```powershell
wsl --shutdown
```

Run in PowerShell to print a distribution's vhdx path:

```powershell
(Get-ChildItem -Path HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss | Where-Object { $_.GetValue("DistributionName") -eq '<distribution-name>' }).GetValue("BasePath") + "\ext4.vhdx"
```

Run in an elevated PowerShell after the shutdown. `Optimize-VHD` is in
the Hyper-V PowerShell module, which not every Windows edition installs,
and requires the disk to be detached or attached read-only. On a detached
VHDX, `-Mode Full` falls back to Prezeroed per the cmdlet page:

```powershell
Optimize-VHD -Path <path-to-ext4.vhdx> -Mode Full
```

The Microsoft pages cite no command that sets an existing distribution's
disk sparse. They document only `sparseVhd=true` under `[experimental]`
in `%UserProfile%\.wslconfig`, which applies to newly created VHDs. For
an existing disk, tell the user no cited command exists here and have
them check `wsl --manage --help` on their WSL version.

## Docker Desktop and Hyper-V

Free space inside, stop the VM, compact the backing file. Each has a
vendor-specific shutdown: locate the file as above, give no command not
found in the vendor's documentation, and treat stopping the VM as a halt
the user runs.
