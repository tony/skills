#!/usr/bin/env python3
"""Deterministic pin checks for GitHub Actions workflows.

``inventory REPO...`` prints one JSON object per repository (a clone path or an
``owner/name`` slug) listing every ``uses:`` pin on its default branch.
``majors ACTION PIN TARGET`` prints the first release of each major above PIN's
major and at or below TARGET's. ``tag ACTION TAG`` exits 0 when the tag exists,
1 when it does not (HTTP 404), and 3 when the lookup failed (auth, rate limit,
network) so the tag could not be checked.

Every git call runs as ``git -C <path>`` and every gh call names its slug, so
the current directory never decides which repository is read.
"""

# ruff: noqa: S603, PLR2004, TRY003, EM102
# pyright: reportUnusedCallResult=false, reportAny=false
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>[^\s#]+)\s*(?:#\s*(?P<note>.*))?$")
SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")
REMOTE_SLUG = re.compile(r"github\.com[:/](?P<slug>[\w.-]+/[\w.-]+?)(?:\.git)?/?$")
WORKFLOW = re.compile(r"^\.github/(workflows|actions)/.+\.ya?ml$")
MAJOR = re.compile(r"^v(\d+)(?:\.(\d+))?(?:\.(\d+))?$")


def parse_uses(line: str) -> dict[str, str] | None:
    """Parse one ``uses:`` line; return None when it is not one.

    >>> parse_uses("  - uses: actions/checkout@v3")["ref"]
    'v3'
    >>> parse_uses("uses: a/b/sub@abc123 # v1.2.3")["note"]
    'v1.2.3'
    >>> parse_uses("uses: ./local")["kind"]
    'local'
    >>> parse_uses("run: echo uses: x") is None
    True
    """
    m = USES.match(line)
    if not m:
        return None
    raw = m.group("ref").strip("'\"")
    note = (m.group("note") or "").strip()
    if raw.startswith("./"):
        return {"uses": raw, "kind": "local", "action": raw, "ref": "", "note": note}
    if raw.startswith("docker://"):
        return {"uses": raw, "kind": "docker", "action": raw, "ref": "", "note": note}
    action, _, ref = raw.partition("@")
    return {"uses": raw, "kind": "action", "action": action, "ref": ref, "note": note}


def action_repo(action: str) -> str:
    """Return ``owner/repo`` for ``owner/repo/subpath``.

    >>> action_repo("github/codeql-action/init")
    'github/codeql-action'
    """
    return "/".join(action.split("/")[:2])


def first_of_majors(tags: list[str], above: int, upto: int) -> list[str]:
    """Pick the first release tag of each major in (above, upto].

    Prefers ``vN.0.0``, then ``vN.0``, then ``vN``.

    >>> first_of_majors(["v4.2.2", "v4.0.0", "v5.0.0", "v6.0.0", "v6.1.0"], 3, 5)
    ['v4.0.0', 'v5.0.0']
    >>> first_of_majors(["v4", "v5", "v5.1.0"], 3, 5)
    ['v4', 'v5']
    """
    found: dict[int, dict[int, str]] = {}
    for tag in tags:
        m = MAJOR.match(tag)
        if not m:
            continue
        major = int(m.group(1))
        rank = {(None, None): 2, ("0", None): 1, ("0", "0"): 0}.get(
            (m.group(2), m.group(3)),
        )
        if rank is None or not above < major <= upto:
            continue
        found.setdefault(major, {})[rank] = tag
    return [found[n][min(found[n])] for n in sorted(found)]


def _major_of(ref: str) -> int:
    m = MAJOR.match(ref)
    if not m:
        raise SystemExit(f"not a version: {ref}")
    return int(m.group(1))


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def _out(*args: str) -> str:
    done = _run(*args)
    if done.returncode:
        sys.stderr.write(done.stderr or f"{args[0]} failed\n")
        raise SystemExit(1)
    return done.stdout


def _remote(path: str) -> str:
    names = _out("git", "-C", path, "remote").split()
    if "origin" in names:
        return "origin"
    if len(names) == 1:
        return names[0]
    raise SystemExit(f"{path}: no origin and {len(names)} remotes; name one")


def _slug_from_remote(path: str, remote: str) -> str:
    url = _out("git", "-C", path, "config", "--get", f"remote.{remote}.url").strip()
    m = REMOTE_SLUG.search(url)
    if not m:
        raise SystemExit(f"{path}: remote {remote} is not a github.com URL")
    return m.group("slug")


def _default_branch(slug: str) -> str:
    return _out(
        "gh", "repo", "view", slug, "--json", "defaultBranchRef",
        "--jq", ".defaultBranchRef.name",
    ).strip()  # fmt: skip


def _scan(files: dict[str, str]) -> tuple[list[dict[str, str]], list[str]]:
    pins: list[dict[str, str]] = []
    for name in sorted(files):
        for no, line in enumerate(files[name].splitlines(), 1):
            pin = parse_uses(line)
            if pin:
                pins.append({"file": name, "line": str(no), **pin})
    return pins, sorted(files)


def _read_clone(path: str, remote: str, default: str) -> dict[str, str]:
    ref = f"{remote}/{default}"
    names = _out("git", "-C", path, "ls-tree", "-r", "--name-only", ref, ".github")
    return {
        n: _out("git", "-C", path, "show", f"{ref}:{n}")
        for n in names.splitlines()
        if WORKFLOW.match(n)
    }


def _read_slug(slug: str, default: str) -> dict[str, str]:
    tree = _out(
        "gh", "api", f"repos/{slug}/git/trees/{default}?recursive=1",
        "--jq", '.tree[] | select(.type == "blob") | .path',
    )  # fmt: skip
    return {
        n: _out(
            "gh", "api", "-H", "Accept: application/vnd.github.raw+json",
            f"repos/{slug}/contents/{n}?ref={default}",
        )
        for n in tree.splitlines()
        if WORKFLOW.match(n)
    }  # fmt: skip


def inventory(repo: str) -> dict[str, object]:
    """Inventory one repository by clone path or slug."""
    if Path(repo).is_dir():
        remote = _remote(repo)
        _out("git", "-C", repo, "fetch", remote)
        slug = _slug_from_remote(repo, remote)
        default = _default_branch(slug)
        files = _read_clone(repo, remote, default)
        where: dict[str, object] = {"path": repo, "remote": remote}
    elif SLUG.match(repo):
        slug = repo
        default = _default_branch(slug)
        files = _read_slug(slug, default)
        where = {"path": None}
    else:
        raise SystemExit(f"not a directory or owner/name slug: {repo}")
    pins, scanned = _scan(files)
    return {"slug": slug, "default": default, **where, "files": scanned, "pins": pins}


def tag_status(action: str, tag: str) -> tuple[str, str]:
    """Return ``exists``, ``missing`` (HTTP 404), or ``unchecked`` plus gh's error."""
    done = _run("gh", "api", f"repos/{action_repo(action)}/git/ref/tags/{tag}")
    if done.returncode == 0:
        return "exists", ""
    err = done.stderr.strip()
    if "HTTP 404" in err:
        return "missing", err
    return "unchecked", err


def majors(action: str, pin: str, target: str) -> list[str]:
    """List the first release of each major between pin and target."""
    repo = action_repo(action)
    above, upto = _major_of(pin), _major_of(target)
    done = _run(
        "gh", "api", f"repos/{repo}/releases", "--paginate", "--jq", ".[].tag_name",
    )  # fmt: skip
    tags = done.stdout.split() if done.returncode == 0 else []
    picked = first_of_majors(tags, above, upto)
    if picked:
        return picked
    refs = _out("git", "ls-remote", "--tags", "--refs", f"https://github.com/{repo}.git")
    tags = [r.rsplit("refs/tags/", 1)[-1] for r in refs.splitlines()]
    return first_of_majors(tags, above, upto)


def main(argv: list[str]) -> int:
    """Run the CLI."""
    if len(argv) >= 2 and argv[0] == "inventory":
        for repo in argv[1:]:
            print(json.dumps(inventory(repo)))
        return 0
    if len(argv) == 4 and argv[0] == "majors":
        print("\n".join(majors(argv[1], argv[2], argv[3])))
        return 0
    if len(argv) == 3 and argv[0] == "tag":
        status, err = tag_status(argv[1], argv[2])
        if status == "unchecked":
            sys.stderr.write(f"could not be checked: {err or 'gh failed'}\n")
            return 3
        print(status)
        return 0 if status == "exists" else 1
    sys.stderr.write(__doc__ or "")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
