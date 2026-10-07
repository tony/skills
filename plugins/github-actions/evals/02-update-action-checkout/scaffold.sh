#!/usr/bin/env bash
# A repository with a committed workflow, a bare local remote, and a stub gh
# that resolves and verifies tags for actions/checkout, actions/setup-node
# and astral-sh/setup-uv.
set -euo pipefail

git init -q --bare ../origin.git
git init -q -b main
git remote add origin ../origin.git
mkdir -p .github/workflows
cat >.github/workflows/ci.yml <<'YML'
name: CI
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

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
args="$*"
case "$args" in
  "repo view"*isFork*) echo '{"isFork":false}' ;;
  "repo view"*defaultBranchRef*) echo main ;;
  "repo view"*nameWithOwner*) echo acme/widgets ;;
  "api repos/actions/checkout/releases/latest"*) echo v4.2.2 ;;
  "api repos/actions/setup-node/releases/latest"*) echo v4.4.0 ;;
  "api repos/astral-sh/setup-uv/releases/latest"*) echo v6.1.0 ;;
  "api repos/actions/checkout/releases --paginate"*) printf 'v4.2.2\nv4.0.0\nv3.0.0\n' ;;
  "api repos/actions/setup-node/releases --paginate"*) printf 'v4.0.0\n' ;;
  "api repos/astral-sh/setup-uv/releases --paginate"*) printf 'v6.0.0\nv5.0.0\n' ;;
  "api repos/"*"/git/ref/tags/v4"*|"api repos/"*"/git/ref/tags/v6"*) echo '{}' ;;
  "api repos/"*"/releases/tags/"*tag_name*) t=${args#*releases/tags/}; echo "${t%% *}" ;;
  "api repos/"*"/releases/tags/"*) echo "Release notes: raises the minimum runtime." ;;
  "pr list"*) echo '[]' ;;
  *) echo "unsupported: $args" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
