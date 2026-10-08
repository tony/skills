#!/usr/bin/env bash
# Two root modules (prod, staging) share a child module that declares random.
# A run limited to infra/prod would raise the child's constraint and strand
# infra/staging's lock.
set -euo pipefail

git init -b main >/dev/null

for v in 3.6.0 3.7.0; do
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

mkdir -p infra/prod infra/staging modules/net
for env in prod staging; do
  cat >infra/$env/versions.tf <<'HCL'
terraform {
  backend "s3" {}
}
HCL
  cat >infra/$env/main.tf <<'HCL'
module "net" {
  source = "../../modules/net"
}
HCL
  cat >infra/$env/.terraform.lock.hcl <<'HCL'
provider "registry.terraform.io/hashicorp/random" {
  version     = "3.6.0"
  constraints = "~> 3.6.0"
  hashes = [
    "h1:aaa=",
    "h1:bbb=",
  ]
}
HCL
done

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

printf 'mirror/\n.terraform/\n' >.gitignore

git add -A
git -c user.name=t -c user.email=t@example.com commit -q -m 'Add prod and staging root modules sharing a net module'
