# Resources

How a goal keeps the machine usable while it runs, and what it may delete.

## Reserves

Each filesystem the goal writes to keeps 20 GiB and 10,000 inodes free; the
machine keeps 4 GiB of MemAvailable; CPU pressure stays under 60% and memory
pressure under 10% (Linux pressure stall information, `avg10`). The profile
can change each figure. Raise a reserve only with a reason tied to the build's
needs, and never lower one to make a breach go away.

## Readings

`./resources.py` resolves from this file's own directory; write it as
an absolute path in each command. Check the reserves for the worktree and the
evidence folder, printing one line first:

```console
$ python3 <resources.py> check \
    --path <worktree> \
    --path <documents>
```

The first line reads `resources ok: ...` or `resources low (<breaches>): ...`
and goes into the conversation, where Claude's evaluator can see it. The
command exits 1 on a breach. On macOS memory comes from `vm_stat`; pressure
is unknown there, and on WSL's Windows drives inode counts are unknown. On
native Windows only free space reads, and `sample` reports wall time alone. A
kernel that refuses to read pressure, as with PSI turned off, reads as
unknown. An unknown reading is reported, never counted as a breach.

Measure one expensive command:

```console
$ python3 <resources.py> sample \
    --interval 5 \
    -- <command>
```

It reports wall time, user and system CPU time, and the peak RSS of the
command's process tree, and exits with the command's own status. The peak is
null when the command exited between polls without outgrowing the sampler's
own footprint, which a child inherits on Linux: it stayed below that.

## On a breach

Stop launching work. Halve build and test parallelism (job count, worker
count, test shards). Look for leaks the goal owns: stray servers, sockets,
temporary trees. Then clean its own artifacts.

## Cleaning

Record each worktree the goal creates as it creates it:

```console
$ python3 <resources.py> register \
    --manifest <manifest file> \
    <worktree>
```

List what would be removed:

```console
$ python3 <resources.py> clean \
    --manifest <manifest file>
```

Remove it:

```console
$ python3 <resources.py> clean \
    --manifest <manifest file> \
    --apply
```

Only directories named like build artifacts (`target`, `node_modules`,
`_build`, `deps`, `dist`, `build`, `.venv`, and tool caches) inside registered
worktrees are candidates. The walk never enters a nested repository, such as a
worktree or clone inside a registered one; register it separately to clean it.
One is removed only when it is a real directory, git ignores it, and no
tracked file lives in it; everything else is reported as refused, with the
reason. Shared clones, user edits, and evidence are never candidates. Space
trouble beyond the goal's own artifacts goes to the `disk` skill.

Keep the manifest file outside every worktree, beside the goal's objective.
