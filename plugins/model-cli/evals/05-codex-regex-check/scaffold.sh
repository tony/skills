#!/usr/bin/env bash
# Fixture binaries keep delegated runs offline.
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
echo "ANSWER: \\w is Unicode-aware in Python 3 str patterns, so non-ASCII local parts match."
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
