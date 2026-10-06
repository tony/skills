#!/usr/bin/env bash
# Two root modules whose exact CLI pins already disagree.
set -euo pipefail

git init -b main >/dev/null

for env_ver in staging:1.9.5 prod:1.10.2; do
  env=${env_ver%%:*}
  ver=${env_ver#*:}
  mkdir -p "environments/$env"
  cat >"environments/$env/versions.tf" <<HCL
terraform {
  required_version = "= $ver"
}
HCL
done

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "Add root modules"
