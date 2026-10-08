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
file and compare its size against the used space reported inside it.
This command is WSL-only and needs GNU `find` and `numfmt`. `%s` is the
file's apparent size; on `/mnt/c`, `du` reports the same figure, so the
on-disk size of a sparse vhdx is readable only from Windows (file
properties, "Size on disk"). Label the figure "apparent size":

```console
$ find /mnt/c/Users/*/AppData/Local \
    -iname '*.vhdx' \
    -size +1G \
    -printf '%s\t%p\n' \
  | sort -rn \
  | numfmt --field=1 --to=iec
```

The gap between a backing file's size and the guest's used
space is *balloon* — blocks written once, freed inside the guest, and
never returned to the host. It is recoverable without deleting
anything.

## Why balloon accumulates

A dynamically expanding virtual disk grows on write and never shrinks
on delete. The guest kernel can signal freed blocks with TRIM, but the
signal may not reach the host unless the backing file is sparse-aware
(see the `sparseVhd` page linked below).

Check whether the guest even issues TRIM. This layer is Linux-only —
`findmnt` is util-linux, and the surrounding `.vhdx` inspection assumes
a WSL guest:

```console
$ findmnt -no OPTIONS /
```

`discard` in the mount options means the kernel trims on every delete.
Its presence alongside a fully-allocated backing file may mean the
virtual disk is not sparse: the guest signals and the host may ignore it.

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
2. Hand the user the in-guest trim, then the shutdown command, and wait.
3. Hand the user the compaction commands.

`sparseVhd` is documented for new disks only; whether TRIM then reclaims
space on the host is unmeasured. Mention it as an option, with that
caveat, alongside a plain compact.

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
(compact),
[Mount-VHD](https://learn.microsoft.com/en-us/powershell/module/hyper-v/mount-vhd)
(`-ReadOnly`), and
[compact vdisk](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/compact-vdisk)
(diskpart). Re-read the linked pages before relying on a command.

Run inside the guest, before the shutdown. It tells the filesystem to
release free blocks so the host can reclaim them; see `man fstrim`. Zero
bytes trimmed, or an error, means compaction will likely free little:

```console
$ sudo fstrim -av
```

Run in PowerShell. It terminates every running distribution and the WSL 2
VM, killing all shells, servers, and containers in them:

```powershell
wsl --shutdown
```

Run in PowerShell to print a distribution's vhdx path:

```powershell
(Get-ChildItem -Path HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss | Where-Object { $_.GetValue("DistributionName") -eq '<distribution-name>' }).GetValue("BasePath") + "\ext4.vhdx"
```

Compaction needs the vhdx detached or attached read-only. The
`Optimize-VHD` page says `-Mode Full` and `-Mode Quick` are allowable only
for a disk mounted read-only, and that on a VHDX not attached read-only
they fall back to Prezeroed and Pretrimmed. Prezeroed reclaims only space
already zeroed, which ext4 free space is not, so `Optimize-VHD` on a
detached vhdx can free nothing. Attach read-only first.

Run in an elevated PowerShell after the shutdown. `Mount-VHD` and
`Optimize-VHD` are in the Hyper-V PowerShell module, which not every
Windows edition installs:

```powershell
Mount-VHD -Path <path-to-ext4.vhdx> -ReadOnly
```

Compact it, then detach:

```powershell
Optimize-VHD -Path <path-to-ext4.vhdx> -Mode Full
```

```powershell
Dismount-VHD -Path <path-to-ext4.vhdx>
```

Where the Hyper-V module is missing, run `diskpart` in an elevated
prompt and enter these at the `DISKPART>` prompt (cited on the
`compact vdisk` page):

```text
select vdisk file="<path-to-ext4.vhdx>"
attach vdisk readonly
compact vdisk
detach vdisk
```

The compact "can succeed without reducing the file size". Re-read the
file size afterwards and report the measured change.

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
