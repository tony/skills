#!/usr/bin/env python3
"""Print per-repository scope facts as JSON: remotes, fork signal, default branch, pins.

``repo_facts.py [--fetch] REPO...`` prints one JSON object per repository.
Pins are read from the default branch ref, not the working tree. With
``--fetch`` the remote is fetched first and ``fetch_ok`` reports the result.

``repo_facts.py --lock-diff REPO [LOCKFILE...]`` compares each lockfile
(default: every tracked ``uv.lock``, ``poetry.lock`` and ``Cargo.lock`` in REPO,
at any depth) at ``HEAD`` with the working tree and splits the changed packages
into ``majors`` (a new major, or for 0.x a new minor) and ``in_range``.

``repo_facts.py --manifest-diff REPO [MANIFEST...]`` does the same for the
dependency ranges of each ``package.json`` (default: every tracked one).

``repo_facts.py --scope [--root DIR...] [--repo PATH|SLUG...] [--owner NAME...]`` prints one
row per repository found: remote, owner match, worktree, submodule, duplicate-clone and
fork signals, whether the configured author email appears among the last ten commits, and
``excluded`` (the rule that drops it, or null). With no flag it covers the current repository.

``repo_facts.py --pin-sites REPO NAME`` lists every tracked line naming NAME as
a whole word. ``--free-branch REPO NAME`` prints the first of NAME, NAME-2, ...
that no local or remote branch uses. ``--issue-branch NUMBER TITLE`` prints
``NUMBER-slug``.

Exit status: 0, 1 when a printed result carries an ``error``, 2 on bad usage.

A file that cannot be read is reported as an ``error`` or in ``failed``, never
as absent or unchanged. A file missing from ``HEAD`` is ``{"new": true}``.
"""

# ruff: noqa: S603, S607, PLR2004
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

LOCKFILES = ("uv.lock", "poetry.lock", "Cargo.lock")


def _git(repo: str, *args: str, strip_newline: bool = True) -> tuple[int, str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    done = subprocess.run(
        ["git", "--no-optional-locks", "-C", repo, *args],
        capture_output=True,
        check=False,
        env=env,
    )
    output = os.fsdecode(done.stdout)
    return done.returncode, output.removesuffix("\n") if strip_newline else output


def _remotes(repo: str) -> dict[str, str]:
    _, out = _git(repo, "remote", "-v")
    found: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            found.setdefault(parts[0], parts[1])
    return found


def _default_branch(repo: str, remote: str) -> str | None:
    prefix = f"refs/remotes/{remote}/"
    code, out = _git(repo, "symbolic-ref", f"{prefix}HEAD")
    if code == 0 and out.startswith(prefix):
        return out.removeprefix(prefix)
    code, out = _git(repo, "ls-remote", "--symref", remote, "HEAD")
    match = re.search(r"^ref: refs/heads/(\S+)\s+HEAD", out, re.MULTILINE)
    return str(match.group(1)) if code == 0 and match else None


PRESENT, ABSENT, FAILED = "present", "absent", "failed"
DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)
MANIFEST = "package.json"


def _read(repo: str, ref: str, path: str) -> tuple[str, str]:
    """Read ``path`` at ``ref``: ``(PRESENT, text)``, ``(ABSENT, "")`` or ``(FAILED, "")``."""
    code, listed = _git(repo, "ls-tree", "--name-only", ref, "--", f"./{path}")
    if code:
        return FAILED, ""
    if not listed:
        return ABSENT, ""
    code, out = _git(repo, "show", f"{ref}:./{path}", strip_newline=False)
    return (PRESENT, out) if code == 0 else (FAILED, "")


def _scan_toml(line: str) -> tuple[str, int]:
    """Return ``line`` without its comment and its bracket depth outside strings."""
    quote, depth = "", 0
    kept: list[str] = []
    for char in line:
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "#":
            break
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        kept.append(char)
    return "".join(kept), depth


def _versions(values: list[str]) -> str | list[str]:
    return values[0] if len(values) == 1 else values


def _mise_tools(text: str) -> tuple[dict[str, object], bool]:
    """Read the ``[tools]`` table of a mise file; the flag is False when a line is not understood.

    Understood values: ``"v"``, ``["v", ...]`` (also across lines) and
    ``{ version = "v" | [...], ... }``.
    """
    tools: dict[str, object] = {}
    ok, in_tools, pending, depth = True, False, "", 0
    for raw in text.splitlines():
        line, delta = _scan_toml(raw)
        line = line.strip()
        if pending:
            pending, depth = f"{pending} {line}", depth + delta
            if depth > 0:
                continue
            line, pending, depth = pending, "", 0
        elif line.startswith("["):
            in_tools = line == "[tools]"
            ok = ok and not line.startswith("[tools.")
            continue
        elif delta > 0:
            pending, depth = line, delta
            continue
        if not line or not in_tools:
            continue
        match = re.match(r"""(["']?)([^"'=\s]+)\1\s*=\s*(.+)$""", line)
        if not match:
            ok = False
            continue
        value = match.group(3).strip()
        if value.startswith("{"):
            inner = re.search(r"""\bversion\s*=\s*(\[[^\]]*\]|["'][^"']*["'])""", value)
            value = inner.group(1) if inner else ""
        found = [m.group(2) for m in re.finditer(r"""(["'])((?:(?!\1).)*)\1""", value)]
        if found:
            tools[match.group(2)] = _versions(found)
        else:
            ok = False
    return tools, ok


def _first_line(text: str) -> str | None:
    return text.splitlines()[0].strip() if text.strip() else None


def _version_lines(text: str) -> str | list[str] | None:
    """Every version line of a one-version-per-line file (``.python-version`` may list several)."""
    lines = [ln for raw in text.splitlines() if (ln := raw.split("#")[0].strip())]
    return _versions(lines) if lines else None


def _tool_versions(text: str) -> dict[str, object] | None:
    tools: dict[str, object] = {}
    for line in text.splitlines():
        parts = line.split("#")[0].split()
        if len(parts) == 1:
            return None
        if parts:
            tools[parts[0]] = _versions(parts[1:])
    return tools


def _mise(text: str) -> dict[str, object] | None:
    tools, understood = _mise_tools(text)
    return tools if understood else None


def _rust_channel(text: str) -> str | None:
    if text.lstrip().startswith("["):
        match = re.search(r"""^\s*channel\s*=\s*(["'])([^"'\r\n]+)\1""", text, re.MULTILINE)
        return str(match.group(2)) if match else None
    return _first_line(text)


def _go_pins(text: str) -> dict[str, object]:
    pins: dict[str, object] = {}
    for key in ("go", "toolchain"):
        match = re.search(rf"^{key}\s+(\S+)", text, re.MULTILINE)
        if match:
            pins[key] = match.group(1)
    return pins


def _package_pins(text: str) -> dict[str, object] | None:
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return {k: data[k] for k in ("packageManager", "engines") if k in data}


PIN_PARSERS: dict[str, Callable[[str], object | None]] = {
    ".tool-versions": _tool_versions,
    ".nvmrc": _version_lines,
    ".node-version": _version_lines,
    ".python-version": _version_lines,
    ".ruby-version": _version_lines,
    ".java-version": _version_lines,
    ".terraform-version": _version_lines,
    "mise.toml": _mise,
    ".mise.toml": _mise,
    "rust-toolchain.toml": _rust_channel,
    "rust-toolchain": _rust_channel,
    "go.mod": _go_pins,
    MANIFEST: _package_pins,
}


MISE_CONFIG_SUFFIXES = (".config/mise/config.toml", ".config/mise.toml")


def _parser(path: str) -> Callable[[str], object | None] | None:
    if path.endswith(MISE_CONFIG_SUFFIXES):
        return _mise
    return PIN_PARSERS.get(path.rsplit("/", maxsplit=1)[-1])


def _pins(repo: str, ref: str) -> tuple[dict[str, object], list[str]]:
    """Read every tracked toolchain pin file at ``ref``, at any depth.

    Keys are paths from the repository root; an unreadable or unparsed file is in ``failed``.
    """
    pins: dict[str, object] = {}
    code, listed = _git(repo, "ls-tree", "-r", "-z", "--name-only", ref)
    if code:
        return pins, list(PIN_PARSERS)
    failed: list[str] = []
    for path in listed.split("\0"):
        parse = _parser(path) if path else None
        if parse is None:
            continue
        state, text = _read(repo, ref, path)
        value = parse(text) if state == PRESENT else None
        if value is None:
            failed.append(path)
        elif value or not path.endswith(MANIFEST):
            pins[path] = value
    return pins, failed


def facts(repo: str, *, fetch: bool = False) -> dict[str, object]:
    """Collect scope facts for one repository."""
    code, top = _git(repo, "rev-parse", "--show-toplevel")
    if code:
        return {"path": repo, "error": "not a git repository"}
    _, git_dir = _git(repo, "rev-parse", "--path-format=absolute", "--git-dir")
    _, common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    _, super_wt = _git(repo, "rev-parse", "--show-superproject-working-tree")
    remotes = _remotes(repo)
    remote = (
        "origin" if "origin" in remotes else (next(iter(remotes)) if len(remotes) == 1 else None)
    )
    status, changes = _git(repo, "status", "--porcelain", "--untracked-files=no")
    failed = ["worktree status"] if status else []
    out: dict[str, object] = {
        "path": top,
        "linked_worktree": git_dir != common,
        "submodule": bool(super_wt),
        "remotes": remotes,
        "remote": remote,
        "fork_signal": "upstream" in remotes,
        "default_branch": None,
        "branch": _git(repo, "branch", "--show-current")[1],
        "dirty": bool(changes) if status == 0 else None,
        "failed": failed,
    }
    if remote is None and remotes:
        out["error"] = "multiple remotes without origin"
        return out
    if remote is None:
        ref = str(out["branch"] or "HEAD")
        out["pins_ref"] = ref
        out["pins"], pin_failures = _pins(top, ref)
        failed.extend(pin_failures)
        return out
    if fetch:
        out["fetch_ok"] = _git(repo, "fetch", remote)[0] == 0
    default = _default_branch(repo, remote)
    out["default_branch"] = default
    if default is None:
        failed.append("default branch")
        return out
    ref = f"{remote}/{default}"
    if _git(repo, "rev-parse", "--verify", "--quiet", ref)[0] != 0:
        ref = default
    behind = _git(repo, "rev-list", "--count", f"{default}..{remote}/{default}")
    ahead = _git(repo, "rev-list", "--count", f"{remote}/{default}..{default}")
    out["behind_remote"] = int(behind[1]) if behind[0] == 0 and behind[1] else None
    out["ahead_remote"] = int(ahead[1]) if ahead[0] == 0 and ahead[1] else None
    if out["ahead_remote"] and out["behind_remote"] == 0:
        ref = default
    out["pins_ref"] = ref
    out["pins"], pin_failures = _pins(top, ref)
    failed.extend(pin_failures)
    return out


def _lock_versions(text: str) -> dict[str, set[str]]:
    """Map package name to its versions from ``[[package]]`` tables (uv, Poetry, Cargo).

    A local project table (``source = { virtual | editable = ... }``) may omit ``version`` when uv
    resolves it dynamically; it names no version to move.
    """
    found: dict[str, set[str]] = {}
    blocks = re.split(
        r"^\[\[package\]\][ \t]*(?:#.*)?$",
        text.replace("\r\n", "\n"),
        flags=re.MULTILINE,
    )
    if len(blocks) == 1:
        message = "no readable package tables"
        raise ValueError(message)
    for block in blocks[1:]:
        name = re.search(
            r"""^name\s*=\s*(['"])([^'"\r\n]+)\1[ \t]*(?:#.*)?$""", block, re.MULTILINE
        )
        version = re.search(
            r"""^version\s*=\s*(['"])([^'"\r\n]+)\1[ \t]*(?:#.*)?$""", block, re.MULTILINE
        )
        if (
            name
            and not version
            and re.search(r"^source\s*=\s*\{\s*(virtual|editable)\s*=", block, re.MULTILINE)
        ):
            continue
        if not name or not version:
            message = "package name or version is not readable"
            raise ValueError(message)
        found.setdefault(name.group(2), set()).add(version.group(2))
    return found


def _series(version: str) -> tuple[int, ...]:
    """Return ``(major,)``, or ``(0, minor)`` for a 0.x version."""
    match = re.match(r"v?(\d+)(?:\.(\d+))?", version.strip())
    if not match:
        message = f"unrecognized version {version!r}"
        raise ValueError(message)
    major, minor = int(match.group(1)), int(match.group(2) or 0)
    return (major,) if major else (0, minor)


def _split(
    changed: list[tuple[dict[str, object], set[str], set[str]]],
) -> dict[str, list[dict[str, object]]]:
    """Split changes into new-series (``majors``) and same-series (``in_range``) moves."""
    majors: list[dict[str, object]] = []
    in_range: list[dict[str, object]] = []
    for entry, before, after in changed:
        gone, came = sorted(before - after), sorted(after - before)
        if not gone and not came:
            continue
        old_series = {_series(v) for v in before}
        crossed = bool(old_series) and any(_series(v) not in old_series for v in came)
        (majors if crossed else in_range).append({**entry, "from": gone, "to": came})
    return {"majors": majors, "in_range": in_range}


def lock_changes(old: str, new: str) -> dict[str, list[dict[str, object]]]:
    """Split the packages that differ between two lock texts into majors and in-range moves."""
    before, after = _lock_versions(old), _lock_versions(new)
    return _split(
        [
            ({"name": name}, before.get(name, set()), after.get(name, set()))
            for name in sorted(set(before) | set(after))
        ]
    )


def _spec_version(spec: str) -> str | None:
    """Return the first version number in a dependency range, or None when it names none."""
    if "://" in spec or spec.startswith(("file:", "link:", "workspace:", "catalog:", "git")):
        return None
    match = re.search(r"\d+(?:\.\d+)*", spec)
    return match.group(0) if match else None


def _ranges(text: str) -> dict[tuple[str, str], str]:
    data: object = json.loads(text)
    if not isinstance(data, dict):
        message = "manifest is not a JSON object"
        raise ValueError(message)  # noqa: TRY004
    found: dict[tuple[str, str], str] = {}
    for section in DEPENDENCY_SECTIONS:
        table: object = cast("dict[str, object]", data).get(section, {})
        if not isinstance(table, dict):
            message = f"{section} is not a JSON object"
            raise ValueError(message)  # noqa: TRY004
        found.update(
            {
                (section, k): v
                for k, v in cast("dict[str, object]", table).items()
                if isinstance(v, str)
            }
        )
    return found


def manifest_changes(old: str, new: str) -> dict[str, list[dict[str, object]]]:
    """Split changed dependency ranges into majors, in-range moves and unclassified ones."""
    before, after = _ranges(old), _ranges(new)
    unclassified: list[dict[str, object]] = []
    changed: list[tuple[dict[str, object], set[str], set[str]]] = []
    for key in sorted(set(before) | set(after)):
        old_spec, new_spec = before.get(key), after.get(key)
        if old_spec == new_spec:
            continue
        entry: dict[str, object] = {"section": key[0], "name": key[1]}
        old_v = _spec_version(old_spec) if old_spec else None
        new_v = _spec_version(new_spec) if new_spec else None
        if (
            (old_spec and old_v is None)
            or (new_spec and new_v is None)
            or (old_spec and new_spec and old_v == new_v)
        ):
            unclassified.append({**entry, "from": old_spec, "to": new_spec})
            continue
        changed.append((entry, {old_v} if old_v else set(), {new_v} if new_v else set()))
    return {**_split(changed), "unclassified": unclassified}


def _tracked(repo: str, names: tuple[str, ...]) -> list[str] | None:
    """Return tracked files at any depth whose basename is in ``names``; None if unreadable."""
    code, out = _git(repo, "ls-files", "-z")
    if code:
        return None
    return sorted(p for p in out.split("\0") if p and p.rsplit("/", maxsplit=1)[-1] in names)


def _diff_files(
    repo: str,
    names: list[str],
    compare: Callable[[str, str], dict[str, list[dict[str, object]]]],
) -> dict[str, object]:
    out: dict[str, object] = {"path": repo}
    for name in names:
        state, old = _read(repo, "HEAD", name)
        if state == FAILED:
            out[name] = {"error": "HEAD baseline is not readable"}
            continue
        try:
            new = (Path(repo) / name).read_text()
        except OSError, UnicodeError:
            out[name] = {"error": "not readable"}
            continue
        if state == ABSENT:
            out[name] = {"new": True}
            continue
        try:
            out[name] = compare(old, new)
        except ValueError as error:
            out[name] = {"error": str(error)}
    return out


def _default_names(repo: str, basenames: tuple[str, ...]) -> list[str] | dict[str, object]:
    tracked = _tracked(repo, basenames)
    if tracked is None:
        return {"path": repo, "error": "tracked files are not readable"}
    return sorted({*tracked, *(n for n in basenames if (Path(repo) / n).is_file())})


def lock_diff(repo: str, lockfiles: list[str]) -> dict[str, object]:
    """Compare each lockfile at HEAD with the working tree."""
    names = lockfiles or _default_names(repo, LOCKFILES)
    if isinstance(names, dict):
        return names
    return _diff_files(repo, names, lock_changes)


def manifest_diff(repo: str, manifests: list[str]) -> dict[str, object]:
    """Compare each ``package.json`` at HEAD with the working tree."""
    names = manifests or _default_names(repo, (MANIFEST,))
    if isinstance(names, dict):
        return names
    return _diff_files(repo, names, manifest_changes)


SITE_LIMIT = 200


def pin_sites(repo: str, name: str) -> dict[str, object]:
    """List every tracked line that mentions ``name`` as a whole word, with its file and line."""
    code, out = _git(repo, "grep", "-n", "-I", "-w", "-F", "-z", "-e", name)
    if code not in (0, 1):
        return {"path": repo, "name": name, "error": "tracked files are not searchable"}
    sites: list[dict[str, object]] = []
    for record in out.split("\n"):
        parts = record.split("\0")
        if len(parts) == 3 and parts[1].isdigit():
            sites.append({"file": parts[0], "line": int(parts[1]), "text": parts[2].strip()[:200]})
    shown = sites[:SITE_LIMIT]
    return {"path": repo, "name": name, "total": len(sites), "sites": shown}


def free_branch(repo: str, name: str) -> dict[str, object]:
    """Return ``name``, else the first ``name-N`` that no local or remote branch uses."""
    code, out = _git(repo, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    if code:
        return {"path": repo, "error": "branches are not readable"}
    taken: set[str] = set()
    for ref in out.splitlines():
        parts = ref.split("/", 3 if ref.startswith("refs/remotes/") else 2)
        taken.add(parts[-1])
    candidate, n = name, 1
    while candidate in taken:
        n += 1
        candidate = f"{name}-{n}"
    return {"path": repo, "branch": candidate}


def issue_branch(number: str, title: str) -> dict[str, object]:
    """Return ``<number>-<slug>``; accents fold to ASCII, letters with no ASCII form drop."""
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = "-".join(re.findall(r"[a-z0-9]+", folded.lower()))[:50].strip("-")
    return {"branch": f"{number}-{slug}" if slug else number}


SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "target", "__pycache__"})
BOT = "[bot]"


def _repos_under(root: str) -> list[str]:
    found: list[str] = []
    for here, dirs, _ in os.walk(root):
        if (Path(here) / ".git").exists():
            found.append(here)
            dirs[:] = []
        else:
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
    return found


def _remote_key(url: str) -> str:
    """Return ``host/owner/name`` lowercased from a git remote URL; ``""`` when unparsable."""
    match = re.match(
        r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^/:]+)[:/]+(.+?)(?:\.git)?/?$", url.strip(), re.IGNORECASE
    )
    return f"{match.group(1)}/{match.group(2)}".lower() if match else ""


def _scope_row(path: str, owners: set[str]) -> dict[str, object]:
    code, top = _git(path, "rev-parse", "--show-toplevel")
    if code:
        return {"path": path, "error": "not a git repository"}
    _, git_dir = _git(path, "rev-parse", "--path-format=absolute", "--git-dir")
    _, common = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    _, super_wt = _git(path, "rev-parse", "--show-superproject-working-tree")
    remotes = _remotes(path)
    remote = "origin" if "origin" in remotes else next(iter(remotes), "")
    key = _remote_key(remotes.get(remote, ""))
    owner = key.split("/")[1] if key.count("/") >= 2 else ""
    ref = "HEAD"
    if remote:
        code, head = _git(path, "symbolic-ref", f"refs/remotes/{remote}/HEAD")
        ref = head.removeprefix("refs/remotes/") if code == 0 else "HEAD"
    _, log = _git(path, "log", "--max-count=10", "--format=%ae%x09%an", ref)
    authors = [line.split("\t") for line in log.splitlines()]
    _, mine = _git(path, "config", "user.email")
    return {
        "path": top,
        "remote_key": key,
        "owner_match": None if not owners else owner in owners,
        "linked_worktree": git_dir != common,
        "clone": str(Path(common).parent) if git_dir != common else top,
        "submodule": bool(super_wt),
        "fork_signal": "upstream" in remotes,
        "author_email": mine or None,
        "email_in_recent": bool(mine) and any(a[0] == mine for a in authors),
        "bot_only": bool(authors) and all(BOT in a[-1] for a in authors),
        "excluded": None,
    }


def scope(
    roots: list[str], repos: list[str], owners: list[str], cwd: str = "."
) -> list[dict[str, object]]:
    """Resolve the repositories a sweep covers and mark each one it excludes, with the rule.

    Exclusion rules, in order: ``submodule``, ``worktree`` (the clone is its own row),
    ``owner``, ``duplicate`` (same remote as an earlier row). Forge checks stay with the caller.
    """
    wanted = {o.lower() for o in owners}
    found = [r for root in roots for r in _repos_under(root)]
    chosen = list(found)
    rows: list[dict[str, object]] = []
    for name in repos:
        if (Path(name) / ".git").exists():
            chosen.append(name)
            continue
        matches = [
            r
            for r in found
            if _remote_key(_remotes(r).get("origin", "")).endswith(f"/{name.lower()}")
        ]
        if matches:
            chosen.extend(matches)
        else:
            rows.append({"path": name, "error": "repository not found"})
    if not roots and not repos:
        chosen.append(cwd)
    seen_keys: set[str] = set()
    for path in dict.fromkeys(str(Path(c).resolve()) for c in chosen):
        row = _scope_row(path, wanted)
        rows.append(row)
        if "error" in row:
            continue
        key = str(row["remote_key"])
        if row["submodule"]:
            row["excluded"] = "submodule"
        elif row["linked_worktree"]:
            row["excluded"] = "worktree"
        elif wanted and not row["owner_match"]:
            row["excluded"] = "owner"
        elif key and key in seen_keys:
            row["excluded"] = "duplicate"
        elif key:
            seen_keys.add(key)
    return rows


def _scope_args(args: list[str]) -> tuple[list[str], list[str], list[str]] | None:
    values: dict[str, list[str]] = {"--root": [], "--repo": [], "--owner": []}
    current = ""
    for arg in args:
        if arg in values:
            current = arg
        elif arg.startswith("-") or not current:
            return None
        else:
            values[current].append(arg)
    if any(not values[k] for k in values if k in args):
        return None
    return values["--root"], values["--repo"], values["--owner"]


USAGE = (
    "usage: repo_facts.py [--fetch] [REPO...] | --lock-diff REPO [LOCKFILE...] | "
    "--manifest-diff REPO [MANIFEST...] | --pin-sites REPO NAME | "
    "--free-branch REPO NAME | --issue-branch NUMBER TITLE | "
    "--scope [--root DIR...] [--repo PATH|SLUG...] [--owner NAME...]"
)


def _failed(result: dict[str, object]) -> bool:
    return any(k == "error" or (isinstance(v, dict) and "error" in v) for k, v in result.items())


def _emit(results: list[dict[str, object]]) -> int:
    for result in results:
        sys.stdout.write(json.dumps(result) + "\n")
    bad = [r for r in results if _failed(r)]
    if bad:
        sys.stderr.write(f"repo_facts.py: {len(bad)} result(s) carry an error; see the JSON\n")
    return 1 if bad else 0


def _lock_mode(a: list[str]) -> dict[str, object]:
    return lock_diff(a[0], a[1:])


def _manifest_mode(a: list[str]) -> dict[str, object]:
    return manifest_diff(a[0], a[1:])


def _pin_mode(a: list[str]) -> dict[str, object]:
    return pin_sites(a[0], a[1])


def _branch_mode(a: list[str]) -> dict[str, object]:
    return free_branch(a[0], a[1])


def _issue_mode(a: list[str]) -> dict[str, object]:
    return issue_branch(a[0], a[1])


def _run_mode(mode: str, args: list[str]) -> list[dict[str, object]] | None:
    """Run a mode; None when ``args`` do not fit it."""
    arity = {
        "--lock-diff": (1, None),
        "--manifest-diff": (1, None),
        "--pin-sites": (2, 2),
        "--free-branch": (2, 2),
        "--issue-branch": (2, 2),
    }
    if mode == "--scope":
        parsed = _scope_args(args)
        return None if parsed is None else scope(*parsed)
    low, high = arity[mode]
    if len(args) < low or (high is not None and len(args) > high):
        return None
    one: dict[str, Callable[[list[str]], dict[str, object]]] = {
        "--lock-diff": _lock_mode,
        "--manifest-diff": _manifest_mode,
        "--pin-sites": _pin_mode,
        "--free-branch": _branch_mode,
        "--issue-branch": _issue_mode,
    }
    return [one[mode](args)]


MODES = frozenset(
    {"--scope", "--lock-diff", "--manifest-diff", "--pin-sites", "--free-branch", "--issue-branch"}
)


def main(argv: list[str]) -> int:
    """Print one JSON line per repository; exit 2 on bad usage, 1 when a result carries an error."""
    if argv[:1] in (["--help"], ["-h"]):
        sys.stdout.write(USAGE + "\n")
        return 0
    unknown = [a for a in argv if a.startswith("-") and a != "--fetch"]
    if argv[:1] and argv[0] in MODES:
        results = _run_mode(argv[0], argv[1:])
        if results is None:
            sys.stderr.write(f"repo_facts.py: {argv[0]} takes different arguments\n")
            return 2
        return _emit(results)
    if unknown:
        sys.stderr.write(f"repo_facts.py: unknown option {unknown[0]}\n")
        return 2
    fetch = "--fetch" in argv
    repos = [a for a in argv if a != "--fetch"] or ["."]
    return _emit(
        [
            facts(repo, fetch=fetch)
            if Path(repo).is_dir()
            else {"path": repo, "error": "not a directory"}
            for repo in repos
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
