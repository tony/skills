#!/usr/bin/env python3
"""Deterministic gates and derivations for the git-branch skills.

Subcommands (run from inside the repository):

``preflight BRANCH [--mode recommit|redo] [--parent REF]``
    Print one ``refuse <code>: <reason>`` line per refusal and exit 2, or
    exit 0. ``note <code>: <reason>`` lines are reported, not halting. The
    ``redo`` mode refuses only what a redo cannot start from.

``base [--parent REF] [--branch BRANCH]``
    Print the 40-character base SHA: the merge base of the branch (default
    HEAD) and the parent, or trunk when no parent is given.

``backup BRANCH TIP [--soft-reset BASE]``
    Create ``backup/<flat>-<UTC timestamp>`` at TIP, read it back, print its
    name; with ``--soft-reset`` then ``git reset --soft BASE``.

``remote-tip BRANCH``
    Read the remote tip without fetching and print ``key=value`` lines.

``staged [PATH...]``
    Exit 2 unless the staged set is exactly PATH.

``hunks PATCH N[,N...]``
    Print the patch keeping its header and only the listed hunks.

``changed BASE REF`` / ``carry BASE REF PATH...``
    List, or apply to the index, the changes between BASE and REF under the
    pathspecs, deletes included; run ``carry`` in a worktree checked out at
    BASE.

``series BASE TIP [--authors-of REF]``
    Print ``hash author <email> date subject`` for BASE..TIP; with
    ``--authors-of`` also exit 2 when an author or date differs from REF's.
"""

# ruff: noqa: S603, S607, EM101
# pyright: reportAny=false, reportUnusedCallResult=false
import argparse
import os
import re
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import final

REFUSED = 2
FAILED = 1
IN_PROGRESS = (
    "rebase-merge",
    "rebase-apply",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "sequencer",
)
TRUNK_CANDIDATES = ("origin/main", "origin/master", "main", "master")
FIELD = "\x1f"
Row = tuple[str, str, str, str, str]


@final
class Refusal(Exception):  # noqa: N818
    """A gate that stops the run, with a stable code and a reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run git and capture text output."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def out(text: str) -> None:
    """Write one line to stdout."""
    sys.stdout.write(text + "\n")


def flat_name(branch: str) -> str:
    """Replace every ``/`` so the backup is one segment after ``backup/``.

    >>> flat_name("feature/auth/rework")
    'feature-auth-rework'
    """
    return branch.replace("/", "-")


def verify(ref: str) -> str | None:
    """Return the full commit SHA ``ref`` names, or ``None``."""
    done = git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return done.stdout.strip() if done.returncode == 0 else None


def operation_in_progress() -> str | None:
    """Return the first in-progress operation marker, probing the git dir."""
    for name in IN_PROGRESS:
        path = git("rev-parse", "--git-path", name).stdout.strip()
        if path and Path(path).exists():
            return name
    return None


def is_stale_ref(ref: str) -> bool:
    """Tell whether ``ref`` is a remote-tracking ref, last fetched."""
    full = git("rev-parse", "--symbolic-full-name", ref).stdout.strip()
    return full.startswith("refs/remotes/")


def trunk_ref() -> str:
    """Find trunk: the remote's default branch, else a conventional name."""
    head = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if head.returncode == 0 and verify(head.stdout.strip()):
        return head.stdout.strip()
    for candidate in TRUNK_CANDIDATES:
        if verify(candidate):
            return candidate
    raise Refusal("base", "no trunk found; name the parent branch with --parent")


def resolve_base(parent: str | None, branch: str) -> tuple[str, str | None]:
    """Return ``(base_sha, stale_ref)`` for ``branch`` against parent or trunk."""
    ref = parent or trunk_ref()
    if parent and not verify(ref) and verify(f"origin/{ref}"):
        ref = f"origin/{ref}"
    if not verify(ref):
        raise Refusal("base", f"cannot resolve base ref {ref}")
    if not verify(branch):
        raise Refusal("base", f"cannot resolve {branch}")
    bases = git("merge-base", "--all", ref, branch).stdout.split()
    if len(bases) != 1:
        found = "none" if not bases else f"{len(bases)}"
        raise Refusal("base", f"expected one merge base with {ref}, found {found}")
    fork = git("merge-base", "--fork-point", ref, branch)
    base = fork.stdout.strip() if fork.returncode == 0 and fork.stdout.strip() else bases[0]
    return base, (ref if is_stale_ref(ref) else None)


def check_home(top: str) -> str | None:
    """Return a reason when the repository root is, or contains, home."""
    home = os.path.realpath(Path("~").expanduser())
    root = os.path.realpath(top)
    if home == root or home.startswith(root.rstrip(os.sep) + os.sep):
        return "the repository is rooted at the home directory or above it"
    return None


def worktree_holder(branch: str, top: str) -> str | None:
    """Return the path of another worktree that has ``branch`` checked out."""
    listing = git("worktree", "list", "--porcelain").stdout
    path = ""
    for line in listing.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line == f"branch refs/heads/{branch}" and os.path.realpath(path) != os.path.realpath(
            top
        ):
            return path
    return None


def preflight(
    branch: str, mode: str, parent: str | None
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Collect ``(code, reason)`` refusals and notes for ``branch``."""
    refusals: list[tuple[str, str]] = []
    notes: list[tuple[str, str]] = []
    top = git("rev-parse", "--show-toplevel").stdout.strip()
    if not top:
        return [("not-a-repository", "this is not a git repository")], notes
    reason = check_home(top)
    if reason:
        refusals.append(("home", reason))
    if git("rev-parse", "--verify", "--quiet", "HEAD").returncode != 0:
        refusals.append(("unborn", "the repository has no commits"))
        return refusals, notes
    if git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        refusals.append(("shallow", "a shallow clone cannot be reasoned about historically"))
    dirty = bool(git("status", "--porcelain").stdout.strip())
    if mode == "redo":
        if not verify(f"refs/heads/{branch}"):
            refusals.append(
                ("branch-not-local", f"{branch} is not a local branch; fetch or check it out first")
            )
        else:
            try:
                resolve_base(parent, f"refs/heads/{branch}")
            except Refusal as err:
                refusals.append((err.code, err.reason))
        if dirty:
            notes.append(("dirty", "uncommitted edits are outside the ledger"))
        return refusals, notes
    head = git("symbolic-ref", "--short", "HEAD")
    on_branch = head.returncode == 0 and head.stdout.strip() == branch
    if not on_branch:
        refusals.append(("not-checked-out", f"check out {branch} first"))
    if dirty:
        refusals.append(("dirty", "the working tree has uncommitted changes or untracked files"))
    marker = operation_in_progress()
    if marker:
        refusals.append(("in-progress", f"a git operation is in progress ({marker})"))
    if worktree_holder(branch, top):
        refusals.append(("worktree", f"{branch} is checked out in another worktree"))
    if on_branch:
        refusals += merge_refusals(parent, notes)
    if git("config", "--get", "core.sparseCheckout").stdout.strip() == "true":
        notes.append(("sparse", "sparse checkout is active; file listings are incomplete"))
    if any(s.startswith("+") for s in git("submodule", "status").stdout.splitlines()):
        notes.append(("submodule", "a submodule pointer differs from the index"))
    return refusals, notes


def merge_refusals(parent: str | None, notes: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Refuse an unresolvable base, an empty range, or merge commits in it."""
    try:
        base, _ = resolve_base(parent, "HEAD")
    except Refusal as err:
        return [(err.code, err.reason)]
    if base == verify("HEAD"):
        return [("empty-range", "the branch has no commits beyond its base")]
    found: list[tuple[str, str]] = []
    if git("rev-list", "--merges", f"{base}..HEAD").stdout.strip():
        found.append(
            (
                "merge-commit",
                "the range holds a merge commit; collapsing would erase the merged work",
            )
        )
    log = git("log", "--format=%G?", f"{base}..HEAD").stdout.split()
    if any(flag != "N" for flag in log):
        notes.append(("signed", "the range has signed commits; a rebase strips signatures"))
    return found


def cmd_preflight(args: argparse.Namespace) -> int:
    """Print refusals and notes for the target branch."""
    refusals, notes = preflight(args.branch, args.mode, args.parent)
    for code, reason in refusals:
        out(f"refuse {code}: {reason}")
    for code, reason in notes:
        out(f"note {code}: {reason}")
    return REFUSED if refusals else 0


def cmd_base(args: argparse.Namespace) -> int:
    """Print the base SHA."""
    branch = f"refs/heads/{args.branch}" if args.branch else "HEAD"
    base, stale = resolve_base(args.parent, branch)
    out(base)
    if stale:
        sys.stderr.write(f"note: base came from {stale}, last fetched; it may be stale\n")
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    """Create and read back the backup branch, then optionally collapse."""
    tip = verify(args.tip)
    if tip is None or tip != verify(f"refs/heads/{args.branch}"):
        raise Refusal("backup", f"{args.tip} is not the tip of {args.branch}")
    if args.soft_reset:
        head = git("symbolic-ref", "--short", "HEAD")
        if head.returncode != 0 or head.stdout.strip() != args.branch:
            raise Refusal("not-checked-out", f"check out {args.branch} first; nothing was created")
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    stem = f"backup/{flat_name(args.branch)}-{stamp}"
    name = stem
    suffix = 1
    while verify(f"refs/heads/{name}"):
        suffix += 1
        name = f"{stem}-{suffix}"
    made = git("branch", name, tip)
    if made.returncode != 0:
        raise Refusal("backup", f"git could not create {name}: {made.stderr.strip()}")
    if verify(f"refs/heads/{name}") != tip:
        raise Refusal("backup", f"{name} does not read back as {tip}")
    if args.soft_reset:
        if git("merge-base", "--is-ancestor", args.soft_reset, tip).returncode != 0:
            raise Refusal("backup", "the base is not an ancestor of the tip; nothing was reset")
        done = git("reset", "--soft", args.soft_reset)
        if done.returncode != 0:
            sys.stderr.write(done.stderr)
            return FAILED
    out(name)
    return 0


def cmd_remote_tip(args: argparse.Namespace) -> int:
    """Print the remote tip of the branch and the push command, no fetch."""
    branch = args.branch
    remote = git("config", "--get", f"branch.{branch}.remote").stdout.strip()
    merge = git("config", "--get", f"branch.{branch}.merge").stdout.strip()
    if not remote or remote == ".":
        remotes = git("remote").stdout.split()
        remote = remotes[0] if len(remotes) == 1 else ("origin" if "origin" in remotes else "")
        merge = ""
        if not remote and remotes:
            raise Refusal(
                "remote-unknown",
                f"{len(remotes)} remotes and none is origin; name the one that holds {branch}",
            )
    if not remote:
        out("pushed=no")
        return 0
    remote_branch = merge.removeprefix("refs/heads/") if merge else branch
    listed = git("ls-remote", "--heads", remote, f"refs/heads/{remote_branch}")
    if listed.returncode != 0:
        raise Refusal("remote-unreachable", f"cannot read {remote}; the remote tip is unknown")
    tip = next(
        (
            ln.split()[0]
            for ln in listed.stdout.splitlines()
            if ln.endswith(f"\trefs/heads/{remote_branch}")
        ),
        "",
    )
    out(f"remote={remote}")
    out(f"remote-branch={remote_branch}")
    if not tip:
        out("pushed=no")
        return 0
    out(f"tip={tip}")
    out("pushed=yes")
    if git("merge-base", "--is-ancestor", tip, f"refs/heads/{branch}").returncode != 0:
        raise Refusal(
            "remote-ahead", f"{remote}/{remote_branch} is at {tip}, which {branch} does not contain"
        )
    spec = f"--force-with-lease={remote_branch}:{tip}"
    out("push=" + shlex.join(["git", "push", spec, remote, f"{branch}:{remote_branch}"]))
    return 0


def cmd_staged(args: argparse.Namespace) -> int:
    """Exit 2 unless the staged set is exactly the given paths."""
    raw = git("diff", "--cached", "--name-only", "--no-renames", "-z").stdout
    staged = {p for p in raw.split("\0") if p}
    want = set(args.paths)
    for path in sorted(staged - want):
        out(f"unexpected: {path}")
    for path in sorted(want - staged):
        out(f"missing: {path}")
    return 0 if staged == want else REFUSED


def filter_hunks(patch: bytes, keep: set[int]) -> bytes:
    r"""Keep the patch header and only the hunks numbered in ``keep``.

    >>> p = b"--- a\n+++ b\n@@ -1 +1 @@\n-x\n+y\n@@ -9 +9 @@\n-p\n+q\n"
    >>> filter_hunks(p, {2})
    b'--- a\n+++ b\n@@ -9 +9 @@\n-p\n+q\n'
    """
    kept: list[bytes] = []
    count = 0
    active = True
    for line in patch.splitlines(keepends=True):
        if line.startswith(b"@@"):
            count += 1
            active = count in keep
        if active:
            kept.append(line)
    return b"".join(kept)


def count_hunks(patch: bytes) -> int:
    r"""Count hunks in a patch.

    >>> count_hunks(b"@@ -1 +1 @@\n-a\n+b\n")
    1
    """
    return sum(1 for line in patch.splitlines() if line.startswith(b"@@"))


def cmd_hunks(args: argparse.Namespace) -> int:
    """Print the patch filtered to the listed hunks."""
    patch = Path(args.patch).read_bytes()
    keep = {int(n) for n in re.split(r"[,\s]+", args.numbers.strip()) if n}
    total = count_hunks(patch)
    if not keep or max(keep) > total or min(keep) < 1:
        sys.stderr.write(f"the patch has {total} hunks; asked for {args.numbers}\n")
        return REFUSED
    sys.stdout.flush()
    sys.stdout.buffer.write(filter_hunks(patch, keep))
    return 0


def name_status(base: str, ref: str, paths: list[str]) -> list[tuple[str, str]]:
    """Return ``(status, path)`` for BASE..REF, a rename as delete plus add."""
    done = git("diff", "--name-status", "--no-renames", "-z", base, ref, "--", *paths)
    fields = [f for f in done.stdout.split("\0") if f]
    return [(fields[i], fields[i + 1]) for i in range(0, len(fields) - 1, 2)]


def cmd_changed(args: argparse.Namespace) -> int:
    """List the changes between BASE and REF."""
    for status, path in name_status(args.base, args.ref, []):
        out(f"{status}\t{path}")
    return 0


def cmd_carry(args: argparse.Namespace) -> int:
    """Apply the REF changes under the pathspecs to the index, deletes too."""
    base = verify(args.base)
    if base is None or base != verify("HEAD"):
        raise Refusal("carry", "HEAD is not the base; run this in the redo worktree")
    changes = name_status(base, args.ref, args.paths)
    if not changes:
        raise Refusal("carry", "no change under those pathspecs")
    for status, path in changes:
        if status.startswith("D"):
            done = git("rm", "-q", "--ignore-unmatch", "--", path)
        else:
            done = git("checkout", args.ref, "--", path)
        if done.returncode != 0:
            sys.stderr.write(done.stderr)
            return FAILED
        out(f"{status}\t{path}")
    return 0


def author_lines(base: str, tip: str) -> list[Row]:
    """Return ``(hash, name, email, date, body)`` per non-merge commit."""
    fmt = FIELD.join(["%h", "%an", "%ae", "%aI", "%B"]) + "\x1e"
    log = git("log", "--reverse", "--no-merges", f"--format={fmt}", f"{base}..{tip}").stdout
    rows: list[Row] = []
    for record in log.split("\x1e"):
        parts = record.strip("\n").split(FIELD, 4)
        if len(parts) == 5:  # noqa: PLR2004
            rows.append((parts[0], parts[1], parts[2], parts[3], parts[4]))
    return rows


def compare_authors(
    old: list[Row],
    new: list[Row],
) -> list[str]:
    """Return problems: a new identity or date, or an original author lost.

    A lost author is excused when the new messages carry their email.

    >>> a = [("1", "Ada", "a@x", "2026-01-01T00:00:00+00:00", "m")]
    >>> compare_authors(a, [("2", "Ada", "a@x", "2026-01-01T00:00:00+00:00", "m")])
    []
    >>> compare_authors(a, [("2", "Bob", "b@x", "2026-01-01T00:00:00+00:00", "m")])[0]
    'not in the original: Bob <b@x> 2026-01-01T00:00:00+00:00'
    """
    known = {(r[1], r[2], r[3]) for r in old}
    problems = [
        f"not in the original: {n} <{e}> {d}" for _, n, e, d, _ in new if (n, e, d) not in known
    ]
    present = {(r[1], r[2]) for r in new}
    bodies = "\n".join(r[4] for r in new).lower()
    for _, name, email, _, _ in old:
        if (name, email) not in present and email.lower() not in bodies:
            problems.append(f"original author lost: {name} <{email}>")
    return sorted(set(problems))


def cmd_series(args: argparse.Namespace) -> int:
    """Print the series and compare authors when asked."""
    new = author_lines(args.base, args.tip)
    for short, name, email, date, body in new:
        out(f"{short} {name} <{email}> {date} {body.splitlines()[0] if body else ''}")
    if not args.authors_of:
        return 0
    problems = compare_authors(author_lines(args.base, args.authors_of), new)
    for problem in problems:
        out(f"refuse authors: {problem}")
    return REFUSED if problems else 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(description="Gates and derivations for the git-branch skills.")
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("branch")
    pre.add_argument("--mode", choices=("recommit", "redo"), default="recommit")
    pre.add_argument("--parent")
    pre.set_defaults(func=cmd_preflight)
    base = sub.add_parser("base")
    base.add_argument("--parent")
    base.add_argument("--branch")
    base.set_defaults(func=cmd_base)
    bak = sub.add_parser("backup")
    bak.add_argument("branch")
    bak.add_argument("tip")
    bak.add_argument("--soft-reset", metavar="BASE")
    bak.set_defaults(func=cmd_backup)
    rem = sub.add_parser("remote-tip")
    rem.add_argument("branch")
    rem.set_defaults(func=cmd_remote_tip)
    stg = sub.add_parser("staged")
    stg.add_argument("paths", nargs="*")
    stg.set_defaults(func=cmd_staged)
    hnk = sub.add_parser("hunks")
    hnk.add_argument("patch")
    hnk.add_argument("numbers")
    hnk.set_defaults(func=cmd_hunks)
    chg = sub.add_parser("changed")
    chg.add_argument("base")
    chg.add_argument("ref")
    chg.set_defaults(func=cmd_changed)
    car = sub.add_parser("carry")
    car.add_argument("base")
    car.add_argument("ref")
    car.add_argument("paths", nargs="+")
    car.set_defaults(func=cmd_carry)
    ser = sub.add_parser("series")
    ser.add_argument("base")
    ser.add_argument("tip")
    ser.add_argument("--authors-of", metavar="REF")
    ser.set_defaults(func=cmd_series)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand; a refusal prints its line and exits 2."""
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except Refusal as err:
        out(f"refuse {err.code}: {err.reason}")
        return REFUSED


if __name__ == "__main__":
    sys.exit(main())
