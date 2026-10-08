#!/usr/bin/env bash
# A committed repository holding a small argparse CLI whose --help is ungrouped.
set -euo pipefail

git init -b main >/dev/null
git config user.email eval@example.com
git config user.name eval

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
MD

mkdir -p src
cat >src/acme.py <<'PY'
"""Acme CLI."""
import argparse


def build_parser():
    p = argparse.ArgumentParser(prog="acme", description="Manage Acme projects.")
    p.add_argument("-v", "--verbose", action="store_true", help="Print more detail.")
    sub = p.add_subparsers(dest="command")
    for name, text in [
        ("init", "Create a new project in the current directory."),
        ("deploy", "Ship the current build. Takes a target and optional flags."),
        ("logs", "Stream logs from a running deployment."),
        ("login", "Sign in to your Acme account."),
        ("logout", "Sign out."),
        ("completion", "Generate shell completion scripts."),
    ]:
        sub.add_parser(name, help=text)
    return p
PY
git add .gitignore src/acme.py
git commit -q -m 'cli(feat) Add the acme parser'
