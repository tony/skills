#!/usr/bin/env bash
# A repo with a trunk and a sync command, so a branch name can be derived from
# the goal and a worktree has somewhere to come from.
set -euo pipefail

git init -b main >/dev/null

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.eval-state
bin
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
MD

mkdir -p src
cat >src/sync.py <<'PY'
"""Sync command."""


def sync(source, destination):
    copied = 0
    for item in source.list():
        destination.write(item)
        copied += 1
    return copied
PY

git add .gitignore src/sync.py
git commit -q -m 'sync(feat) Add the sync command'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

mkdir -p bin .eval-state
command -v git >.eval-state/git-path
cat >bin/git <<'PY'
#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import sys

main = Path(__file__).resolve().parent.parent
git = (main / ".eval-state/git-path").read_text().strip()
args = sys.argv[1:]
code = subprocess.run([git, *args], check=False).returncode
if code == 0 and any(args[i:i + 2] == ["worktree", "add"] for i in range(len(args))):
    raw = subprocess.check_output(
        [git, "-C", str(main), "worktree", "list", "--porcelain"], text=True
    )
    entries = [dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
               for block in raw.strip().split("\n\n")]
    linked = entries[1:]
    result = {"count": len(linked)}
    if len(linked) == 1:
        worktree = Path(linked[0]["worktree"]).resolve()
        result.update({
            "outside": worktree != main and main not in worktree.parents,
            "branch": linked[0].get("branch", ""),
            "source_present": (worktree / "src/sync.py").is_file(),
        })
    (main / ".eval-state/worktree.json").write_text(json.dumps(result) + "\n")
sys.exit(code)
PY
chmod +x bin/git
