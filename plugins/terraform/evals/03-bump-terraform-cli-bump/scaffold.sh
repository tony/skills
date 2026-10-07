#!/usr/bin/env bash
# Two root modules whose exact CLI pins already disagree, each with a
# committed lock file.
set -euo pipefail

git init -b main >/dev/null

for env_ver in staging:1.9.5 prod:1.10.2; do
  env=${env_ver%%:*}
  ver=${env_ver#*:}
  mkdir -p "environments/$env"
  cat >"environments/$env/versions.tf" <<HCL
terraform {
  backend "s3" {}

  required_version = "= $ver"

  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
HCL
  cat >"environments/$env/.terraform.lock.hcl" <<'HCL'
provider "registry.terraform.io/hashicorp/random" {
  version     = "3.6.0"
  constraints = "~> 3.6"
  hashes = [
    "h1:aaa=",
    "h1:bbb=",
    "zh:111",
  ]
}
HCL
done

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "Add root modules"
