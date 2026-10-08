#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail
mkdir -p .eval-state/prompts

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --dangerously-bypass-approvals-and-sandbox --sandbox --skip-git-repo-check"; exit 0;; esac
case " $* " in *" --dangerously-bypass-approvals-and-sandbox "*) ;; *) echo "stub: expected --dangerously-bypass-approvals-and-sandbox" >&2; exit 2;; esac
n=$(cat .calls 2>/dev/null || echo 0)
echo $((n + 1)) >.calls
exit 0
SH
chmod +x bin/codex

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
