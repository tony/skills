#!/usr/bin/env bash
# Builds a fixture file, a stub `codex` that fails to authenticate, and a
# stub `agent` that returns an answer.
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
echo "Authentication required: run codex login" >&2
exit 1
SH

cat >bin/agent <<'SH'
#!/usr/bin/env bash
[ "${1:-}" = --list-models ] && { printf '%s\n' 'Available models' '' 'auto - Auto (default)' 'gpt-5.4-high - GPT-5.4 1M High' 'gpt-5.4-mini-medium - GPT-5.4 Mini'; exit 0; }
case " $* " in *" --help "*) echo "  -f --force --mode --model --sandbox --trust --list-models -p"; exit 0;; esac
case " $* " in *" --sandbox "*) echo "stub: preserve configured sandbox" >&2; exit 2;; esac
case " $* " in *" -f "*) ;; *) echo "stub: expected -f" >&2; exit 2;; esac
echo "ANSWER: handle() upper-cases payload['name'] and raises KeyError when it is missing."
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
.calls
MD

git init -q
git add -A
git -c user.name=eval -c user.email=eval@example.com commit -q -m init
