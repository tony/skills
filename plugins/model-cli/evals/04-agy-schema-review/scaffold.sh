#!/usr/bin/env bash
# Fixture binaries keep delegated runs offline.
set -euo pipefail
mkdir -p .eval-state/prompts

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/agy <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --dangerously-skip-permissions --mode --model -p"; exit 0;; esac
echo "Authentication required: log in first" >&2
exit 1
SH
chmod +x bin/agy

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.eval-state
.gitconfig
.gitmodules
.ripgreprc
.mcp.json
.vscode
.idea
.profile
.zprofile
.zshrc
bin
.calls
MD

git init -q
git add -A
git -c user.name=eval -c user.email=eval@example.com commit -q -m init
