# Virtual disks and nested filesystems

## Contents

- Detect the nesting first
- Why apparent size differs
- Never run the shutdown yourself
- Ordering
- WSL: shutdown, compact, sparse
- Docker Desktop and Hyper-V

Only Linux and WSL guests have been exercised. The Windows commands below
come from Microsoft's pages and have not been run against a live VHDX;
macOS APFS snapshots and Time Machine are not covered. Say so instead of
inferring either from Linux behavior.

When the filesystem being cleaned lives inside a virtual disk, measure
guest and host recovery separately. Guest deletion alone proves neither
host recovery nor the need for compaction.

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
file's apparent size; guest-side `du` may not expose Windows allocation.
Read host allocation from Windows file properties ("Size on disk").
Label the guest-side figure "apparent size":

```console
$ find /mnt/c/Users/*/AppData/Local \
    -iname '*.vhdx' \
    -size +1G \
    -printf '%s\t%p\n' \
  | sort -rn \
  | numfmt --field=1 --to=iec
```

The backing file's apparent size minus guest used space is an *apparent
gap*, not a recovery estimate. Sparse allocation and virtual-disk
metadata prevent that subtraction from measuring host space. Subtracting
guest used space from host allocated size does not establish a reclaim
estimate or upper bound either: the layers account for different blocks.
Present allocation does not establish allocation history: call blocks
currently unallocated, not "never allocated".
Read host
allocated size or free space before and after any compaction; Microsoft's
[sparse-file documentation](https://learn.microsoft.com/en-us/windows/win32/fileio/sparse-files)
distinguishes file length from allocation.

## Why apparent size differs

A dynamically expanding virtual disk can retain its apparent size after
guest deletion. TRIM and sparse allocation can affect host usage without
the same change in apparent size (see the `sparseVhd` page linked below).

Check whether the guest even issues TRIM. This layer is Linux-only —
`findmnt` is util-linux, and the surrounding `.vhdx` inspection assumes
a WSL guest:

```console
$ findmnt -no OPTIONS /
```

`discard` requests online discard of freed blocks. It does not measure
whether the host reclaimed them.

## Never run the shutdown yourself

Compacting requires the guest to be stopped. **Do not run
`wsl --shutdown`, `wsl --terminate`, or any equivalent guest-halting
command.** It kills every running shell, server, container, and
background job, risking unsaved work.

Present it as a step the user runs, with what it interrupts, and stop.
The same applies to host-side compaction, which runs from a Windows
administrator shell.

## Ordering

Compaction only reclaims blocks that are already free inside the guest,
so sequence matters:

1. Perform approved guest cleanup and measure its guest free-space delta.
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
release free blocks so the host can reclaim them; see `man fstrim`.
Report the result without inferring compaction yield from it:

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
they fall back to Prezeroed and Pretrimmed. Prezeroed relies on space
already being zeroed. Attach read-only for Full mode; neither mode
guarantees that the file will shrink.

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

Compaction can succeed without reducing file size. Measure host allocation
or host free space afterwards and report that delta separately from the
change in apparent file size.

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
