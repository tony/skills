#!/usr/bin/env python3
"""Deterministic pin checks for GitHub Actions workflows.

``inventory REPO...`` prints one JSON object per repository (a clone path or an
``owner/name`` slug) listing every ``uses:`` pin on its default branch.
``majors ACTION PIN TARGET`` prints the first release of each major above PIN's
major and at or below TARGET's. ``tag ACTION TAG`` exits 0 when the tag exists,
1 when it does not (HTTP 404), and 3 when the lookup failed (auth, rate limit,
network) so the tag could not be checked.

Clone commands name their path; GitHub CLI queries name their repository and
github.com host independently of the working directory and host environment.
"""

# ruff: noqa: S603, S607, PLR2004, TRY003, EM102
# pyright: reportUnusedCallResult=false, reportAny=false
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>[^\s#]+)\s*(?:#\s*(?P<note>.*))?$")
SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")
SCP_REMOTE = re.compile(r"(?:[\w.-]+@)?github\.com:(?P<path>.+)", re.IGNORECASE | re.ASCII)
WORKFLOW = re.compile(r"\.github/(workflows|actions)/.+\.ya?ml", re.DOTALL)
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


def _github_slug(url: str) -> str | None:
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or any(
        c in url for c in "\\?#"
    ):
        return None
    if "://" in url:
        try:
            parsed = urlsplit(url)
            # urlsplit defers port validation until this property is read.
            _ = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme not in {"https", "ssh"}
            or parsed.hostname != "github.com"
            or parsed.netloc.count("@") > 1
        ):
            return None
        path = parsed.path.removeprefix("/")
    else:
        match = SCP_REMOTE.fullmatch(url)
        if not match:
            return None
        path = match.group("path")
    slug = path.removesuffix("/").removesuffix(".git")
    if not SLUG.fullmatch(slug) or any(part in {".", ".."} for part in slug.split("/")):
        return None
    return slug


def _slug_from_remote(path: str, remote: str) -> str:
    url = _out("git", "-C", path, "config", "--get-all", f"remote.{remote}.url")
    slug = _github_slug(url.removesuffix("\n"))
    if slug is None:
        raise SystemExit(f"{path}: remote {remote} is not a github.com URL")
    return slug


def _default_branch(slug: str) -> str:
    return _out(
        "gh", "repo", "view", f"https://github.com/{slug}", "--json", "defaultBranchRef",
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
    # Text-mode newline conversion would change CR and CRLF inside filenames.
    done = subprocess.run(
        ["git", "-C", path, "ls-tree", "-r", "-z", "--name-only", ref, ".github"],
        capture_output=True,
        check=False,
    )
    if done.returncode:
        sys.stderr.write(done.stderr.decode(errors="replace") or "git ls-tree failed\n")
        raise SystemExit(1)
    names = (os.fsdecode(name) for name in done.stdout.split(b"\0"))
    return {
        n: _out("git", "-C", path, "show", f"{ref}:{n}") for n in names if WORKFLOW.fullmatch(n)
    }


def _tree_paths(slug: str, tree_sha: str) -> list[str]:
    tree = json.loads(_out(
        "gh", "api", "--hostname", "github.com",
        f"repos/{slug}/git/trees/{tree_sha}?recursive=1",
    ))  # fmt: skip
    if not tree["truncated"]:
        return [
            entry["path"]
            for entry in tree["tree"]
            if entry["type"] == "blob" and WORKFLOW.fullmatch(entry["path"])
        ]

    names: list[str] = []
    pending = [("", tree_sha)]
    while pending:
        prefix, sha = pending.pop()
        subtree = json.loads(_out(
            "gh", "api", "--hostname", "github.com", f"repos/{slug}/git/trees/{sha}",
        ))  # fmt: skip
        if subtree["truncated"]:
            raise SystemExit(f"{slug}: incomplete non-recursive tree {sha}")
        for entry in subtree["tree"]:
            name = prefix + entry["path"]
            if entry["type"] == "blob" and WORKFLOW.fullmatch(name):
                names.append(name)
            elif entry["type"] == "tree" and (
                name in {".github", ".github/workflows", ".github/actions"}
                or name.startswith((".github/workflows/", ".github/actions/"))
            ):
                pending.append((name + "/", entry["sha"]))
    return names


def _read_slug(slug: str, default: str) -> tuple[dict[str, str], str, str]:
    ref = quote(f"heads/{default}", safe="")
    snapshot = json.loads(_out(
        "gh", "api", "--hostname", "github.com", f"repos/{slug}/commits/{ref}",
    ))  # fmt: skip
    commit, tree = snapshot["sha"], snapshot["commit"]["tree"]["sha"]
    files = {
        n: _out(
            "gh", "api", "--hostname", "github.com",
            "-H", "Accept: application/vnd.github.raw+json",
            f"repos/{slug}/contents/{quote(n, safe='/')}?ref={commit}",
        )
        for n in _tree_paths(slug, tree)
    }  # fmt: skip
    return files, commit, tree


def inventory(repo: str) -> dict[str, object]:
    """Inventory one repository by clone path or slug."""
    if Path(repo).is_dir():
        remote = _remote(repo)
        slug = _slug_from_remote(repo, remote)
        _out("git", "-C", repo, "fetch", remote)
        default = _default_branch(slug)
        files = _read_clone(repo, remote, default)
        where: dict[str, object] = {"path": repo, "remote": remote}
    elif SLUG.fullmatch(repo):
        slug = repo
        default = _default_branch(slug)
        files, commit, tree = _read_slug(slug, default)
        where = {"path": None, "commit": commit, "tree": tree}
    else:
        raise SystemExit(f"not a directory or owner/name slug: {repo}")
    pins, scanned = _scan(files)
    return {"slug": slug, "default": default, **where, "files": scanned, "pins": pins}


def tag_status(action: str, tag: str) -> tuple[str, str]:
    """Return ``exists``, ``missing`` (HTTP 404), or ``unchecked`` plus gh's error."""
    done = _run(
        "gh", "api", "--hostname", "github.com", f"repos/{action_repo(action)}/git/ref/tags/{tag}"
    )
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
        "gh", "api", "--hostname", "github.com", f"repos/{repo}/releases",
        "--paginate", "--jq", ".[].tag_name",
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
