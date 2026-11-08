#!/usr/bin/env python3
r"""Pin and fetch corpora for scholar, and vet identifiers before they reach a tool.

Standard library only. Every refusal prints one line to stderr and exits
non-zero; a success prints its result to stdout.

Examples
--------
Identifiers from a study are untrusted until they pass:

>>> import contextlib, sys
>>> with contextlib.redirect_stderr(sys.stdout):
...     main(["ident", "--owner", "..", "--repo", "r"])
owner '..' is not a GitHub owner name
2
>>> main(["ident", "--owner", "o", "--repo", "r", "--ref", "v1.0", "--path", "src/a.py"])
0
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_REFPATH = re.compile(r"^[A-Za-z0-9._/-]+$")
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_FULL = re.compile(r"^[0-9a-f]{40}$")
_HTTPS = re.compile(r"^https://[A-Za-z0-9.-]+(?::\d+)?(?:/[A-Za-z0-9._-]+)+$")
_GITHUB_URL = re.compile(
    r"^https://github\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._~%/#?=&+@:-]*)?$"
)
_PREFIX = "scholar-corpus."


class FetchError(RuntimeError):
    """A throwaway checkout could not be made."""


def _refuse(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _name_problem(label: str, value: str) -> str | None:
    if not _NAME.match(value) or value in {".", ".."}:
        return f"{label} {value!r} is not a GitHub {label} name"
    return None


def _path_problem(label: str, value: str) -> str | None:
    parts = value.split("/")
    if not _REFPATH.match(value) or value.startswith(("/", "-")) or {"", ".", ".."} & set(parts):
        return f"{label} {value!r} is not a plain relative {label}"
    return None


class _Args(argparse.Namespace):
    command: str = ""
    corpus: str = ""
    study: str | None = None
    expect: str | None = None
    url: str | None = None
    commit: str | None = None
    dir: str = ""
    owner: str | None = None
    repo: str | None = None
    ref: str | None = None
    path: str | None = None
    file: str = ""


def ident_problem(args: _Args) -> str | None:
    """Return the first reason a supplied identifier is unsafe, else ``None``."""
    owner, repo, ref, commit, path, url = (
        args.owner,
        args.repo,
        args.ref,
        args.commit,
        args.path,
        args.url,
    )
    checks = [
        _name_problem("owner", owner) if owner is not None else None,
        _name_problem("repo", repo) if repo is not None else None,
        _path_problem("ref", ref) if ref is not None else None,
        _path_problem("path", path) if path is not None else None,
        f"commit {commit!r} is not 7 to 40 hex digits"
        if commit is not None and not _COMMIT.match(commit)
        else None,
        f"url {url!r} is not a plain https://github.com/ URL"
        if url is not None and not _GITHUB_URL.match(url)
        else None,
    ]
    return next((check for check in checks if check), None)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def _study_exclude(corpus: str, study: str | None) -> list[str]:
    """Pathspec arguments leaving the study directory out of the dirty check."""
    if not study:
        return []
    root = Path(corpus).resolve()
    inside = Path(study).resolve()
    if inside != root and root not in inside.parents:
        return []
    return ["--", ".", f":(exclude){inside.relative_to(root).as_posix()}"]


def local(args: _Args) -> int:
    """Resolve a local checkout to the pin ``gather`` records, or refuse when it is dirty."""
    corpus = str(args.corpus)
    head = _git("-C", corpus, "rev-parse", "HEAD")
    if head.returncode != 0 or not _FULL.match(head.stdout.strip()):
        return _refuse(f"{corpus} is not a git checkout with a commit")
    commit = head.stdout.strip()
    status = _git("-C", corpus, "status", "--porcelain", *_study_exclude(corpus, args.study))
    if status.returncode != 0 or status.stdout.strip():
        return _refuse("the corpus has uncommitted edits")
    if args.expect and not commit.startswith(args.expect):
        return _refuse(f"the corpus is at {commit[:7]}, not {args.expect[:7]}")
    short = _git("-C", corpus, "rev-parse", "--short=7", "HEAD").stdout.strip()
    tag = _git("-C", corpus, "describe", "--tags", "--exact-match", "HEAD").stdout.strip()
    remotes = _git("-C", corpus, "branch", "--remotes", "--contains", "HEAD").stdout.strip()
    print(
        json.dumps(
            {"commit": commit, "ref": tag or short, "tag": tag, "pushed": bool(remotes)},
        )
    )
    return 0


def fetch(url: str, commit: str, parent: str | None = None) -> str:
    """Fetch *commit* of *url* into a new throwaway directory and return its path."""
    path = tempfile.mkdtemp(prefix=_PREFIX, dir=parent)
    steps = [
        ["-C", path, "init", "--quiet"],
        ["-C", path, "fetch", "--quiet", "--depth", "1", url, commit],
        ["-C", path, "checkout", "--quiet", "FETCH_HEAD"],
    ]
    for step in steps:
        if _git(*step).returncode != 0:
            shutil.rmtree(path, ignore_errors=True)
            message = f"could not fetch {commit[:7]} from {url}"
            raise FetchError(message)
    return path


def remote(args: _Args) -> int:
    """Check out a remote source at its commit in a throwaway directory."""
    url, commit = args.url or "", args.commit or ""
    if not _HTTPS.match(url) or not _FULL.match(commit):
        return _refuse("the source must be a plain https:// URL and a 40-digit commit")
    try:
        print(fetch(url, commit))
    except FetchError as exc:
        return _refuse(str(exc))
    return 0


def release(args: _Args) -> int:
    """Delete a directory ``remote`` created, and only such a directory."""
    path = Path(args.dir)
    temp = Path(tempfile.gettempdir()).resolve()
    if not path.name.startswith(_PREFIX) or path.resolve().parent != temp:
        return _refuse(f"{path.name} is not a scholar checkout")
    if not path.is_dir():
        return _refuse(f"no checkout {path.name}")
    shutil.rmtree(path)
    return 0


def resolve_remote(url: str, ref: str) -> tuple[str, bool]:
    """Return the commit *ref* names at *url*, and whether an annotated tag was peeled.

    A tag wins over a branch of the same name; the peeled line (``REF^{}``) is
    the commit an annotated tag points at.
    """
    done = _git("ls-remote", url, ref, f"{ref}^{{}}")
    if done.returncode != 0:
        message = f"could not list {url}"
        raise FetchError(message)
    found: dict[str, str] = {}
    for line in done.stdout.splitlines():
        sha, _, name = line.partition("\t")
        found[name] = sha
    for name, peeled in (
        (f"refs/tags/{ref}^{{}}", True),
        (f"refs/tags/{ref}", False),
        (f"refs/heads/{ref}", False),
        (ref, False),
    ):
        if name in found and _FULL.match(found[name]):
            return found[name], peeled
    message = f"{ref} not found at {url}"
    raise FetchError(message)


def ls_remote(args: _Args) -> int:
    """Print the commit a ref names at a remote, after vetting both."""
    url, ref = args.url or "", args.ref or ""
    if not _HTTPS.match(url) or _path_problem("ref", ref):
        return _refuse("the source must be a plain https:// URL and a plain ref")
    try:
        commit, peeled = resolve_remote(url, ref)
    except FetchError as exc:
        return _refuse(str(exc))
    print(json.dumps({"commit": commit, "peeled": peeled}))
    return 0


def ident(args: _Args) -> int:
    """Exit 0 when every supplied identifier is safe to hand to gh, curl or git."""
    problem = ident_problem(args)
    return _refuse(problem) if problem else 0


def sha256(args: _Args) -> int:
    """Print the SHA-256 of a file; the same spelling on GNU and BSD systems."""
    path = Path(args.file)
    if not path.is_file():
        return _refuse(f"no file {path.name}")
    print(hashlib.sha256(path.read_bytes()).hexdigest())
    return 0


_COMMANDS = {
    "local": local,
    "remote": remote,
    "release": release,
    "ident": ident,
    "ls-remote": ls_remote,
    "sha256": sha256,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scholar_pins.py", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("local", help="pin a local checkout; refuse when dirty")
    _ = one.add_argument("corpus")
    _ = one.add_argument("--study", help="study directory to leave out of the dirty check")
    _ = one.add_argument("--expect", help="refuse unless HEAD starts with this commit")

    two = sub.add_parser("remote", help="check out URL at COMMIT in a throwaway directory")
    _ = two.add_argument("url")
    _ = two.add_argument("commit")

    three = sub.add_parser("release", help="delete a directory made by remote")
    _ = three.add_argument("dir")

    four = sub.add_parser("ident", help="vet identifiers taken from a study")
    for flag in ("owner", "repo", "ref", "commit", "path", "url"):
        _ = four.add_argument(f"--{flag}")

    six = sub.add_parser("ls-remote", help="print the commit REF names at URL")
    _ = six.add_argument("url")
    _ = six.add_argument("ref")

    five = sub.add_parser("sha256", help="print a file's SHA-256")
    _ = five.add_argument("file")
    return parser


def main(argv: list[str]) -> int:
    """Run one subcommand; return its exit status."""
    try:
        args = _parser().parse_args(argv, namespace=_Args())
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
