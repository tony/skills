#!/usr/bin/env bash
# A repo with a recorded execute session that captured one new file, no worker needed.
set -euo pipefail

git init -b main >/dev/null
git config user.email eval@example.com
git config user.name eval

mkdir -p src
printf 'def main():\n    print("hi")\n' >src/cli.py
git add src/cli.py
git commit -q -m 'cli(feat) Add the entry point'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
engine="$here/../../scripts/engine.py"
session="$(python3 "$engine" init --command execute --mutating --backend subagents | jq -r .session_dir)"
python3 "$engine" worktrees create --session "$session" --participants maintainer >/dev/null
wt="$(jq -r '.worktrees.maintainer.path' "$session/session.json")"
printf 'def dry_run():\n    return True\n' >"$wt/src/dry.py"
python3 "$engine" capture --session "$session" --pass 1 --participant maintainer >/dev/null
mkdir -p "$session/pass-0001"
printf '# Synthesis\n\n- src/dry.py from maintainer (only candidate).\n' >"$session/pass-0001/synthesis.md"
python3 "$engine" worktrees remove --session "$session" >/dev/null
python3 "$engine" stash-restore --session "$session" >/dev/null
python3 "$engine" update --session "$session" --status completed --event pass_complete --link-latest >/dev/null
