#!/usr/bin/env bash
# Tier 1 fails auth; tier 2's model is unknown and has no version sibling listed.
set -euo pipefail
mkdir -p .eval-state/prompts bin

cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --dangerously-bypass-approvals-and-sandbox --sandbox --skip-git-repo-check"; exit 0;; esac
case " $* " in *" --dangerously-bypass-approvals-and-sandbox "*) ;; *) echo "stub: expected canonical bypass flag" >&2; exit 2;; esac
echo "Authentication required: run codex login" >&2
exit 1
SH

cat >bin/agent <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  -f --force --mode --model --sandbox -p"; exit 0;; esac
case " $* " in *" --list-models "*) printf '%s\n' 'Available models' '' 'gpt-5.5-codex-high - Codex 5.5 High' 'gpt-5.6-sol-high - GPT-5.6 Sol 1M High' 'gpt-5.4-mini-medium - GPT-5.4 Mini'; exit 0;; esac
case " $* " in *" -f "*) ;; *) echo "stub: expected -f" >&2; exit 2;; esac
model=$(printf '%s\n' "$@" | sed -n '/^--model$/{n;p;}')
echo "$model" >>.models_ran
case "$model" in
  gpt-5.4-high) echo "Cannot use this model: gpt-5.4-high" >&2; exit 1;;
  *) echo "ANSWER: handle() upper-cases payload['name'].";;
esac
SH
chmod +x bin/codex bin/agent

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
.models_ran
MD

git init -q
git add app.py .gitignore
git -c user.name=eval -c user.email=eval@example.com commit -q -m init
