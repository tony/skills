#!/usr/bin/env bash
# A root module whose lock has three h1 records for aws and one for random,
# so a file-wide maximum would report 3 for both.
set -euo pipefail

git init -b main >/dev/null

mkdir -p infra/prod
cat >infra/prod/versions.tf <<'HCL'
terraform {
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
HCL

cat >infra/prod/.terraform.lock.hcl <<'HCL'
provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.60.0"
  constraints = "~> 5.60"
  hashes = [
    "h1:aaa=",
    "h1:bbb=",
    "h1:ccc=",
    "zh:111",
    "zh:222",
  ]
}

provider "registry.terraform.io/hashicorp/random" {
  version     = "3.6.0"
  constraints = "~> 3.6"
  hashes = [
    "h1:ddd=",
    "zh:333",
  ]
}
HCL

git add -A
git -c user.name=t -c user.email=t@example.com commit -q -m 'Add prod root module'
