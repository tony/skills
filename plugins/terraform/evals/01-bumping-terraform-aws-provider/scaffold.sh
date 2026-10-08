#!/usr/bin/env bash
# Root and child module declare the aws provider at different constraints.
set -euo pipefail

git init -b main >/dev/null

mkdir -p modules/network
cat >versions.tf <<'HCL'
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.60.0"
    }
  }
}
HCL
cat >modules/network/versions.tf <<'HCL'
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.55.0"
    }
  }
}
HCL

git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "Add root and network modules"
