#!/usr/bin/env bash
# Builds a fixture file and a stub `codex` that prints a canned plan.
set -euo pipefail

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --yolo --sandbox -f --mode --dangerously-skip-permissions"; exit 0;; esac
case " $* " in *" --sandbox "*) ;; *) echo "stub: expected --sandbox" >&2; exit 2;; esac
case " $* " in *" read-only "*) ;; *) echo "stub: expected read-only" >&2; exit 2;; esac
case " $* " in *" --yolo "*) echo "stub: unexpected --yolo" >&2; exit 2;; esac
echo "PLAN: validate that payload is a dict with a string name in app.py:handle."
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
