#!/usr/bin/env bash
# A repository on a feature branch with a bare local remote, pinning
# actions/checkout@v3, and a stub gh that verifies tags v4 and v4.2.2.
set -euo pipefail

git init -q --bare ../origin.git
git init -q -b main
git remote add origin ../origin.git
mkdir -p .github/workflows
cat >.github/workflows/ci.yml <<'YML'
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: echo ok
YML
git add .github
git commit -q -m 'Add CI'
git push -q origin main
git fetch -q origin
git remote set-head origin main >/dev/null
git checkout -q -b feature/wip
echo wip >notes.txt

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
args="$*"
case "$args" in
  "repo view"*isFork*) echo '{"isFork":false}' ;;
  "repo view"*defaultBranchRef*) echo main ;;
  "repo view"*nameWithOwner*) echo acme/widgets ;;
  "api repos/actions/checkout/releases/latest"*) echo v4.2.2 ;;
  "api repos/actions/checkout/releases --paginate"*) printf 'v4.2.2\nv4.0.0\nv3.0.0\n' ;;
  "api repos/actions/checkout/git/ref/tags/v4"*|"api repos/actions/checkout/git/ref/tags/v4.2.2"*) echo '{}' ;;
  "api repos/actions/checkout/releases/tags/"*tag_name*) t=${args#*releases/tags/}; echo "${t%% *}" ;;
  "api repos/actions/checkout/releases/tags/v4"*) echo "v4 runs on a newer Node runtime." ;;
  "pr list"*) echo '[]' ;;
  *) echo "unsupported: $args" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
