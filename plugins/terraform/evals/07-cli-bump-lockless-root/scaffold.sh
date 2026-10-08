#!/usr/bin/env bash
# One root module with a committed lock and one with none, so a plain init
# in the second would mint a lock and select providers.
set -euo pipefail

git init -b main >/dev/null

mkdir -p envs/prod envs/dev
for env in prod dev; do
  cat >"envs/$env/versions.tf" <<'HCL'
terraform {
  backend "s3" {}

  required_version = "~> 1.9.0"

  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
HCL
done

cat >envs/prod/.terraform.lock.hcl <<'HCL'
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

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "Add prod and dev root modules"
