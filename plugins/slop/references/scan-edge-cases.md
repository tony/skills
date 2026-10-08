# /slop:scan edge cases

| Case | Behavior |
|---|---|
| Empty repo or no tracked files | Step 1 stops with the one-sentence shape. |
| All findings advisory (Tier C only at `default` budget) | Print the report; no commits; exit 0. |
| `--allow-dirty` and a finding sits in a dirty file | Advisory only; never edited. |
| Finding's edit yields an empty diff (already fixed) | Skip; record "no-op"; never create an empty commit. |
| Two findings target the same line range | Keep `commits.json` list order; a stale patch halts before touching the checkout. |
| Disk fills while writing a patch | Treat as a gate failure for that finding and follow `--on-fail`. |
| Binary file | Pass A skips it; it yields no findings. |
| Symlink | Skip it; the link target is out of scope. |
