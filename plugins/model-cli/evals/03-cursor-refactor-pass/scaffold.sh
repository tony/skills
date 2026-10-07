#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin

cat >bin/agent <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --yolo --sandbox -f --mode --dangerously-skip-permissions"; exit 0;; esac
case " $* " in *" -f "*) ;; *) echo "stub: expected -f" >&2; exit 2;; esac
echo "ANSWER: use a parameterized query: db.query(\"SELECT * FROM users WHERE id = ?\", (id,))"
SH
chmod +x bin/agent

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.profile
.zprofile
.zshrc
MD
