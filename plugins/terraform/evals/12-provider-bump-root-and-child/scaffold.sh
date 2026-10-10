#!/usr/bin/env bash
# A root module (random ~> 3.6.1) and a child module (random ~> 3.6.0),
# the lock holding two h1 records, with a local
# filesystem mirror standing in for the registry (3.6.0, 3.6.1, 3.7.0, 3.7.1).
set -euo pipefail

git init -b main >/dev/null

for v in 3.6.0 3.6.1 3.7.0 3.7.1; do
  for p in linux_amd64 darwin_arm64; do
    d=mirror/registry.terraform.io/hashicorp/random/$v/$p
    mkdir -p "$d"
    printf '%s %s\n' "$v" "$p" >"$d/terraform-provider-random_v${v}_x5"
    chmod +x "$d/terraform-provider-random_v${v}_x5"
  done
done

# The harness gives each run its own HOME; never overwrite a real one.
if [ -e "$HOME/.terraformrc" ]; then
  echo "refusing to overwrite $HOME/.terraformrc" >&2
  exit 1
fi
cat >"$HOME/.terraformrc" <<RC
provider_installation {
  filesystem_mirror {
    path = "$PWD/mirror"
  }
}
RC

mkdir -p infra/prod modules/net .github/workflows
cat >infra/prod/versions.tf <<'HCL'
terraform {
  backend "s3" {}

  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.1"
    }
  }
}
HCL

cat >infra/prod/main.tf <<'HCL'
module "net" {
  source = "../../modules/net"
}
HCL

cat >modules/net/versions.tf <<'HCL'
terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6.0"
    }
  }
}
HCL

cat >infra/prod/.terraform.lock.hcl <<'HCL'
provider "registry.terraform.io/hashicorp/random" {
  version     = "3.6.1"
  constraints = "~> 3.6.1"
  hashes = [
    "h1:NwAJgK+hAyb44sXEmoaG8uO7c49UyBCLUstgvJb2JFA=",
    "h1:lkUCsaCF4ZxEkiI1jrfBFt6ypQk/m6e3mdJjlmRVKoI=",
  ]
}
HCL

cat >.github/workflows/lock.yml <<'YML'
name: lock
on: workflow_dispatch
jobs:
  lock:
    runs-on: ubuntu-latest
    steps:
      - run: terraform -chdir=infra/prod providers lock -fs-mirror=../../mirror -platform=linux_amd64 -platform=darwin_arm64
YML

printf 'mirror/\n.terraform/\n' >.gitignore

git add -A
git -c user.name=t -c user.email=t@example.com commit -q -m 'Add prod root module and net child module'
