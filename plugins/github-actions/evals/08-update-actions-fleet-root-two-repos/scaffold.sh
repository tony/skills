#!/usr/bin/env bash
# Two clones under fleet/, on different default branches, each pinning
# actions/checkout at a different old major, plus a stub gh that answers only
# when a command names the repository's slug.
set -euo pipefail

git init -q -b main

make_repo() {
  local name=$1 branch=$2 pin=$3
  git init -q --bare "remotes/$name.git"
  git init -q -b "$branch" "fleet/$name"
  git -C "fleet/$name" remote add origin "https://github.com/acme/$name.git"
  git -C "fleet/$name" config "url.$PWD/remotes/$name.git.insteadOf" "https://github.com/acme/$name.git"
  mkdir -p "fleet/$name/.github/workflows"
  cat >"fleet/$name/.github/workflows/ci.yml" <<YML
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@$pin
      - run: echo ok
YML
  git -C "fleet/$name" add .github
  git -C "fleet/$name" commit -q -m 'Add CI'
  git -C "fleet/$name" push -q origin "$branch"
  git -C "fleet/$name" fetch -q origin
  git -C "fleet/$name" remote set-head origin "$branch" >/dev/null
}

make_repo alpha main v3
make_repo beta trunk v2

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
args="$*"
case "$args" in
  "repo view acme/alpha"*isFork*|"repo view acme/beta"*isFork*) echo '{"isFork":false}' ;;
  "repo view acme/alpha"*defaultBranchRef*) echo main ;;
  "repo view acme/beta"*defaultBranchRef*) echo trunk ;;
  "repo view acme/alpha"*nameWithOwner*) echo acme/alpha ;;
  "repo view acme/beta"*nameWithOwner*) echo acme/beta ;;
  "api repos/actions/checkout/releases/latest"*) echo v4.2.2 ;;
  "api repos/actions/checkout/releases --paginate"*) printf 'v4.2.2\nv4.0.0\nv3.0.0\nv2.0.0\n' ;;
  "api repos/actions/checkout/git/ref/tags/v4"*) echo '{}' ;;
  "api repos/acme/alpha/git/trees/main"*) echo .github/workflows/ci.yml ;;
  "api repos/acme/beta/git/trees/trunk"*) echo .github/workflows/ci.yml ;;
  "api repos/actions/checkout/releases/tags/"*tag_name*) t=${args#*releases/tags/}; echo "${t%% *}" ;;
  "api repos/actions/checkout/releases/tags/"*) echo "v4 runs on a newer Node runtime." ;;
  "pr list"*) echo '[]' ;;
  *) echo "unsupported: $args" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
