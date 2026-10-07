#!/usr/bin/env bash
# Git repo plus a codex stub that edits app.py, then outlives the timeout.
set -euo pipefail

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
.gitconfig
.profile
.zprofile
.zshrc
.agent_ran
bin
MD

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --yolo --sandbox"; exit 0;; esac
case " $* " in *" --yolo "*) ;; *) echo "stub: expected --yolo" >&2; exit 2;; esac
echo "# edited by codex" >>app.py
sleep 30
SH

cat >bin/agent <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  -f --mode"; exit 0;; esac
touch .agent_ran
echo "ANSWER: should never be reached"
SH
chmod +x bin/codex bin/agent

git init -q
git add app.py .gitignore
git -c user.name=eval -c user.email=eval@example.com commit -q -m init
