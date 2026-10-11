#!/usr/bin/env bash
# Git repo with an untracked notes.txt, plus a codex stub that re-edits it, then outlives the timeout.
set -euo pipefail
mkdir -p .eval-state/prompts

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

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
.agent_ran
.calls
bin
MD

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --dangerously-bypass-approvals-and-sandbox --sandbox --skip-git-repo-check"; exit 0;; esac
case " $* " in *" --dangerously-bypass-approvals-and-sandbox "*) ;; *) echo "stub: expected --dangerously-bypass-approvals-and-sandbox" >&2; exit 2;; esac
n=$(cat .calls 2>/dev/null || echo 0)
echo $((n + 1)) >.calls
echo "# edited by codex" >>notes.txt
sleep 30
SH

cat >bin/agent <<'SH'
#!/usr/bin/env bash
[ "${1:-}" = --list-models ] && { printf '%s\n' 'Available models' '' 'auto - Auto (default)' 'gpt-5.4-high - GPT-5.4 1M High' 'gpt-5.4-mini-medium - GPT-5.4 Mini'; exit 0; }
case " $* " in *" --help "*) echo "  -f --force --mode --model --trust --list-models -p"; exit 0;; esac
touch .agent_ran
echo "ANSWER: should never be reached"
SH
chmod +x bin/codex bin/agent

git init -q
git add app.py .gitignore
git -c user.name=eval -c user.email=eval@example.com commit -q -m init

echo "draft notes" >notes.txt
