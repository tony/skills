#!/usr/bin/env bash
# An empty repo with one commit and no remote, plus a stub gh that fails as if
# unauthenticated, so the case never reaches a real PR.
set -euo pipefail

git init -b main >/dev/null

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
bin
MD

echo "# demo" >README.md
git add .gitignore README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
echo "You are not logged into any GitHub hosts. To log in, run: gh auth login" >&2
exit 4
SH
chmod +x bin/gh
