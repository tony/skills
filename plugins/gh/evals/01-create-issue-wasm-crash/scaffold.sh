#!/usr/bin/env bash
# A stub gh that is not logged in, so the result never depends on the
# runner's ambient login.
set -euo pipefail

git init -b main >/dev/null
echo "# demo" >README.md
git add README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
echo "You are not logged into any GitHub hosts. To log in, run: gh auth login" >&2
exit 1
SH
chmod +x bin/gh
