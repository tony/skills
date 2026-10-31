#!/usr/bin/env python3
"""Git plumbing for the respond skills.

``guard`` exits 3 when the repository is rooted at the home directory or above
it. ``base`` resolves the provenance base. ``changes`` lists every path the
working tree differs from ``HEAD`` on, one JSON array. ``revert`` restores every
such path to ``HEAD``. ``mark`` records the changed paths' contents and
``since-mark`` lists the paths that differ from that record, which is how a
gate's own edits are told apart from the tree it started with.
``fixup-check`` decides whether a ``fixup!`` plus autosquash may rewrite history.
``push-target`` and ``push`` resolve the pull request's head remote and branch
and push to it, never forcing; ``push`` then reads the pull request head back.

``gh`` calls go through ghcli.py.

Exit codes: 0 done, 1 refused or unresolved (stderr says why), 2 usage, 3 the
repository is rooted at the home directory, 4 ``gh`` failed.
"""

# ruff: noqa: S603, S607
# pyright: reportAny=false, reportUnusedCallResult=false
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from ghcli import GhError, gh  # pyright: ignore[reportImplicitRelativeImport]

_PREFERRED_REMOTES = ("upstream", "origin")
_COPY_OR_RENAME = {"R", "C"}


def git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git`` in the current directory without raising."""
    return subprocess.run(["git", *args], check=False, capture_output=True, text=True)


class RefusalError(Exception):
    """A check failed; the message is the reason."""


def status_entries() -> list[tuple[str, str, str]]:
    """Return ``(XY, path, original-path-or-empty)`` for every changed path.

    Reads ``git status -z --untracked-files=all``, so paths are never quoted
    and a new directory lists its files.
    """
    out = git("status", "-z", "--untracked-files=all").stdout
    parts = out.split("\0")
    entries: list[tuple[str, str, str]] = []
    i = 0
    while i < len(parts) and parts[i]:
        xy, path = parts[i][:2], parts[i][3:]
        orig = ""
        if xy[0] in _COPY_OR_RENAME or xy[1] in _COPY_OR_RENAME:
            i += 1
            orig = parts[i] if i < len(parts) else ""
        entries.append((xy, path, orig))
        i += 1
    return entries


def changed_paths() -> list[str]:
    """Return the sorted paths the working tree or index changes against ``HEAD``."""
    paths: set[str] = set()
    for _xy, path, orig in status_entries():
        paths.add(path)
        if orig:
            paths.add(orig)
    return sorted(paths)


def home_rooted() -> bool:
    """Return whether the repository's top level is the home directory or above it."""
    top = git("rev-parse", "--show-toplevel").stdout.strip()
    if not top:
        return False
    home = Path.home().resolve()
    root = Path(top).resolve()
    return root == home or root in home.parents


def _ref_exists(ref: str) -> bool:
    return git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0


def _remotes() -> list[str]:
    names = git("remote").stdout.split()
    first = [n for n in _PREFERRED_REMOTES if n in names]
    return first + sorted(n for n in names if n not in first)


def _pr_base_name(pr: str) -> str:
    """Return the pull request's base branch; empty when no ``--pr`` was given and none is found.

    A lookup that fails for a named pull request raises ``GhError``, so a
    stacked pull request never falls back to the trunk unnoticed.
    """
    args = ["pr", "view", *([pr] if pr else []), "--json", "baseRefName", "--jq", ".baseRefName"]
    try:
        return gh(*args).strip()
    except GhError:
        if pr:
            raise
        return ""


def _base_candidates(pr_name: str, remotes: list[str]) -> list[tuple[str, str]]:
    """Return ``(source, ref)`` candidates in resolution order."""
    out: list[tuple[str, str]] = []
    if pr_name:
        out += [("pr", f"{r}/{pr_name}") for r in remotes]
        out.append(("pr", pr_name))
    for remote in remotes:
        head = git("symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD")
        if head.returncode == 0:
            out.append(("origin-head", head.stdout.strip()))
    for trunk in ("main", "master"):
        out += [("fallback", f"{r}/{trunk}") for r in remotes]
        out.append(("fallback", trunk))
    return out


def resolve_base(pr: str, flag: str, *, fetch: bool) -> dict[str, object]:
    """Resolve the provenance base: flag, else the PR's base branch, else the trunk.

    Candidates are tried in order and the first that exists wins: ``--base``;
    ``baseRefName`` from ``gh pr view`` on ``upstream``, ``origin``, other
    remotes, then locally; the remote's ``HEAD``; ``main`` and ``master``.
    ``fetch`` refreshes every remote first, since each is a candidate.
    ``source`` tells how the base was found; anything but ``pr`` or ``flag``
    is a guess the report must name.

    Raises ``RefusalError`` when nothing resolves and ``GhError`` when a named
    pull request cannot be read.
    """
    remotes = _remotes()
    fetched = False
    if fetch and remotes:
        fetched = all(git("fetch", "--quiet", r).returncode == 0 for r in list(remotes))
    if flag:
        candidates = [("flag", flag)]
    else:
        candidates = _base_candidates(_pr_base_name(pr), remotes)
    for source, ref in candidates:
        if not _ref_exists(ref):
            continue
        merged = git("merge-base", ref, "HEAD")
        if merged.returncode == 0:
            return {
                "ref": ref,
                "sha": merged.stdout.strip(),
                "source": source,
                "fetched": fetched,
            }
    msg = "no base resolved: pass --base=<ref>"
    raise RefusalError(msg)


def fixup_check(sha: str, base: str) -> dict[str, str]:
    """Allow a ``fixup!`` rewrite only for an unpushed, non-merge commit on a linear range.

    Unpushed means no remote-tracking ref (as last fetched) contains the
    commit. Raises ``RefusalError`` with the reason otherwise.
    """
    full = git("rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}").stdout.strip()
    if not full:
        msg = f"{sha} is not a commit"
        raise RefusalError(msg)
    if git("rev-list", "--merges", f"{base}..HEAD").stdout.split():
        msg = f"{base}..HEAD contains a merge commit; autosquash would flatten it"
        raise RefusalError(msg)
    if full not in git("rev-list", f"{base}..HEAD").stdout.split():
        msg = f"{sha} is not in {base}..HEAD"
        raise RefusalError(msg)
    pushed = git("for-each-ref", "--contains", full, "--format=%(refname:short)", "refs/remotes")
    if pushed.stdout.split():
        msg = f"{sha} is pushed: reachable from {pushed.stdout.split()[0]}"
        raise RefusalError(msg)
    return {"commit": full, "base": base}


def revert_changes() -> list[str]:
    """Restore every changed path to ``HEAD`` and delete untracked files.

    Precondition owned by the caller: the tree was clean before the change
    being undone, so every changed path belongs to it.
    """
    reverted: list[str] = []
    for xy, path, orig in status_entries():
        if xy == "??":
            Path(path).unlink(missing_ok=True)
            reverted.append(path)
            continue
        for item in (path, orig):
            if not item:
                continue
            if git("cat-file", "-e", f"HEAD:{item}").returncode == 0:
                git("restore", "--staged", "--worktree", "--source=HEAD", "--", item)
            else:
                git("rm", "-q", "-f", "--", item)
            reverted.append(item)
    return sorted(set(reverted))


_MISSING = "deleted"
_CLEAN = "clean"


def _fingerprint(path: str) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return _MISSING


def _mark_file() -> Path:
    return Path(git("rev-parse", "--git-path", "respond-mark.json").stdout.strip())


def mark() -> list[str]:
    """Record a content hash for every changed path; return those paths."""
    paths = changed_paths()
    _mark_file().write_text(json.dumps({p: _fingerprint(p) for p in paths}), encoding="utf-8")
    return paths


def since_mark() -> list[str]:
    """Return the paths whose state differs from the last ``mark``.

    A path counts when it is newly changed, changed again, or back to clean.
    """
    record = _mark_file()
    if not record.is_file():
        msg = "no mark recorded; run mark before the gate"
        raise RefusalError(msg)
    before: dict[str, str] = json.loads(record.read_text(encoding="utf-8"))
    now = {p: _fingerprint(p) for p in changed_paths()}
    return sorted(
        p for p in before.keys() | now.keys() if before.get(p, _CLEAN) != now.get(p, _CLEAN)
    )


def _url_matches(url: str, owner: str, name: str) -> bool:
    """Return whether a remote URL names ``owner/name``.

    >>> _url_matches("git@github.com:Acme/widgets.git", "acme", "widgets")
    True
    >>> _url_matches("https://github.com/acme/widgets-extra", "acme", "widgets")
    False
    """
    tail = re.sub(r"\.git/?$", "", url.strip()).rstrip("/").lower()
    want = f"{owner}/{name}".lower()
    return tail.endswith(("/" + want, ":" + want))


def _pick_remote(owner: str, name: str, *, cross_repo: bool) -> str:
    for remote in _remotes():
        if _url_matches(git("remote", "get-url", remote).stdout, owner, name):
            return remote
    if cross_repo:
        msg = f"no remote points at {owner}/{name}; add one, then run again"
        raise RefusalError(msg)
    branch = git("branch", "--show-current").stdout.strip()
    tracked = git("config", f"branch.{branch}.remote").stdout.strip()
    if tracked and tracked != ".":
        return tracked
    if "origin" in _remotes():
        return "origin"
    msg = "no remote to push to"
    raise RefusalError(msg)


def push_target(pr: str) -> dict[str, object]:
    """Resolve where a push for ``pr`` goes and how the local head relates to it.

    ``state`` is ``up-to-date``, ``ahead``, ``behind``, or ``diverged``, judged
    against the pull request's own ``headRefOid``.
    """
    fields = "headRefName,headRefOid,headRepository,headRepositoryOwner,isCrossRepository"
    data = json.loads(gh("pr", "view", pr, "--json", fields))
    repo, owner = data.get("headRepository"), data.get("headRepositoryOwner")
    if not repo or not owner:
        msg = "the pull request's head repository is gone"
        raise RefusalError(msg)
    remote = _pick_remote(
        owner["login"], repo["name"], cross_repo=bool(data.get("isCrossRepository"))
    )
    branch, remote_head = data["headRefName"], data["headRefOid"]
    local = git("rev-parse", "HEAD").stdout.strip()
    if local == remote_head:
        state = "up-to-date"
    else:
        if git("cat-file", "-e", f"{remote_head}^{{commit}}").returncode != 0:
            git("fetch", "--quiet", remote, branch)
        if git("merge-base", "--is-ancestor", remote_head, local).returncode == 0:
            state = "ahead"
        elif git("merge-base", "--is-ancestor", local, remote_head).returncode == 0:
            state = "behind"
        else:
            state = "diverged"
    return {
        "remote": remote,
        "branch": branch,
        "state": state,
        "command": ["git", "push", remote, f"HEAD:refs/heads/{branch}"],
    }


def push(pr: str) -> dict[str, object]:
    """Push when ahead; refuse when behind or diverged. Never forces."""
    target = push_target(pr)
    state = target["state"]
    if state in {"behind", "diverged"}:
        msg = f"local head is {state} of the pull request head; a rebase or force-push is needed"
        raise RefusalError(msg)
    if state == "ahead":
        cmd = ["git", "push", str(target["remote"]), f"HEAD:refs/heads/{target['branch']}"]
        done = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if done.returncode != 0:
            raise RefusalError(done.stderr.strip() or "push failed")
        target["pushed"] = True
        head = gh("pr", "view", pr, "--json", "headRefOid", "--jq", ".headRefOid").strip()
        target["head"] = head
        if head != git("rev-parse", "HEAD").stdout.strip():
            msg = f"the pull request head is {head} after the push, not the local head"
            raise RefusalError(msg)
    return target


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("guard")
    sub.add_parser("changes")
    sub.add_parser("revert")
    sub.add_parser("mark")
    sub.add_parser("since-mark")
    base = sub.add_parser("base")
    base.add_argument("--pr", default="")
    base.add_argument("--base", default="")
    base.add_argument("--fetch", action="store_true")
    fix = sub.add_parser("fixup-check")
    fix.add_argument("sha")
    fix.add_argument("--base", required=True)
    for name in ("push-target", "push"):
        sub.add_parser(name).add_argument("pr")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "guard":
            if home_rooted():
                sys.stderr.write("repository is rooted at the home directory\n")
                return 3
            return 0
        if args.cmd == "changes":
            _emit(changed_paths())
        elif args.cmd == "revert":
            _emit(revert_changes())
        elif args.cmd == "mark":
            _emit(mark())
        elif args.cmd == "since-mark":
            _emit(since_mark())
        elif args.cmd == "base":
            _emit(resolve_base(args.pr, args.base, fetch=args.fetch))
        elif args.cmd == "fixup-check":
            _emit(fixup_check(args.sha, args.base))
        elif args.cmd == "push-target":
            _emit(push_target(args.pr))
        else:
            _emit(push(args.pr))
    except RefusalError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    except GhError as exc:
        sys.stderr.write(f"{exc}\n")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
