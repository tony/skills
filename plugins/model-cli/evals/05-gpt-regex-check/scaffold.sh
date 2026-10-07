#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin

cat >bin/codex <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*) echo "  --yolo --sandbox -f --mode --dangerously-skip-permissions"; exit 0;; esac
case " $* " in *" --yolo "*) ;; *) echo "stub: expected --yolo" >&2; exit 2;; esac
echo "ANSWER: \\w is Unicode-aware in Python 3 str patterns, so non-ASCII local parts match."
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
MD
