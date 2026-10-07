#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin

cat >bin/agy <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --yolo --sandbox -f --mode --dangerously-skip-permissions"; exit 0;; esac
echo "Authentication required: log in first" >&2
exit 1
SH
chmod +x bin/agy

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
