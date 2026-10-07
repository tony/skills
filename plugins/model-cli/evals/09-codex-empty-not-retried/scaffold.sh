#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --yolo --sandbox -f --mode --dangerously-skip-permissions"; exit 0;; esac
case " $* " in *" --yolo "*) ;; *) echo "stub: expected --yolo" >&2; exit 2;; esac
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
.gitconfig
.profile
.zprofile
.zshrc
bin
.calls
MD

git init -q
git add -A
git -c user.name=eval -c user.email=eval@example.com commit -q -m init
