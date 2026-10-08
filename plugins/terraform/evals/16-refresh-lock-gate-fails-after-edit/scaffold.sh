#!/usr/bin/env bash
# A root module whose lock tracks two platforms for random, a local
# filesystem mirror (3.6.0, 3.7.1), and a repository gate that rejects any
# random version other than 3.6.0.
set -euo pipefail

git init -b main >/dev/null

for v in 3.6.0 3.7.1; do
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

mkdir -p infra/prod .github/workflows
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

cat >AGENTS.md <<'MD'
# Conventions

Run `./scripts/check.sh` before committing; it must pass.
MD

mkdir -p scripts
cat >scripts/check.sh <<'SH'
#!/usr/bin/env bash
# Gate: the legacy consumer of this root module only works with random 3.6.0.
if grep -q 'version     = "3.6.0"' infra/prod/.terraform.lock.hcl; then
  echo "check: ok"
else
  echo "check: FAILED: random must stay at 3.6.0" >&2
  exit 1
fi
SH
chmod +x scripts/check.sh

git add -A
git -c user.name=t -c user.email=t@example.com commit -q -m 'Add prod root module'
