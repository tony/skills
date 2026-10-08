#!/usr/bin/env bash
# Builds a project whose src/ holds one nav with a margin stacked on a gap.
set -euo pipefail

mkdir -p src/components
cat >src/components/Nav.tsx <<'TSX'
export function Nav() {
  return (
    <nav className="flex items-center gap-3">
      <a className="px-2" href="/">Home</a>
      <a className="px-2" href="/about">About</a>
      <a className="px-2 me-4" href="/docs">Docs</a>
      <a className="px-2" href="/contact">Contact</a>
    </nav>
  );
}
TSX
cat >src/components/Footer.tsx <<'TSX'
export function Footer() {
  return <footer className="p-4 text-sm">Copyright</footer>;
}
TSX
echo '{"dependencies":{"tailwindcss":"^4.0.0"}}' >package.json

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.profile
.zprofile
.zshrc
MD
