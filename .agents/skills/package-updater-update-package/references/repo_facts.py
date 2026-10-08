#!/usr/bin/env python3
"""Print per-repository scope facts as JSON: remotes, fork signal, default branch, pins.

``repo_facts.py [--fetch] REPO...`` prints one JSON object per repository.
Pins are read from the default branch ref, not the working tree. With
``--fetch`` the remote is fetched first and ``fetch_ok`` reports the result.

``repo_facts.py --lock-diff REPO [LOCKFILE...]`` compares each lockfile
(default: ``uv.lock``, ``poetry.lock``, ``Cargo.lock`` in REPO) at ``HEAD``
with the working tree and splits the changed packages into ``majors`` (a new
major, or for 0.x a new minor) and ``in_range``.
"""

# ruff: noqa: S603, S607, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

LOCKFILES = ("uv.lock", "poetry.lock", "Cargo.lock")
PIN_FILES = (".tool-versions", ".nvmrc", ".python-version", ".ruby-version")


def _git(repo: str, *args: str) -> tuple[int, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    done = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=False, env=env
    )
    return done.returncode, done.stdout.strip()


def _remotes(repo: str) -> dict[str, str]:
    _, out = _git(repo, "remote", "-v")
    found: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            found.setdefault(parts[0], parts[1])
    return found


def _default_branch(repo: str, remote: str) -> str | None:
    code, out = _git(repo, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD")
    if code == 0 and out:
        return out.split("/", 1)[1]
    code, out = _git(repo, "ls-remote", "--symref", remote, "HEAD")
    match = re.search(r"^ref: refs/heads/(\S+)\s+HEAD", out, re.MULTILINE)
    return match.group(1) if code == 0 and match else None


def _show(repo: str, ref: str, path: str) -> str | None:
    code, out = _git(repo, "show", f"{ref}:{path}")
    return out if code == 0 else None


def _mise_tools(text: str) -> dict[str, str]:
    """Read ``tool = "version"`` and ``tool = ["version", ...]`` lines under ``[tools]``."""
    tools: dict[str, str] = {}
    in_tools = False
    for raw in text.splitlines():
        line = raw.split("#")[0].strip()
        if line.startswith("["):
            in_tools = line == "[tools]"
            continue
        match = re.match(r"""["']?([^"'=\s]+)["']?\s*=\s*(.*)$""", line)
        if in_tools and match:
            value = re.search(r"""["']([^"']+)["']""", match.group(2))
            tools[match.group(1)] = value.group(1) if value else match.group(2).strip()
    return tools


def _pins(repo: str, ref: str) -> dict[str, object]:
    pins: dict[str, object] = {}
    for name in PIN_FILES:
        text = _show(repo, ref, name)
        if text is None:
            continue
        if name == ".tool-versions":
            tools = {}
            for line in text.splitlines():
                parts = line.split("#")[0].split()
                if len(parts) >= 2:
                    tools[parts[0]] = parts[1]
            pins[name] = tools
        else:
            pins[name] = text.splitlines()[0].strip() if text else ""
    for name in ("mise.toml", ".mise.toml"):
        mise = _show(repo, ref, name)
        if mise is not None:
            pins[name] = _mise_tools(mise)
    toolchain = _show(repo, ref, "rust-toolchain.toml")
    if toolchain is not None:
        match = re.search(r'^\s*channel\s*=\s*"([^"]+)"', toolchain, re.MULTILINE)
        pins["rust-toolchain.toml"] = match.group(1) if match else ""
    plain = _show(repo, ref, "rust-toolchain")
    if plain is not None:
        pins["rust-toolchain"] = plain.splitlines()[0].strip() if plain else ""
    gomod = _show(repo, ref, "go.mod")
    if gomod is not None:
        go = {}
        for key in ("go", "toolchain"):
            match = re.search(rf"^{key}\s+(\S+)", gomod, re.MULTILINE)
            if match:
                go[key] = match.group(1)
        pins["go.mod"] = go
    package = _show(repo, ref, "package.json")
    if package is not None:
        try:
            data = json.loads(package)
        except ValueError:
            data = {}
        picked: dict[str, object] = {k: data[k] for k in ("packageManager", "engines") if k in data}
        if picked:
            pins["package.json"] = picked
    return pins


def facts(repo: str, *, fetch: bool = False) -> dict[str, object]:
    """Collect scope facts for one repository."""
    code, top = _git(repo, "rev-parse", "--show-toplevel")
    if code:
        return {"path": repo, "error": "not a git repository"}
    _, git_dir = _git(repo, "rev-parse", "--path-format=absolute", "--git-dir")
    _, common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    _, super_wt = _git(repo, "rev-parse", "--show-superproject-working-tree")
    remotes = _remotes(repo)
    remote = "origin" if "origin" in remotes else next(iter(remotes), None)
    out: dict[str, object] = {
        "path": top,
        "linked_worktree": git_dir != common,
        "submodule": bool(super_wt),
        "remotes": remotes,
        "remote": remote,
        "fork_signal": "upstream" in remotes,
        "default_branch": None,
        "branch": _git(repo, "branch", "--show-current")[1],
        "dirty": bool(_git(repo, "status", "--porcelain", "--untracked-files=no")[1]),
    }
    if remote is None:
        ref = str(out["branch"] or "HEAD")
        out["pins_ref"] = ref
        out["pins"] = _pins(repo, ref)
        return out
    if fetch:
        out["fetch_ok"] = _git(repo, "fetch", remote)[0] == 0
    default = _default_branch(repo, remote)
    out["default_branch"] = default
    if default is None:
        return out
    ref = f"{remote}/{default}"
    if _git(repo, "rev-parse", "--verify", "--quiet", ref)[0] != 0:
        ref = default
    behind = _git(repo, "rev-list", "--count", f"{default}..{remote}/{default}")
    out["behind_remote"] = int(behind[1]) if behind[0] == 0 and behind[1] else None
    out["pins_ref"] = ref
    out["pins"] = _pins(repo, ref)
    return out


def _lock_versions(text: str) -> dict[str, set[str]]:
    """Map package name to its versions from ``[[package]]`` tables (uv, Poetry, Cargo)."""
    found: dict[str, set[str]] = {}
    for block in re.split(r"^\[\[package\]\]\s*$", text, flags=re.MULTILINE)[1:]:
        name = re.search(r'^name\s*=\s*"([^"]+)"', block, re.MULTILINE)
        version = re.search(r'^version\s*=\s*"([^"]+)"', block, re.MULTILINE)
        if name and version:
            found.setdefault(name.group(1), set()).add(version.group(1))
    return found


def _series(version: str) -> tuple[int, ...]:
    """Return ``(major,)``, or ``(0, minor)`` for a 0.x version."""
    nums = [int(n) for n in re.findall(r"\d+", version.split("+", maxsplit=1)[0])[:2]]
    nums += [0] * (2 - len(nums))
    return (nums[0],) if nums[0] else (0, nums[1])


def lock_changes(old: str, new: str) -> dict[str, list[dict[str, object]]]:
    """Split the packages that differ between two lock texts into majors and in-range moves."""
    before, after = _lock_versions(old), _lock_versions(new)
    majors: list[dict[str, object]] = []
    in_range: list[dict[str, object]] = []
    for name in sorted(set(before) | set(after)):
        gone = sorted(before.get(name, set()) - after.get(name, set()))
        came = sorted(after.get(name, set()) - before.get(name, set()))
        if not gone and not came:
            continue
        entry: dict[str, object] = {"name": name, "from": gone, "to": came}
        old_series = {_series(v) for v in before.get(name, set())}
        crossed = bool(gone) and any(_series(v) not in old_series for v in came)
        (majors if crossed else in_range).append(entry)
    return {"majors": majors, "in_range": in_range}


def lock_diff(repo: str, lockfiles: list[str]) -> dict[str, object]:
    """Compare each lockfile at HEAD with the working tree."""
    out: dict[str, object] = {"path": repo}
    for name in lockfiles or [n for n in LOCKFILES if (Path(repo) / n).is_file()]:
        old = _show(repo, "HEAD", f"./{name}")
        try:
            new = (Path(repo) / name).read_text()
        except OSError:
            out[name] = {"error": "not readable"}
            continue
        out[name] = lock_changes(old or "", new)
    return out


def main(argv: list[str]) -> int:
    """Print one JSON line per repository."""
    if argv[:1] == ["--lock-diff"] and len(argv) > 1:
        sys.stdout.write(json.dumps(lock_diff(argv[1], argv[2:])) + "\n")
        return 0
    fetch = "--fetch" in argv
    repos = [a for a in argv if a != "--fetch"] or ["."]
    for repo in repos:
        if not Path(repo).is_dir():
            sys.stdout.write(json.dumps({"path": repo, "error": "not a directory"}) + "\n")
            continue
        sys.stdout.write(json.dumps(facts(repo, fetch=fetch)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
