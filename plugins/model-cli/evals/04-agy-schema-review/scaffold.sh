#!/usr/bin/env bash
# Fixture binaries keep delegated runs offline.
set -euo pipefail
mkdir -p .eval-state/prompts

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/agy <<'SH'
#!/usr/bin/env bash
[ "${1:-}" = models ] && { printf '%s\n' 'Fetching available models...' "gemini-3.1-pro-high$(printf '\t')Gemini 3.1 Pro (High)" "gemini-3.8-flash-high$(printf '\t')Gemini 3.8 Flash (High)"; exit 0; }
case " $* " in *" --help "*) echo "  --dangerously-skip-permissions --mode --model -p"; exit 0;; esac
n=$(cat .calls 2>/dev/null || echo 0)
echo $((n + 1)) >.calls
echo "Error: 429 Too Many Requests" >&2
exit 1
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
