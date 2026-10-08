#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
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
case " $* " in *" --dangerously-skip-permissions "*) ;; *) echo "stub: expected --dangerously-skip-permissions" >&2; exit 2;; esac
echo "ANSWER: dropping legacy_status breaks any query or ORM model that still reads it."
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
