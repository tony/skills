#!/usr/bin/env bash
# A root module whose lock tracks two platforms for random, with a local
# filesystem mirror standing in for the registry (3.6.0, 3.7.0); no CI file records the platforms.
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

mkdir -p infra/prod
cat >infra/prod/versions.tf <<'HCL'
terraform {
  backend "s3" {}

  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
HCL

cat >infra/prod/.terraform.lock.hcl <<'HCL'
provider "registry.terraform.io/hashicorp/random" {
  version     = "3.6.0"
  constraints = "~> 3.6"
  hashes = [
    "h1:aaa=",
    "h1:bbb=",
  ]
}
HCL

printf 'mirror/\n.terraform/\n' >.gitignore

git add -A
git -c user.name=t -c user.email=t@example.com commit -q -m 'Add prod root module'
