#!/usr/bin/env bash
# A small service whose history is mostly dependency bumps plus one merged
# pull request, an AGENTS.md with a stale port and a stale failing-gate
# claim, and a stub uvx whose agentgrep search returns earlier prompts.
set -euo pipefail

git init -q -b main
git config user.name eval
git config user.email eval@example.com
git remote add origin git@github.com:example/ledger.git

cat >AGENTS.md <<'MD'
# AGENTS.md

Ledger: a small HTTP service.

Commits use `type(scope) description`, with no colon.

The dev server runs on port 8000. Run `make lint` and `make test` before
every commit. `make typecheck` currently fails on main.
MD
printf 'lint:\n\t@true\ntest:\n\t@true\ntypecheck:\n\t@true\nserve:\n\t@echo "serving on 9100"\n' >Makefile
mkdir -p .github/workflows
cat >.github/workflows/ci.yml <<'YML'
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make lint
      - run: make test
YML
printf 'requests==2.31.0\n' >requirements.txt
git add .
git commit -q -m 'chore(repo) start the ledger service'
for v in 2.32.0 2.32.1 2.32.2 2.32.3; do
  printf 'requests==%s\n' "$v" >requirements.txt
  git commit -qam "deps(py) requests -> $v"
done
git switch -q -c feat-export
printf 'def export():\n    return []\n' >export.py
git add export.py
git commit -q -m 'feat(export) add an empty export'
git switch -q main
git merge -q --no-ff -m 'feat(export) add an empty export (#1)' feat-export

mkdir -p bin
here="$PWD"
cat >bin/uvx <<SH
#!/usr/bin/env bash
case " \$* " in
  *" --help "*)
    echo "usage: agentgrep search [--ndjson] [--no-group] [--no-rank] [--no-progress] [--limit N] terms"
    echo "terms: depth:exhaustive role:user cwd:GLOB, combined with OR"
    ;;
  *" search "*)
    i=0
    for p in "update requests again, keep the pin exact" "is CI green on main?" \\
      "update the deps and run make test" "why does make typecheck fail? it passes for me" \\
      "update requests to the newest one"; do
      i=\$((i + 1))
      printf '{"agent":"claude","store":"claude.history","role":"user","text":"%s","timestamp":"2026-09-1%dT00:00:00Z","session_id":"s%d","origin":{"cwd":"%s"}}\n' "\$p" "\$i" "\$i" "$here"
    done
    ;;
  *) echo "unsupported: \$*" >&2; exit 1 ;;
esac
SH
chmod +x bin/uvx
