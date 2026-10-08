#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail
mkdir -p .eval-state/prompts

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/agent <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  -f --force --mode --model --sandbox -p"; exit 0;; esac
case " $* " in *" --sandbox "*) echo "stub: preserve configured sandbox" >&2; exit 2;; esac
case " $* " in *" -f "*) ;; *) echo "stub: expected -f" >&2; exit 2;; esac
echo "ANSWER: use a parameterized query: db.query(\"SELECT * FROM users WHERE id = ?\", (id,))"
SH
chmod +x bin/agent

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
